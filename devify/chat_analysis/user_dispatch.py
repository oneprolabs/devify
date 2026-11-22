"""Bound broker deliveries by user, reusing each job's lease and fence."""

import logging
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from chat_analysis.models import AnalysisExecutionSlot, AnalysisJob

logger = logging.getLogger(__name__)
ACTIVE_STATES = (AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING)


@contextmanager
def dispatch_lock():
    """Serialize admission only; never keep this lock during model calls."""
    with transaction.atomic():
        AnalysisExecutionSlot.objects.get_or_create(pk=0)
        AnalysisExecutionSlot.objects.select_for_update().get(pk=0)
        yield


def _release_finished_slots():
    slots = AnalysisExecutionSlot.objects.exclude(pk=0)
    slots.filter(
        Q(job__isnull=True)
        | ~Q(job__state__in=ACTIVE_STATES)
        | Q(
            job__state=AnalysisJob.State.QUEUED,
            job__updated_at__gt=F("dispatched_at"),
        )
    ).update(user=None, job=None, dispatched_at=None)


def reserve_user_slot(job):
    """Reserve under dispatch_lock, including calls bypassing Celery."""
    _release_finished_slots()
    occupied = AnalysisExecutionSlot.objects.filter(user_id=job.created_by_id)
    slot = occupied.first()
    if slot:
        return slot if slot.job_id == job.pk else None
    limit = max(1, settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS)
    if (
        AnalysisExecutionSlot.objects.filter(job__isnull=False).count()
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


def dispatch_pending_analysis(*, retry_job_id=None):
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
            job = (
                AnalysisJob.objects.filter(state=AnalysisJob.State.QUEUED)
                .filter(Q(error="") | Q(pk=retry_job_id))
                .exclude(created_by_id__in=users)
                .order_by("updated_at", "pk")
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
