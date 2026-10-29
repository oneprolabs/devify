"""Celery entry points for analysis job execution."""

from celery import shared_task

from chat_analysis.execution import execute_analysis_job


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
