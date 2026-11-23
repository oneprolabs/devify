"""Bound broker deliveries by user, reusing each job's lease and fence."""

import logging
from contextlib import contextmanager
from datetime import UTC, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from chat_analysis.models import AnalysisExecutionSlot, AnalysisJob

logger = logging.getLogger(__name__)
ACTIVE_STATES = (AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING)
PUBLICATION_LEASE_SECONDS = 300


def next_analysis_hour():
    return (
        timezone.now()
        .astimezone(UTC)
        .replace(minute=0, second=0, microsecond=0)
        + timedelta(hours=1)
    ).isoformat()


def resume_is_due(job):
    value = job.checkpoint.get("resume_after")
    return not value or parse_datetime(value) <= timezone.now()


@contextmanager
def dispatch_lock():
    """Serialize admission only; never keep this lock during model calls."""
    with transaction.atomic():
        lock_dispatch_row()
        yield


def lock_dispatch_row():
    """Use the same admission lock inside an existing short transaction."""
    AnalysisExecutionSlot.objects.get_or_create(pk=0)
    AnalysisExecutionSlot.objects.select_for_update().get(pk=0)


def _release_finished_slots():
    slots = AnalysisExecutionSlot.objects.exclude(pk=0)
    publication_cutoff = timezone.now() - timedelta(
        seconds=PUBLICATION_LEASE_SECONDS,
    )
    slots.filter(
        Q(job__isnull=True)
        | (~Q(job__state__in=ACTIVE_STATES) & Q(publishing=False))
        | Q(publishing=True, dispatched_at__lt=publication_cutoff)
        | Q(
            job__state=AnalysisJob.State.QUEUED,
            job__updated_at__gt=F("dispatched_at"),
        )
    ).update(user=None, job=None, dispatched_at=None, publishing=False)


def reserve_user_slot(job):
    """Reserve under dispatch_lock, including calls bypassing Celery."""
    _release_finished_slots()
    legacy_running = AnalysisJob.objects.filter(
        state=AnalysisJob.State.RUNNING,
        analysisexecutionslot__isnull=True,
    ).exclude(pk=job.pk)
    if legacy_running.filter(created_by_id=job.created_by_id).exists():
        return None
    occupied = AnalysisExecutionSlot.objects.filter(user_id=job.created_by_id)
    slot = occupied.first()
    if slot:
        return slot if slot.job_id == job.pk else None
    limit = max(1, settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS)
    if (
        AnalysisExecutionSlot.objects.filter(job__isnull=False).count()
        + legacy_running.count()
        >= limit
    ):
        return None
    for number in range(1, limit + 1):
        slot, _ = AnalysisExecutionSlot.objects.get_or_create(pk=number)
        if slot.job_id is None:
            slot.user_id = job.created_by_id
            slot.job = job
            slot.dispatched_at = timezone.now()
            slot.save(update_fields=("user", "job", "dispatched_at"))
            return slot
    return None


def claim_publication_slot(job_id):
    """Count final event reduction against the same user/model capacity."""
    with dispatch_lock():
        _release_finished_slots()
        job = AnalysisJob.objects.select_for_update().get(pk=job_id)
        if job.state != AnalysisJob.State.READY or not resume_is_due(job):
            return None
        if AnalysisExecutionSlot.objects.filter(
            user_id=job.created_by_id,
        ).exists():
            return None
        slot = reserve_user_slot(job)
        if slot is None:
            return None
        slot.publishing = True
        slot.save(update_fields=("publishing",))
        job.fencing_token += 1
        job.checkpoint = dict(job.checkpoint)
        job.checkpoint.pop("resume_after", None)
        job.save(update_fields=("fencing_token", "checkpoint"))
        return job


def publication_slot_valid(job):
    return AnalysisExecutionSlot.objects.filter(
        job_id=job.pk,
        job__fencing_token=job.fencing_token,
        publishing=True,
        dispatched_at__gt=timezone.now()
        - timedelta(
            seconds=PUBLICATION_LEASE_SECONDS,
        ),
    ).exists()


def release_publication_slot(job):
    with dispatch_lock():
        AnalysisExecutionSlot.objects.filter(
            job_id=job.pk,
            job__fencing_token=job.fencing_token,
        ).update(user=None, job=None, dispatched_at=None, publishing=False)


def renew_publication_slot(job):
    """Renew only a still-valid publication owner, under dispatch_lock."""
    if not publication_slot_valid(job):
        return False
    return bool(
        AnalysisExecutionSlot.objects.filter(
            job_id=job.pk,
            job__fencing_token=job.fencing_token,
            publishing=True,
        ).update(dispatched_at=timezone.now())
    )


def _deliver(job_id, dispatched_at):
    from chat_analysis.tasks import execute_analysis_job_task

    if not AnalysisExecutionSlot.objects.filter(
        job_id=job_id,
        dispatched_at=dispatched_at,
        job__state=AnalysisJob.State.QUEUED,
    ).exists():
        return
    try:
        execute_analysis_job_task.delay(job_id)
    except Exception:
        AnalysisExecutionSlot.objects.filter(
            job_id=job_id,
            dispatched_at=dispatched_at,
        ).update(dispatched_at=None)
        logger.exception("Failed to dispatch analysis job %s", job_id)


def _enqueue(slot):
    slot.dispatched_at = timezone.now()
    slot.save(update_fields=("dispatched_at",))
    transaction.on_commit(lambda: _deliver(slot.job_id, slot.dispatched_at))


def dispatch_pending_analysis():
    """Keep at most one delivery per user and a fixed global upper bound.

    Other queued conversation jobs are durable pending work, not broker
    deliveries. A yielded job moves behind users already waiting.
    """
    dispatched = 0
    with dispatch_lock():
        _release_finished_slots()
        cutoff = timezone.now() - timedelta(
            seconds=getattr(
                settings, "CHAT_ANALYSIS_QUEUED_STALE_SECONDS", 600
            )
        )
        dropped = AnalysisExecutionSlot.objects.filter(
            job__state=AnalysisJob.State.QUEUED,
        ).filter(Q(dispatched_at__isnull=True) | Q(dispatched_at__lt=cutoff))
        for slot in dropped:
            _enqueue(slot)
            dispatched += 1
        limit = max(1, settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS)
        while (
            AnalysisExecutionSlot.objects.filter(job__isnull=False).count()
            < limit
        ):
            users = AnalysisExecutionSlot.objects.filter(
                user__isnull=False
            ).values("user_id")
            running_users = AnalysisJob.objects.filter(
                state=AnalysisJob.State.RUNNING,
            ).values("created_by_id")
            last_work = (
                AnalysisJob.objects.filter(
                    created_by_id=OuterRef("created_by_id"),
                    fencing_token__gt=0,
                )
                .order_by("-updated_at")
                .values("updated_at")[:1]
            )
            now = timezone.now().isoformat()
            job = (
                AnalysisJob.objects.filter(state=AnalysisJob.State.QUEUED)
                .filter(
                    Q(checkpoint__resume_after__isnull=True)
                    | Q(checkpoint__resume_after__lte=now)
                )
                .exclude(created_by_id__in=users)
                .exclude(created_by_id__in=running_users)
                .annotate(last_work=Subquery(last_work))
                .order_by(
                    F("last_work").asc(nulls_first=True), "updated_at", "pk"
                )
                .first()
            )
            if job is None:
                break
            slot = reserve_user_slot(job)
            if slot is None:
                break
            _enqueue(slot)
            dispatched += 1
    return dispatched
