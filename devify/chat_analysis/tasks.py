"""Celery entry points for analysis job execution."""

from datetime import datetime
from time import monotonic

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from chat_analysis.execution import (
    execute_analysis_job,
    publish_ready_event_batches,
)
from chat_analysis.models import AnalysisJob
from chat_analysis.summaries.tasks import generate_chat_summary  # noqa: F401
from chat_analysis.task_status import (
    recover_expired_analysis_jobs,
    sweep_stale_tasks,
)
from chat_analysis.topic_scheduler import run_due_topic_reports
from chat_analysis.user_dispatch import dispatch_pending_analysis


@shared_task(bind=True, max_retries=0)
def execute_analysis_job_task(self, job_id, worker_id=None):
    """Consume one bounded user batch without chaining new Celery tasks."""
    from chat_analysis.scheduled_dispatch import schedule_user

    worker = worker_id or f"celery:{self.request.id or 'local'}"
    started = monotonic()
    input_boundary = timezone.now()
    remaining = max(1, settings.CHAT_ANALYSIS_BATCH_MESSAGES)
    seconds = max(1, settings.CHAT_ANALYSIS_BATCH_SECONDS)
    current_id, first_result = job_id, None
    try:
        while remaining > 0:
            before = (
                AnalysisJob.objects.filter(pk=current_id)
                .values_list(
                    "checkpoint",
                    flat=True,
                )
                .first()
                or {}
            )
            result = execute_analysis_job(
                current_id,
                worker_id=worker,
                message_limit=remaining,
                time_limit=max(1, seconds - (monotonic() - started)),
            )
            if result is None:
                break
            if first_result is None:
                first_result = result
                frozen_at = result.job.specification.get("input_boundary")
                if frozen_at:
                    input_boundary = datetime.fromisoformat(frozen_at)
            processed = result.job.checkpoint.get("messages_processed", 0)
            remaining -= max(
                0, processed - before.get("messages_processed", 0)
            )
            boundary = result.job.specification.get("boundary")
            if (
                result.job.state != AnalysisJob.State.READY
                or not boundary
                or remaining <= 0
                or monotonic() - started >= seconds
            ):
                break
            following = schedule_user(
                result.job.created_by_id,
                datetime.fromisoformat(boundary),
                dispatch=False,
                pending_before=input_boundary,
            )
            if following is None:
                break
            current_id = following.pk
        if first_result is None:
            return {"job_id": job_id, "claimed": False}
        if first_result.job.specification.get("boundary"):
            publish_ready_event_batches()
        return {
            "job_id": job_id,
            "state": first_result.job.state,
            "claimed": True,
        }
    finally:
        # Feed already-admitted users; deferred retries stay gated until due.
        dispatch_pending_analysis()


def dispatch_analysis_job(job):
    """Queue the job on the existing chat_analysis worker."""
    return dispatch_pending_analysis()


@shared_task(bind=True, max_retries=0)
def run_due_topic_reports_task(self):
    """Create reports for topic subscriptions whose time has arrived."""
    return run_due_topic_reports()


@shared_task(bind=True, max_retries=0)
def run_due_scheduled_analysis_task(self):
    """Enqueue due conversations onto the existing analysis worker.

    Beat checks the Beijing schedule. Each job is
    ``execute_analysis_job_task``, which production routes to the
    ``chat_analysis`` queue consumed by ``devify-analysis-worker``.
    """
    from chat_analysis.scheduled_dispatch import dispatch_due_analysis

    recover_expired_analysis_jobs()
    result = dispatch_due_analysis()
    publish_ready_event_batches()
    dispatch_pending_analysis()
    return result


@shared_task(bind=True, max_retries=0)
def sweep_stale_async_tasks(self):
    """Keep summary/question/report deadlines independent of events."""
    result = sweep_stale_tasks(include_analysis=False)
    result.pop("requeued_job_ids", None)
    return result
