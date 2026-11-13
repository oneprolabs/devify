"""Analysis job execution: leases, fencing, checkpoints and rule extraction.

Execution never trusts a worker beyond its lease. Every claim increments the
job's fencing token, so a worker whose lease expired cannot complete or
overwrite a job that another worker has taken over.

The first extractor is deliberately rule based: it turns a message window
into chunked Notes with message evidence. Automatic runs reuse stable note
keys and the existing Note service, which refuses to overwrite manual Notes.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chat_analysis.keys import canonical_event_key, slugify_key
from chat_analysis.models import AnalysisJob, Event, EventSuggestion, Note
from chat_analysis.services import (
    ChatAnalysisError,
    ChatAnalysisPermissionError,
    add_note_evidence,
    create_note,
    refresh_event_window,
)
from chat_analysis.suggestions import (
    create_event_suggestion,
    review_event_suggestion,
)
from chat_domain.models import Message, MessagePart
from core.tracking import LLMTracker
from spaces.models import Space, SpaceWorkflowConfig
from spaces.services import SpacePermissionService

logger = logging.getLogger(__name__)

DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3
ANALYSIS_CHUNK_SIZE = 200
ENGINE_VERSION = "chat-analysis.v2"
MAX_EVENTS_PER_CHUNK = 8
EXISTING_EVENT_CONTEXT_LIMIT = 40
CROSS_CANDIDATE_LIMIT = 12
DEFAULT_OUTPUT_LANGUAGE = "zh-CN"
MODULE_LOADED_AT = time.time()
MODULE_PATH = os.path.abspath(__file__)


class AnalysisJobRejected(Exception):
    """Raised when a job may not run for a non-transient reason."""


class AnalysisLeaseLost(Exception):
    """Raised when a worker no longer holds the job lease."""


@dataclass(frozen=True)
class ExecutionResult:
    job: AnalysisJob
    handler_result: dict


def _lock_job(job_id):
    return AnalysisJob.objects.select_for_update().filter(pk=job_id).first()


def _ensure_lease(job, worker_id, fencing_token):
    if (
        job.state != AnalysisJob.State.RUNNING
        or job.lease_owner != worker_id
        or job.fencing_token != fencing_token
    ):
        raise AnalysisLeaseLost(
            "The analysis job lease is no longer held by this worker."
        )


def claim_analysis_job(
    job_id,
    *,
    worker_id,
    lease_seconds=DEFAULT_LEASE_SECONDS,
):
    """Claim a queued job or an expired running job.

    Returns ``None`` when another worker holds a live lease or the job is in
    a terminal state. Each successful claim increments ``fencing_token`` and
    ``attempts``.
    """
    if not worker_id:
        raise ValueError("worker_id is required.")
    now = timezone.now()
    with transaction.atomic():
        job = _lock_job(job_id)
        if job is None:
            return None
        if job.state == AnalysisJob.State.RUNNING:
            if job.lease_until and job.lease_until > now:
                return None
        elif job.state != AnalysisJob.State.QUEUED:
            return None
        job.state = AnalysisJob.State.RUNNING
        job.lease_owner = worker_id
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.fencing_token = job.fencing_token + 1
        job.attempts = job.attempts + 1
        job.engine_version = ENGINE_VERSION
        job.error = ""
        job.save(
            update_fields=(
                "state",
                "lease_owner",
                "lease_until",
                "fencing_token",
                "attempts",
                "engine_version",
                "error",
                "updated_at",
            )
        )
        return job


def renew_analysis_lease(
    job,
    *,
    worker_id,
    fencing_token,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    checkpoint=None,
):
    """Extend the lease and optionally store a checkpoint."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.lease_until = timezone.now() + timedelta(seconds=lease_seconds)
        update_fields = ["lease_until", "updated_at"]
        if checkpoint is not None:
            locked.checkpoint = checkpoint
            update_fields.append("checkpoint")
        locked.save(update_fields=update_fields)
        return locked


def update_analysis_checkpoint(
    job,
    *,
    worker_id,
    fencing_token,
    checkpoint,
):
    return renew_analysis_lease(
        job,
        worker_id=worker_id,
        fencing_token=fencing_token,
        checkpoint=checkpoint,
    )


