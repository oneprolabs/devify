"""Filter and count personal event labels within an API queryset."""

from django.db.models import Case, Count, Exists, OuterRef, Q, Value, When
from django.db.models.functions import Collate
from django.db.models.lookups import Exact

from chat_analysis.event_relevance import legacy_identity_origins

from chat_analysis.models import (
    EventEvidence,
    EventParticipantEvidence,
    EventSuggestion,
)
from chat_domain.models import ConversationIdentity


RELEVANCE_LABELS = ("my_todo", "related", "other")


def _viewer_identity(user_id, sender_field):
    conversation = OuterRef("message__conversation_id")
    sender = OuterRef(sender_field)
    identities = ConversationIdentity.objects.filter(
        user_id=user_id, conversation_id=conversation,
    )
    # Sender keys are opaque strings. Match the case-sensitive projection
    # used for evidence rather than the database's default text collation.
    known_sender = Exact(Collate("sender_key", "utf8mb4_bin"), sender)
    legacy_sender = Exact(
        Collate("message__sender_key", "utf8mb4_bin"), sender,
    )
    legacy = legacy_identity_origins(user_id).filter(
        legacy_sender, message__conversation_id=conversation,
    )
    return (
        Q(Exists(identities.filter(known_sender)))
        | (Q(~Exists(identities)) & Q(Exists(legacy)))
    )


def with_viewer_relevance(events, user_id):
    """Annotate the same label projected by event_relevance for a page."""
    cited = EventEvidence.objects.filter(
        event_id=OuterRef("suggestion__event_id"),
        message_id=OuterRef("message_id"),
    )
    evidence = EventParticipantEvidence.objects.filter(
        _viewer_identity(user_id, "sender_key"),
        Exists(cited),
        suggestion__status=EventSuggestion.Status.ACCEPTED,
        message__orphaned_at__isnull=True,
    )
    updates = evidence.filter(suggestion__event_id=OuterRef("pk"))
    responsibilities = updates.filter(
        Q(state="open") | (Q(state="done") & ~Q(reference="")),
    )
    participation = EventEvidence.objects.filter(
        _viewer_identity(user_id, "message__sender_key"),
        event_id=OuterRef("pk"),
        message__orphaned_at__isnull=True,
    )
    return events.annotate(
        viewer_relevance=Case(
            When(Exists(responsibilities), then=Value("my_todo")),
            When(
                Q(Exists(updates)) | Q(Exists(participation)),
                then=Value("related"),
            ),
            default=Value("other"),
        )
    )


def relevance_counts(events):
    counts = dict.fromkeys(RELEVANCE_LABELS, 0)
    counts.update(
        events.order_by()
        .values("viewer_relevance")
        .annotate(total=Count("pk", distinct=True))
        .values_list("viewer_relevance", "total")
    )
    return counts
