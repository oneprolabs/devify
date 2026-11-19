"""Bounded deferred event review, separate from published Events."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from chat_analysis.models import DeferredEventCandidate
from chat_domain.models import MessagePart


CANDIDATE_LIMIT = 8
RECENT_DAYS = 14
FOLLOWUP_SIGNALS = {"action", "deadline", "payment", "acceptance", "blocked"}
ACKNOWLEDGEMENTS = {"1", "ok", "okay", "嗯", "好的", "收到", "知道了", "还是不行"}


def message_has_detail(message):
    text = " / ".join(
        part.text.strip() for part in message.parts.all()
        if part.kind == MessagePart.Kind.TEXT and part.text.strip()
    )
    return bool(text and text.casefold().strip(".。!！?？ ") not in ACKNOWLEDGEMENTS)


def reconsideration_candidates(job, messages):
    """Look back in this chat only; older candidates need a direct reply."""
    if not any(message_has_detail(message) for message in messages):
        return []
    first_seq = min(message.ingest_seq for message in messages)
    newest = max((m.occurred_at for m in messages if m.occurred_at), default=None)
    quotes = {message.reply_to_id for message in messages if message.reply_to_id}
    candidates = DeferredEventCandidate.objects.filter(
        space_id=job.space_id, conversation_id=job.conversation_id,
        message__conversation_id=job.conversation_id,
        message__orphaned_at__isnull=True, message__ingest_seq__lt=first_seq,
        status=DeferredEventCandidate.Status.PENDING,
    ).filter(
        Q(resolution_suggestion__isnull=True)
        | Q(resolution_suggestion__analysis_job__state__in=("failed", "cancelled"))
    ).select_related("message").prefetch_related("message__parts").order_by(
        "-urgent", "-created_at", "-id",
    )
    boundary = (job.specification or {}).get("boundary")
    if boundary:
        candidates = candidates.filter(message__created_at__lte=boundary)
    quoted = list(candidates.filter(message_id__in=quotes)[:CANDIDATE_LIMIT])
    remaining = candidates.exclude(message_id__in=quotes).filter(
        created_at__gte=timezone.now() - timedelta(days=RECENT_DAYS),
    )
    if newest is not None:
        remaining = remaining.filter(
            Q(message__occurred_at__lte=newest) | Q(message__occurred_at__isnull=True)
        )
    return quoted + list(remaining[:CANDIDATE_LIMIT - len(quoted)])


def defer_message(*, job, event, message):
    reason = event.get("defer_reason")
    signal = event.get("followup_signal")
    question = event.get("followup_question")
    if not (
        isinstance(reason, str) and reason in DeferredEventCandidate.Reason.values
        and isinstance(signal, str) and signal in FOLLOWUP_SIGNALS
        and isinstance(question, str) and question.strip()
        and message_has_detail(message)
    ):
        return
    DeferredEventCandidate.objects.get_or_create(
        message=message,
        defaults={
            "space_id": job.space_id, "conversation_id": job.conversation_id,
            "reason": reason, "question": question.strip()[:300],
            "urgent": signal != "action",
        },
    )


def reserve_resolutions(*, job, event, suggestion, current, background):
    """Reserve only shown candidates whose original text was cited again."""
    if not current or not any(message_has_detail(message) for message in current):
        return True
    offered = event.get("_deferred_resolutions", {})
    linked = {message.ingest_seq for message in background}
    ids = {candidate_id for candidate_id, seq in offered.items() if seq in linked}
    if not ids:
        return True
    stored = set(suggestion.source_seqs)
    if not (
        {offered[pk] for pk in ids} <= stored
        and any(message.ingest_seq in stored for message in current)
    ):
        return False
    available = DeferredEventCandidate.objects.filter(
        pk__in=ids, space_id=job.space_id, conversation_id=job.conversation_id,
        message__conversation_id=job.conversation_id, message__orphaned_at__isnull=True,
        status=DeferredEventCandidate.Status.PENDING,
    ).filter(
        Q(resolution_suggestion__isnull=True)
        | Q(resolution_suggestion=suggestion)
        | Q(resolution_suggestion__analysis_job__state__in=("failed", "cancelled"))
    )
    locked = set(available.select_for_update().order_by("pk").values_list("pk", flat=True))
    if locked != ids:
        return False
    DeferredEventCandidate.objects.filter(pk__in=locked).update(
        resolution_suggestion=suggestion, updated_at=timezone.now(),
    )
    return True


def settle_resolutions(suggestion, event=None, *, source_messages=()):
    candidates = DeferredEventCandidate.objects.filter(
        resolution_suggestion=suggestion, status=DeferredEventCandidate.Status.PENDING,
        space_id=suggestion.space_id,
        conversation_id=suggestion.analysis_job.conversation_id,
    )
    now = timezone.now()
    if event is not None:
        # A candidate whose anchor disappeared from the accepted evidence is
        # still unresolved. Release it below so it stays eligible for review.
        candidates.filter(
            message_id__in={message.pk for message in source_messages},
        ).filter(message_id__in=event.evidence.values("message_id")).update(
            status=DeferredEventCandidate.Status.RESOLVED, resolved_event=event,
            resolution_suggestion=None, updated_at=now,
        )
    candidates.update(resolution_suggestion=None, updated_at=now)