def complete_analysis_job(
    job,
    *,
    worker_id,
    fencing_token,
    checkpoint=None,
    result_ref=None,
    partial=False,
):
    """Finish a job as ``ready`` or, with unreadable input, ``partial``."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.state = (
            AnalysisJob.State.PARTIAL if partial else AnalysisJob.State.READY
        )
        if checkpoint is not None:
            locked.checkpoint = checkpoint
        if result_ref is not None:
            locked.result_ref = result_ref
        locked.lease_owner = ""
        locked.lease_until = None
        locked.error = ""
        locked.save(
            update_fields=(
                "state",
                "checkpoint",
                "result_ref",
                "lease_owner",
                "lease_until",
                "error",
                "updated_at",
            )
        )
        return locked


def fail_analysis_job(
    job,
    *,
    worker_id,
    fencing_token,
    error,
    retryable=False,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
    checkpoint=None,
):
    """Record a failure and requeue it while attempts remain."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.error = str(error)[:4000]
        if checkpoint is not None:
            locked.checkpoint = checkpoint
        locked.lease_owner = ""
        locked.lease_until = None
        if retryable and locked.attempts < max_attempts:
            locked.state = AnalysisJob.State.QUEUED
        else:
            locked.state = AnalysisJob.State.FAILED
        locked.save(
            update_fields=(
                "state",
                "error",
                "checkpoint",
                "lease_owner",
                "lease_until",
                "updated_at",
            )
        )
        return locked


