"""Build bounded scheduled jobs from fully ingested messages."""

import uuid
from datetime import UTC, datetime

from django.conf import settings
from django.db import transaction
from django.db.models import CharField, Exists, F, OuterRef, Q
from django.db.models.functions import Cast
from django.utils import timezone

from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    NoteEvidence,
    ScheduledAnalysisRun,
)
from chat_analysis.schedule_window import (
    DEFAULT_SCHEDULE,
    due_slot,
    slot_boundary,
)
from chat_analysis.services import (
    ChatAnalysisPermissionError,
    create_analysis_job,
    disallowed_conversation_q,
    ensure_can_contribute,
    get_analysis_preferences,
    readable_text_parts,
)
from chat_analysis.user_dispatch import dispatch_lock
from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch
from spaces.models import (
    Space,
    SpaceMembership,
    SpaceTakeover,
    SpaceWorkflowConfig,
)
from spaces.services import SpacePermissionService

MAX_MESSAGES_PER_JOB = 1000
LEGACY_OVERSIZE_ERROR = "Message exceeds the model input budget."


def _retryable_partials():
    readable = (
        AnalysisJobMessage.objects.filter(
            job_id=OuterRef("pk"),
            completed_at__isnull=True,
            message__orphaned_at__isnull=True,
            error__in=("", LEGACY_OVERSIZE_ERROR),
        )
        .annotate(
            readable=Exists(readable_text_parts(OuterRef("message_id"))),
        )
        .filter(readable=True)
    )
    return (
        AnalysisJob.objects.filter(
            state=AnalysisJob.State.PARTIAL,
        )
        .annotate(retryable=Exists(readable))
        .filter(retryable=True)
        .exclude(
            disallowed_conversation_q(
                "conversation__kind",
                "specification__chat_analysis_preferences",
            ),
        )
    )


def ensure_due_run(now, schedule=None):
    if schedule is None:
        schedule = getattr(
            settings, "CHAT_ANALYSIS_SCHEDULE", DEFAULT_SCHEDULE
        )
    slot = due_slot(now, schedule)
    if slot is None:
        return None
    run = ScheduledAnalysisRun.objects.get_or_create(
        slot=slot, defaults={"boundary": slot_boundary(slot)}
    )[0]
    run.boundary = run.boundary.astimezone(UTC)
    return run


def dispatch_due_analysis(now=None, schedule=None):
    """Open an hourly round for users with an eligible uploaded backlog.

    The slot controls admission. Actual input is selected when the worker
    starts, including uploads received while this user was waiting.
    Continuations do not wait for a new hourly slot.
    """
    now = now or timezone.now()
    run = ensure_due_run(now, schedule)
    if run is None:
        return {"jobs": 0}
    jobs = 0
    pending = _pending_origins(run.boundary)
    busy = AnalysisJob.objects.filter(
        state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
    ).values("created_by_id")
    limit = max(1, settings.CHAT_ANALYSIS_DISPATCH_LIMIT)
    users = list(
        pending.exclude(upload_item__batch__uploaded_by_id__in=busy)
        .order_by("upload_item__batch__uploaded_by_id")
        .values_list("upload_item__batch__uploaded_by_id", flat=True)
        .distinct()[:limit]
    )
    partial_users = (
        _retryable_partials()
        .exclude(created_by_id__in=busy)
        .exclude(
            created_by_id__in=users,
        )
        .order_by("created_by_id")
        .values_list(
            "created_by_id",
            flat=True,
        )
        .distinct()[: max(0, limit - len(users))]
    )
    for user_id in users + list(partial_users):
        try:
            jobs += int(schedule_user(user_id, run.boundary) is not None)
        except ChatAnalysisPermissionError:
            continue
    return {"jobs": jobs, "slot": run.slot}


def _pending_origins(boundary, user_id=None):
    excluded = (
        SpaceWorkflowConfig.objects.filter(
            space_id=OuterRef("message__conversation__space_id"),
        )
        .annotate(
            chat_kind=Cast(
                OuterRef("message__conversation__kind"),
                CharField(),
            ),
        )
        .filter(
            disallowed_conversation_q(
                "chat_kind", "chat_analysis_preferences"
            ),
        )
    )
    membership = SpaceMembership.objects.filter(
        space_id=OuterRef("message__conversation__space_id"),
        user_id=OuterRef("upload_item__batch__uploaded_by_id"),
        status=SpaceMembership.Status.ACTIVE,
        role__in=SpacePermissionService.WRITE_ROLES,
    )
    takeover = SpaceTakeover.objects.filter(
        space_id=OuterRef("message__conversation__space_id"),
        admin_id=OuterRef("upload_item__batch__uploaded_by_id"),
        admin__is_staff=True,
        active=True,
    )
    analyzed = NoteEvidence.objects.filter(
        message_id=OuterRef("message_id"),
        note__analysis_job__state=AnalysisJob.State.READY,
        note__analysis_job__conversation_id=OuterRef(
            "message__conversation_id"
        ),
    )
    origins = (
        MessageOrigin.objects.filter(
            created_at__lte=boundary,
            upload_item__batch__status=UploadBatch.Status.COMPLETED,
            upload_item__batch__completed_at__lte=boundary,
            message__created_at__lte=boundary,
            message__orphaned_at__isnull=True,
            message__scheduled_analysis__isnull=True,
            message__conversation__space__status=Space.Status.ACTIVE,
            upload_item__batch__space_id=F("message__conversation__space_id"),
        )
        .annotate(
            analyzed=Exists(analyzed),
            writable=Exists(membership),
            takeover=Exists(takeover),
            readable=Exists(readable_text_parts(OuterRef("message_id"))),
            excluded=Exists(excluded),
        )
        .filter(analyzed=False, readable=True, excluded=False)
        .filter(Q(writable=True) | Q(takeover=True))
    )
    if user_id is not None:
        origins = origins.filter(upload_item__batch__uploaded_by_id=user_id)
    return origins


