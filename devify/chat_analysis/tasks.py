"""Celery entry points for analysis job execution."""

import logging

from celery import shared_task

from chat_analysis.execution import execute_analysis_job
from chat_analysis.task_status import sweep_stale_tasks
from chat_analysis.topic_scheduler import run_due_topic_reports

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def execute_analysis_job_task(self, job_id, worker_id=None):
    """Run one analysis job; retries are handled by the job state machine."""
    worker = worker_id or f"celery:{self.request.id or 'local'}"
    result = execute_analysis_job(job_id, worker_id=worker)
    if result is None:
        return {"job_id": job_id, "claimed": False}
    return {
        "job_id": result.job.pk,
        "state": result.job.state,
        "claimed": True,
    }


def dispatch_analysis_job(job):
    """Queue the job without blocking the request."""
    return execute_analysis_job_task.delay(job.pk)


@shared_task(bind=True, max_retries=0)
def run_due_topic_reports_task(self):
    """Create reports for topic subscriptions whose time has arrived."""
    return run_due_topic_reports()


@shared_task(bind=True, max_retries=0)
def sweep_stale_async_tasks(self):
    """Close questions, reports and jobs that no worker finished."""
    result = sweep_stale_tasks()
    for job_id in result.pop("requeued_job_ids", []):
        try:
            execute_analysis_job_task.delay(job_id)
        except Exception:
            logger.exception(
                "Failed to re-dispatch recovered analysis job %s", job_id
            )
    return result