def execute_analysis_job(
    job_id,
    *,
    worker_id,
    handler=None,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
):
    """Claim and run one job, recording success, retry or failure.

    ``handler`` receives the claimed job and a ``lease_seconds`` keyword. It
    must return a dict with optional ``checkpoint``, ``partial`` and
    ``result_ref`` keys. A handler that loses its lease raises
    ``AnalysisLeaseLost`` instead of writing over the new owner's work.
    """
    job = claim_analysis_job(
        job_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if job is None:
        return None
    handler = handler or run_rule_based_analysis
    try:
        outcome = handler(job, lease_seconds=lease_seconds)
    except AnalysisLeaseLost:
        raise
    except Exception as exc:
        non_retryable = isinstance(
            exc,
            (
                AnalysisJobRejected,
                ChatAnalysisPermissionError,
                ChatAnalysisError,
            ),
        )
        failed = fail_analysis_job(
            job,
            worker_id=worker_id,
            fencing_token=job.fencing_token,
            error=f"{type(exc).__name__}: {exc}",
            retryable=not non_retryable,
            max_attempts=max_attempts,
        )
        return ExecutionResult(job=failed, handler_result={"error": str(exc)})
    if not isinstance(outcome, dict):
        outcome = {}
    completed = complete_analysis_job(
        job,
        worker_id=worker_id,
        fencing_token=job.fencing_token,
        checkpoint=outcome.get("checkpoint"),
        result_ref=outcome.get("result_ref"),
        partial=bool(outcome.get("partial")),
    )
    return ExecutionResult(job=completed, handler_result=outcome)


def _ensure_job_runnable(job):
    if job.space.status != Space.Status.ACTIVE:
        raise AnalysisJobRejected("Space is not active.")
    if not SpacePermissionService.can_upload(job.created_by, job.space):
        raise AnalysisJobRejected(
            "The initiating user can no longer write to the space."
        )


def _message_texts(message):
    return [
        part.text.strip()
        for part in message.parts.all()
        if part.kind == MessagePart.Kind.TEXT
        and part.text
        and part.text.strip()
    ]


def _write_chunk_note(job, messages):
    """Create or refresh the automatic Note for one message chunk."""
    conversation = job.conversation
    lines = []
    occurred_at = []
    missing_content = False
    for message in messages:
        if message.occurred_at:
            occurred_at.append(message.occurred_at)
        texts = _message_texts(message)
        if not texts:
            missing_content = True
            continue
        if message.occurred_at:
            stamp = timezone.localtime(message.occurred_at).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            stamp = "unknown-time"
        sender = message.sender_name or message.sender_key or "unknown"
        lines.append(f"[{stamp}] {sender}: {' / '.join(texts)}")
    if not lines:
        return False, True
    first_seq = messages[0].ingest_seq
    last_seq = messages[-1].ingest_seq
    title = (
        f"{conversation.title or conversation.identity_key} "
        f"#{first_seq}-{last_seq}"
    )[:500]
    note = create_note(
        actor=job.created_by,
        space=job.space,
        note_key=f"job:{job.uuid}:{first_seq}-{last_seq}",
        title=title,
        content="\n".join(lines),
        start_at=min(occurred_at) if occurred_at else None,
        end_at=max(occurred_at) if occurred_at else None,
        analysis_job=job,
    )
    if note.origin == Note.Origin.MANUAL:
        return False, missing_content
    for message in messages:
        add_note_evidence(
            actor=job.created_by,
            note=note,
            message=message,
        )
    partial = _enrich_note_with_llm(job, note, messages)
    return True, missing_content or partial


def _output_language(space):
    language = (
        SpaceWorkflowConfig.objects.filter(space=space)
        .values_list("language", flat=True)
        .first()
    )
    return language or DEFAULT_OUTPUT_LANGUAGE


def _message_payload(messages):
    return [
        {
            "seq": message.ingest_seq,
            "sender": message.sender_name or message.sender_key,
            "time": (
                message.occurred_at.isoformat()
                if message.occurred_at
                else None
            ),
            "text": " / ".join(_message_texts(message)),
            "reply_to_seq": (
                message.reply_to.ingest_seq
                if message.reply_to_id
                else None
            ),
        }
        for message in messages
    ]


def _message_people(messages):
    people = set()
    for message in messages:
        for value in (message.sender_name, message.sender_key):
            key = slugify_key(value)
            if key:
                people.add(key)
    return people


def _text_overlaps(left, right):
    left_key = slugify_key(left)
    right_key = slugify_key(right)
    if len(left_key) < 2 or len(right_key) < 2:
        return False
    return left_key in right_key or right_key in left_key


def _chunk_text(messages):
    return " ".join(
        " ".join(_message_texts(message)) for message in messages
    )


def _event_overlaps_chunk(event, messages):
    """True when person, title or entity overlaps this chunk."""
    chunk_text = _chunk_text(messages)
    if event.entity_key and _text_overlaps(event.entity_key, chunk_text):
        return True
    if event.title and _text_overlaps(event.title, chunk_text):
        return True
    chunk_people = _message_people(messages)
    evidence_people = set()
    for link in event.evidence.all():
        evidence_people |= _message_people([link.message])
    return bool(chunk_people & evidence_people)


def _event_prompt_item(event, conversation_title):
    return {
        "event_key": event.event_key,
        "title": event.title,
        "summary": event.content,
        "status": event.status or Event.Status.OPEN,
        "entity": event.entity_key,
        "conversation_title": conversation_title,
    }


def _unfinished_event_qs(space):
    return (
        Event.objects.filter(space=space)
        .exclude(status=Event.Status.DONE)
        .prefetch_related("evidence__message__conversation")
        .order_by("-last_activity_at", "-id")
    )


def _open_events_same_conversation(space, conversation):
    title = conversation.title or conversation.identity_key
    events = (
        _unfinished_event_qs(space)
        .filter(evidence__message__conversation_id=conversation.pk)
        .distinct()[:EXISTING_EVENT_CONTEXT_LIMIT]
    )
    return [_event_prompt_item(event, title) for event in events]


def _other_conversation_title(event, conversation_id):
    for link in event.evidence.all():
        other = link.message.conversation
        if other.pk != conversation_id:
            return other.title or other.identity_key
    return ""


def _cross_candidates(space, conversation, messages):
    events = (
        _unfinished_event_qs(space)
        .exclude(evidence__message__conversation_id=conversation.pk)
        .distinct()[:EXISTING_EVENT_CONTEXT_LIMIT]
    )
    selected = []
    for event in events:
        if not _event_overlaps_chunk(event, messages):
            continue
        selected.append(
            _event_prompt_item(
                event,
                _other_conversation_title(event, conversation.pk),
            )
        )
        if len(selected) >= CROSS_CANDIDATE_LIMIT:
            break
    return selected


def _cited_messages(event, by_seq):
    """Resolve cited seqs from sources or legacy source_seqs."""
    source_messages = []
    roles = []
    sources = event.get("sources")
    if isinstance(sources, list) and sources:
        for item in sources:
            if not isinstance(item, dict):
                continue
            try:
                seq = int(item.get("seq"))
            except (TypeError, ValueError):
                continue
            message = by_seq.get(seq)
            if message is None:
                continue
            source_messages.append(message)
            role = str(item.get("role") or "matter").strip().lower()
            roles.append(role or "matter")
        return source_messages, roles
    for value in event.get("source_seqs") or []:
        try:
            seq = int(value)
        except (TypeError, ValueError):
            continue
        message = by_seq.get(seq)
        if message is None:
            continue
        source_messages.append(message)
        roles.append("matter")
    return source_messages, roles


def _reject_pending_false_positive(*, actor, space, event_key):
    """Reject pending suggestions that never became Events."""
    canonical_key = canonical_event_key(event_key)
    if not canonical_key:
        return
    pending = EventSuggestion.objects.filter(
        space=space,
        event_key=canonical_key,
        status=EventSuggestion.Status.PENDING,
        event__isnull=True,
    )
    for suggestion in pending:
        review_event_suggestion(
            actor=actor,
            suggestion=suggestion,
            decision=EventSuggestion.Status.REJECTED,
        )


def _event_extraction_prompt(language, preferences):
    """Ask the model to judge create, attach or drop for one chat chunk."""
    granularity = preferences.get("event_granularity", "balanced")
    style = preferences.get("summary_style", "concise")
    length = preferences.get("summary_length", "standard")
    return (
        "Judge trackable matters in one conversation chunk, fold them into "
        "existing events when they are the same matter, and name the source "
        "chat for every message you use. Return JSON: "
        '{"events":[{"action":"create"|"attach"|"drop","event_key":"",'
        '"title":"","summary":"","status":"open"|"in_progress"|"done",'
        '"entity":"","tags":[],"sources":[{"seq":0,"conversation_title":"",'
        '"role":"matter"|"confirmation"}],"cross_decision":"same"|"related"'
        '|"separate"|null,"reason":""}]}. '
        "Input fields: conversation_title; messages with seq, sender, time, "
        "text, reply_to_seq; open_events_same_conversation; "
        "cross_candidates. reply_to_seq is the quoted message when WeChat "
        "has one, otherwise null. open_events_same_conversation are "
        "unfinished events from this same chat. cross_candidates are "
        "unfinished events from other chats that already share a person or "
        "a concrete subject with this chunk. Do not treat that list as the "
        "whole space. If a candidate is not in the list, do not merge with "
        "it. "
        "A trackable matter is an assignment, a reminder that expects "
        "action, a decision, a commitment, a deadline, or a follow-up "
        "someone still owes. Greetings, jokes, small talk, meals, casual "
        "invitations, and short replies that confirm nothing are not "
        'events. If this chunk has no trackable matter, return {"events":'
        "[]}. If an existing event is only trivial chat and these messages "
        "do not continue a real matter, emit action drop with that "
        "event_key so a rerun can remove it. "
        'A message whose text is only "1", "收到", "好的", "ok", "嗯" or '
        '"知道了" is a confirmation, never a new event. If reply_to_seq is '
        "set, the confirmation belongs to the matter of that quoted "
        "message. If reply_to_seq is null, attach it to the latest "
        "unfinished matter in this conversation that was directed at the "
        "sender. Later messages from other people do not break the link. "
        "If several unfinished matters fit and none is clearly the target, "
        "or none fits, ignore the reply. "
        "Same conversation: action attach when the candidate continues an "
        "event in open_events_same_conversation, or a confirmation "
        "resolves one. Set event_key to that event. Rewrite summary so it "
        "includes who confirmed and what remains. Set status to "
        "in_progress if work remains, or done if this message closes it. "
        "action create only when no open event in this conversation is the "
        "same matter. Leave event_key empty. A similar topic is not the "
        "same matter. "
        "Cross conversation, only for action create, and only against "
        "cross_candidates: cross_decision same only when both sides are "
        "the same specific assignment, decision or commitment. Set "
        "event_key to that candidate and change action to attach. related "
        "when the topic is similar but it is not the same instance. Words "
        'such as "报价" or "周末" are not enough. Leave event_key empty '
        "and keep action create. separate when they are different "
        "matters. If several candidates could be same and one is not "
        "clearly right, return related. For action attach or drop, set "
        "cross_decision to null. "
        "sources lists every message that supports the event, including "
        "the confirmation. conversation_title is the group or chat name, "
        "not a numeric id. role is matter or confirmation. status is "
        "open, in_progress or done. tags are at most five short labels. "
        f"Return at most {MAX_EVENTS_PER_CHUNK} events. Do not invent "
        f"facts. Write title, summary and reason in {language}. "
        f"Event granularity: {granularity}. For coarse granularity combine "
        "related developments of the same matter rather than creating "
        "fragments. "
        f"Summary style: {style}; detail: {length}."
    )


def _call_json(*, prompt, content, node_name):
    output, _usage = LLMTracker.call_and_track(
        prompt=prompt,
        content=content,
        json_mode=True,
        node_name=node_name,
        state={},
    )
    return output if isinstance(output, dict) else None


def _summarize_note(note, payload, language, preferences=None):
    preferences = preferences or {}
    style = preferences.get("summary_style", "concise")
    length = preferences.get("summary_length", "standard")
    prompt = (
        "Summarize one chunk of chat messages. Return JSON with exactly the "
        "keys facts, actions, risks and decisions. Every item must be an "
        "object with a short text field. Do not include events. Do not "
        f"invent facts. Write all text in {language}. "
        f"Summary style: {style}; level of detail: {length}."
    )
    output = _call_json(
        prompt=prompt,
        content=json.dumps(payload, ensure_ascii=False),
        node_name="chat_note_structuring",
    )
    if output is None:
        return False
    note.structured_data = output
    note.generation_version = "chat-note-llm.v1"
    note.save(
        update_fields=(
            "structured_data",
            "generation_version",
            "updated_at",
        )
    )
    return True


def _extract_events(job, note, messages, payload, language):
    preferences = (job.specification or {}).get(
        "chat_analysis_preferences", {}
    )
    conversation = job.conversation
    conversation_title = (
        conversation.title or conversation.identity_key
    )
    prompt = _event_extraction_prompt(language, preferences)
    content = json.dumps(
        {
            "conversation_title": conversation_title,
            "messages": payload,
            "open_events_same_conversation": (
                _open_events_same_conversation(
                    note.space,
                    conversation,
                )
            ),
            "cross_candidates": _cross_candidates(
                note.space,
                conversation,
                messages,
            ),
        },
        ensure_ascii=False,
    )
    output = _call_json(
        prompt=prompt,
        content=content,
        node_name="chat_event_extraction",
    )
    if output is None:
        return False
    events = output.get("events")
    if not isinstance(events, list):
        return False
    by_seq = {message.ingest_seq: message for message in messages}
    for index, event in enumerate(events[:MAX_EVENTS_PER_CHUNK]):
        if not isinstance(event, dict):
            continue
        action = str(event.get("action") or "create").strip().lower()
        if action not in ("create", "attach", "drop"):
            action = "create"
        if action == "drop":
            key = str(event.get("event_key") or "").strip()
            if key:
                _reject_pending_false_positive(
                    actor=job.created_by,
                    space=note.space,
                    event_key=key,
                )
            continue
        title = str(event.get("title") or "").strip()
        summary = str(event.get("summary") or "").strip()
        if not title or not summary:
            continue
        status = str(event.get("status") or "").strip().lower()
        if status not in Event.Status.values:
            status = Event.Status.OPEN
        source_messages, roles = _cited_messages(event, by_seq)
        confirmation_only = bool(roles) and all(
            role == "confirmation" for role in roles
        )
        if status == Event.Status.DONE and confirmation_only:
            status = Event.Status.IN_PROGRESS
        tags = [
            str(tag).strip()
            for tag in (event.get("tags") or [])
            if str(tag).strip()
        ][:5]
        event_key = str(
            event.get("event_key")
            or f"{job.uuid}:event:{messages[0].ingest_seq}:{index}"
        )[:255]
        suggestion = create_event_suggestion(
            actor=job.created_by,
            note=note,
            analysis_job=job,
            event_key=event_key,
            entity_key=str(event.get("entity") or ""),
            title=title,
            summary=summary,
            status=status,
            tags=tags,
            source_seqs=[
                message.ingest_seq for message in source_messages
            ],
        )
        if getattr(settings, "CHAT_ANALYSIS_AUTO_CREATE_EVENTS", False):
            suggestion = review_event_suggestion(
                actor=job.created_by,
                suggestion=suggestion,
                decision=EventSuggestion.Status.ACCEPTED,
            )
            if suggestion.event_id and not source_messages:
                refresh_event_window(suggestion.event, messages=messages)
    return True


def _enrich_note_with_llm(job, note, messages):
    """Structure a Note and propose Events without mutating Events.

    Summary and event extraction are separate calls: one combined call used
    to fill the model's output budget and silently drop the event list.
    Returns True when part of the work could not be produced.
    """
    if not getattr(settings, "CHAT_ANALYSIS_LLM_ENABLED", False):
        return False
    payload = _message_payload(messages)
    language = _output_language(note.space)
    partial = False
    try:
        if not _summarize_note(
            note,
            payload,
            language,
            (job.specification or {}).get("chat_analysis_preferences"),
        ):
            partial = True
    except Exception:
        # An unavailable LLM is an infrastructure failure, not a data gap:
        # keep the job's state and let the caller retry.
        logger.exception("LLM note structuring failed for job %s", job.pk)
        raise RuntimeError("LLM note structuring failed") from None
    try:
        if not _extract_events(job, note, messages, payload, language):
            partial = True
    except Exception:
        logger.exception("LLM event extraction failed for job %s", job.pk)
        raise RuntimeError("LLM event extraction failed") from None
    return partial


def run_rule_based_analysis(job, *, lease_seconds=DEFAULT_LEASE_SECONDS):
    """Deterministic extractor: chunked Notes plus message evidence.

    It resumes after ``checkpoint["last_ingest_seq"]`` and renews the lease
    after each chunk, so a crashed attempt can be retried without duplicating
    Notes or evidence.
    """
    _ensure_job_runnable(job)
    checkpoint = dict(job.checkpoint or {})
    last_seq = int(checkpoint.get("last_ingest_seq", job.start_seq))
    messages_processed = int(checkpoint.get("messages_processed", 0))
    notes_written = int(checkpoint.get("notes_written", 0))
    partial = bool(checkpoint.get("partial", False))

    preferences = (job.specification or {}).get("chat_analysis_preferences")
    cutoff = (job.specification or {}).get("analysis_cutoff")
    conversation_types = (
        preferences.get("conversation_types", []) if preferences else []
    )
    if not isinstance(conversation_types, list):
        conversation_types = []
    kind = job.conversation.kind
    snapshot_kind = (job.specification or {}).get("analysis_conversation_kind")
    if snapshot_kind is not None and snapshot_kind != kind:
        raise AnalysisJobRejected(
            "Conversation kind changed after the analysis job was created."
        )
    unknown_chat_is_restricted = (
        kind == "unknown"
        and not all(
            item in conversation_types for item in ("direct", "group")
        )
    )
    excluded = bool(
        preferences
        and (
            (kind in ("direct", "group") and kind not in conversation_types)
            or unknown_chat_is_restricted
        )
    )
    batches = job.upload_batches.all()
    while not excluded:
        query = Message.objects.filter(
            conversation_id=job.conversation_id,
            ingest_seq__gt=last_seq,
            ingest_seq__lte=job.end_seq,
            orphaned_at__isnull=True,
        )
        if cutoff:
            query = query.filter(occurred_at__gte=cutoff)
        if batches.exists():
            query = query.filter(
                origins__upload_item__batch__in=batches
            ).distinct()
        messages = list(
            query.select_related("reply_to")
            .prefetch_related("parts")
            .order_by("ingest_seq")[:ANALYSIS_CHUNK_SIZE]
        )
        if not messages:
            break
        written, chunk_partial = _write_chunk_note(job, messages)
        partial = partial or chunk_partial
        notes_written += int(written)
        messages_processed += len(messages)
        last_seq = messages[-1].ingest_seq
        checkpoint = {
            "last_ingest_seq": last_seq,
            "messages_processed": messages_processed,
            "notes_written": notes_written,
            "partial": partial,
        }
        job = renew_analysis_lease(
            job,
            worker_id=job.lease_owner,
            fencing_token=job.fencing_token,
            lease_seconds=lease_seconds,
            checkpoint=checkpoint,
        )

    return {
        "checkpoint": checkpoint,
        "partial": partial,
        "result_ref": {
            "messages_processed": messages_processed,
            "notes_written": notes_written,
            "last_ingest_seq": last_seq,
        },
    }