def schedule_user(user_id, boundary, *, dispatch=True, pending_before=None):
    """Queue a user wakeup; freeze its messages only when execution starts."""
    from chat_analysis.tasks import dispatch_analysis_job

    with dispatch_lock():
        if AnalysisJob.objects.filter(
            created_by_id=user_id,
            state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
        ).exists():
            return None
        partial = (
            _retryable_partials()
            .filter(created_by_id=user_id)
            .order_by("updated_at")
            .first()
        )
        origin = (
            _pending_origins(pending_before or boundary, user_id)
            .select_related(
                "message__conversation__space",
                "upload_item__batch__uploaded_by",
            )
            .order_by("created_at", "pk")
            .first()
        )
        if partial and (
            origin is None or partial.updated_at <= origin.created_at
        ):
            return schedule_conversation(
                partial.conversation_id,
                boundary,
                user_id=user_id,
                dispatch=dispatch,
            )
        if origin is None:
            return None
        conversation = origin.message.conversation
        job = create_analysis_job(
            actor=origin.upload_item.batch.uploaded_by,
            space=conversation.space,
            conversation=conversation,
            request_key=f"scheduled:{uuid.uuid4()}",
            start_seq=0,
            end_seq=0,
            input_version="scheduled.v1",
            specification={
                "scheduled_message_scope": True,
                "snapshot_pending": True,
                "boundary": boundary.isoformat(),
                **(
                    {"input_boundary": pending_before.isoformat()}
                    if pending_before is not None
                    else {}
                ),
            },
        )
        if dispatch:
            transaction.on_commit(lambda: dispatch_analysis_job(job))
        return job


def freeze_scheduled_input(job):
    """Select the user's latest eligible input after obtaining execution."""
    from chat_analysis.execution import _ensure_lease

    with dispatch_lock():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, job.lease_owner, job.fencing_token)
        if not locked.specification.get("snapshot_pending"):
            return locked
        boundary = (
            datetime.fromisoformat(locked.specification["input_boundary"])
            if locked.specification.get("input_boundary")
            else timezone.now()
        )
        origin = (
            _pending_origins(boundary, job.created_by_id)
            .order_by("created_at", "pk")
            .first()
        )
        if origin is not None:
            locked = (
                schedule_conversation(
                    origin.message.conversation_id,
                    boundary,
                    user_id=job.created_by_id,
                    dispatch=False,
                    existing_job=locked,
                )
                or locked
            )
        locked.specification = {
            **locked.specification,
            "snapshot_pending": False,
            "input_boundary": boundary.isoformat(),
        }
        _ensure_lease(locked, job.lease_owner, job.fencing_token)
        locked.save(update_fields=("specification", "updated_at"))
        return locked


