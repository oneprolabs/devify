"""Celery entry points for analysis job execution."""

import logging
from datetime import datetime

from celery import shared_task
from django.utils import timezone

from chat_analysis.execution import (
    execute_analysis_job,
    publish_ready_event_batches,
)
from chat_analysis.models import AnalysisJob
from chat_analysis.summaries.tasks import generate_chat_summary  # noqa: F401
from chat_analysis.task_status import sweep_stale_tasks
from chat_analysis.topic_scheduler import run_due_topic_reports
from chat_analysis.user_dispatch import dispatch_pending_analysis

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def execute_analysis_job_task(self, job_id, worker_id=None):
    """Run one analysis job; retries are handled by the job state machine."""
    worker = worker_id or f"celery:{self.request.id or 'local'}"
    result = execute_analysis_job(job_id, worker_id=worker)
    if result is None:
        return {"job_id": job_id, "claimed": False}
    if (
        result.job.state == AnalysisJob.State.READY
        and result.job.specification.get("boundary")
    ):
        from chat_analysis.scheduled_dispatch import schedule_user

        schedule_user(
            result.job.created_by_id,
            datetime.fromisoformat(result.job.specification["boundary"]),
            dispatch=False,
            pending_before=timezone.now(),
        )
    if result.job.specification.get("boundary") and result.job.state in (
        AnalysisJob.State.READY,
        AnalysisJob.State.PARTIAL,
        AnalysisJob.State.FAILED,
    ):
        publish_ready_event_batches()
    dispatch_pending_analysis()
    return {
        "job_id": result.job.pk,
        "state": result.job.state,
        "claimed": True,
    }


def dispatch_analysis_job(job):
    """Queue the job on the existing chat_analysis worker."""
    return dispatch_pending_analysis(retry_job_id=job.pk)


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

    result = dispatch_due_analysis()
    publish_ready_event_batches()
    dispatch_pending_analysis()
    return result


@shared_task(bind=True, max_retries=0)
def sweep_stale_async_tasks(self):
    """Close questions, reports and jobs that no worker finished."""
    result = sweep_stale_tasks()
    for job_id in result.pop("requeued_job_ids", []):
        try:
            dispatch_analysis_job(AnalysisJob.objects.get(pk=job_id))
        except Exception:
            logger.exception(
                "Failed to re-dispatch recovered analysis job %s", job_id
            )
    dispatch_pending_analysis()
    return result