def schedule_conversation(
    conversation_id,
    boundary,
    *,
    user_id=None,
    dispatch=True,
    existing_job=None,
):
    """Reserve a finite window at the caller's cutoff."""
    from chat_analysis.tasks import dispatch_analysis_job

    with dispatch_lock():
        conversation = (
            Conversation.objects.select_for_update()
            .select_related("space")
            .get(pk=conversation_id)
        )
        if existing_job is not None:
            ensure_can_contribute(existing_job.created_by, conversation.space)
        if (
            existing_job is None
            and AnalysisJob.objects.filter(
                conversation=conversation,
                state__in=(
                    AnalysisJob.State.QUEUED,
                    AnalysisJob.State.RUNNING,
                ),
            ).exists()
        ):
            return None
        partials = _retryable_partials().filter(
            conversation=conversation,
        )
        if existing_job is not None:
            partials = partials.none()
        if user_id is not None:
            partials = partials.filter(created_by_id=user_id)
        retryable = []
        for partial in partials:
            unfinished = (
                partial.scheduled_messages.filter(completed_at__isnull=True)
                .annotate(
                    readable=Exists(
                        readable_text_parts(OuterRef("message_id"))
                    ),
                )
                .filter(readable=True)
            )
            skipped = unfinished.filter(error=LEGACY_OVERSIZE_ERROR)
            legacy_skip = skipped.exists()
            if legacy_skip:
                skipped.update(error="")
                partial.attempts = 0
            first_seq = (
                unfinished.filter(error="")
                .order_by("message__ingest_seq")
                .values_list("message__ingest_seq", flat=True)
                .first()
            )
            if first_seq is not None:
                # Rewind gaps without replaying completed assignments.
                partial.checkpoint = {
                    **partial.checkpoint,
                    "partial": False,
                    "last_ingest_seq": min(
                        partial.checkpoint.get(
                            "last_ingest_seq",
                            partial.start_seq,
                        ),
                        first_seq - 1,
                    ),
                }
                partial.save(
                    update_fields=(
                        "checkpoint",
                        "attempts",
                        "updated_at",
                    )
                )
                retryable.append(partial)
        if retryable:
            for partial in retryable[:1]:
                partial.state = AnalysisJob.State.QUEUED
                partial.lease_owner = ""
                partial.lease_until = None
                partial.error = ""
                partial.save(
                    update_fields=(
                        "state",
                        "lease_owner",
                        "lease_until",
                        "error",
                        "updated_at",
                    )
                )
                resumed = partial
                if dispatch:
                    transaction.on_commit(
                        lambda job=resumed: dispatch_analysis_job(job)
                    )
            return retryable[0]
        eligible_origins = MessageOrigin.objects.filter(
            message_id=OuterRef("pk"),
            created_at__lte=boundary,
            upload_item__batch__space_id=conversation.space_id,
            upload_item__batch__status=UploadBatch.Status.COMPLETED,
            upload_item__batch__completed_at__lte=boundary,
        )
        if user_id is not None:
            eligible_origins = eligible_origins.filter(
                upload_item__batch__uploaded_by_id=user_id,
            )
        analyzed_evidence = NoteEvidence.objects.filter(
            message_id=OuterRef("pk"),
            note__space_id=conversation.space_id,
            note__analysis_job__conversation_id=conversation.pk,
            note__analysis_job__state=AnalysisJob.State.READY,
        )
        messages = list(
            Message.objects.filter(
                conversation=conversation,
                orphaned_at__isnull=True,
                scheduled_analysis__isnull=True,
                created_at__lte=boundary,
            )
            .annotate(
                eligible=Exists(eligible_origins),
                already_analyzed=Exists(analyzed_evidence),
                readable=Exists(readable_text_parts(OuterRef("pk"))),
            )
            .filter(eligible=True, already_analyzed=False, readable=True)
            .order_by("ingest_seq", "pk")[
                : min(
                    MAX_MESSAGES_PER_JOB,
                    max(
                        1,
                        settings.CHAT_ANALYSIS_BATCH_MESSAGES,
                    ),
                )
            ]
        )
        if not messages:
            return None
        batches = UploadBatch.objects.filter(
            space=conversation.space,
            status=UploadBatch.Status.COMPLETED,
            completed_at__lte=boundary,
            items__chat_message_origins__message=messages[0],
            items__chat_message_origins__created_at__lte=boundary,
        )
        if user_id is not None:
            batches = batches.filter(uploaded_by_id=user_id)
        batch = (
            batches.select_related("uploaded_by")
            .order_by("completed_at", "pk")
            .first()
        )
        if batch is None:
            return None
        if (
            existing_job is None
            and user_id is not None
            and AnalysisJob.objects.filter(
                created_by=batch.uploaded_by,
                state__in=(
                    AnalysisJob.State.QUEUED,
                    AnalysisJob.State.RUNNING,
                ),
            ).exists()
        ):
            return None
        job = existing_job or create_analysis_job(
            actor=batch.uploaded_by,
            space=conversation.space,
            conversation=conversation,
            request_key=f"scheduled:{uuid.uuid4()}",
            start_seq=messages[0].ingest_seq - 1,
            end_seq=messages[-1].ingest_seq,
            input_version="scheduled.v1",
            specification={
                "scheduled_message_scope": True,
                "boundary": boundary.isoformat(),
            },
        )
        if existing_job is not None:
            job.space = conversation.space
            job.conversation = conversation
            job.start_seq = messages[0].ingest_seq - 1
            job.end_seq = messages[-1].ingest_seq
            job.specification = {
                **job.specification,
                "chat_analysis_preferences": get_analysis_preferences(
                    conversation.space,
                ),
                "analysis_conversation_kind": conversation.kind,
            }
            job.save(
                update_fields=(
                    "space",
                    "conversation",
                    "start_seq",
                    "end_seq",
                    "specification",
                    "updated_at",
                )
            )
        AnalysisJobMessage.objects.bulk_create(
            [
                AnalysisJobMessage(job=job, message=message)
                for message in messages
            ]
        )
        job.upload_batches.set(
            UploadBatch.objects.filter(
                space=conversation.space,
                status=UploadBatch.Status.COMPLETED,
                completed_at__lte=boundary,
                items__chat_message_origins__message__in=messages,
                items__chat_message_origins__created_at__lte=boundary,
            ).distinct()
        )
        if dispatch:
            transaction.on_commit(lambda: dispatch_analysis_job(job))
        return job
