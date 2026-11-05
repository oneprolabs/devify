"""Shared terminal-state semantics for chat analysis async work.

Analysis jobs, questions and reports are executed by separate Celery tasks
but share one failure contract: a record that is still ``queued``/``running``
after its deadline is moved to a terminal state with a machine-readable
reason, so clients can stop polling instead of waiting forever.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from chat_analysis.execution import DEFAULT_MAX_ATTEMPTS
from chat_analysis.models import AnalysisJob, QuestionAnswer, Report

logger = logging.getLogger(__name__)

DEFAULT_QUESTION_TIMEOUT_SECONDS = 900
DEFAULT_REPORT_TIMEOUT_SECONDS = 1800
# A job that has been sitting in ``queued`` this long was probably never
# dispatched: a retryable failure moves the job back to ``queued`` and depends
# on the scheduler to run it again.
DEFAULT_QUEUED_ANALYSIS_STALE_SECONDS = 600

QUESTION_TERMINAL_STATUSES = frozenset(
    {QuestionAnswer.Status.READY, QuestionAnswer.Status.FAILED}
)
REPORT_TERMINAL_STATUSES = frozenset(
    {
        Report.Status.READY,
        Report.Status.PARTIAL,
        Report.Status.FAILED,
    }
)
ANALYSIS_TERMINAL_STATES = frozenset(
    {
        AnalysisJob.State.READY,
        AnalysisJob.State.PARTIAL,
        AnalysisJob.State.FAILED,
        AnalysisJob.State.CANCELLED,
    }
)


def question_timeout_seconds():
    return getattr(
        settings,
        "CHAT_ANALYSIS_QUESTION_TIMEOUT_SECONDS",
        DEFAULT_QUESTION_TIMEOUT_SECONDS,
    )


def report_timeout_seconds():
    return getattr(
        settings,
        "CHAT_ANALYSIS_REPORT_TIMEOUT_SECONDS",
        DEFAULT_REPORT_TIMEOUT_SECONDS,
    )


def is_terminal_question(question):
    return question.status in QUESTION_TERMINAL_STATUSES


def is_terminal_report(report):
    return report.status in REPORT_TERMINAL_STATUSES


def is_terminal_analysis_job(job):
    return job.state in ANALYSIS_TERMINAL_STATES


def expire_stale_questions(*, now=None, timeout_seconds=None):
    """Fail questions that no worker picked up before the deadline."""

    now = now or timezone.now()
    timeout_seconds = (
        question_timeout_seconds()
        if timeout_seconds is None
        else timeout_seconds
    )
    cutoff = now - timedelta(seconds=timeout_seconds)
    stale = QuestionAnswer.objects.filter(
        status=QuestionAnswer.Status.QUEUED,
        updated_at__lt=cutoff,
    )
    expired = 0
    for question in stale:
        question.status = QuestionAnswer.Status.FAILED
        question.error = (
            f"timeout: no worker result within {timeout_seconds} seconds."
        )
        question.save(update_fields=("status", "error", "updated_at"))
        expired += 1
    return expired


def expire_stale_reports(*, now=None, timeout_seconds=None):
    """Fail or partially fail reports a worker never finished.

    A report that already has a readable body keeps it and becomes
    ``partial``; an empty report becomes ``failed``. Neither outcome touches
    the stored sections, so an earlier snapshot stays readable.
    """

    now = now or timezone.now()
    timeout_seconds = (
        report_timeout_seconds()
        if timeout_seconds is None
        else timeout_seconds
    )
    cutoff = now - timedelta(seconds=timeout_seconds)
    stale = Report.objects.filter(
        status=Report.Status.QUEUED,
        updated_at__lt=cutoff,
    )
    expired = 0
    for report in stale:
        processing = dict(report.processing or {})
        if processing.get("generator") in {"llm_pending", "llm"}:
            processing["generator"] = "llm_timeout"
        processing["error"] = (
            f"timeout: no worker result within {timeout_seconds} seconds."
        )
        report.processing = processing
        report.status = (
            Report.Status.PARTIAL if report.body else Report.Status.FAILED
        )
        report.save(update_fields=("status", "processing", "updated_at"))
        expired += 1
    return expired


def queued_analysis_stale_seconds():
    return getattr(
        settings,
        "CHAT_ANALYSIS_QUEUED_STALE_SECONDS",
        DEFAULT_QUEUED_ANALYSIS_STALE_SECONDS,
    )


def recover_stale_queued_analysis_jobs(*, now=None, stale_seconds=None):
    """Re-dispatch jobs that were queued but never picked up.

    ``fail_analysis_job`` moves a retryable failure back to ``queued`` and
    expects another delivery. When that delivery never happens the job would
    stay queued forever, so the sweep treats a long-queued job as dropped and
    dispatches it again. Claiming is exclusive (row lock plus fencing token),
    so a duplicate delivery is harmless.
    """

    now = now or timezone.now()
    stale_seconds = (
        queued_analysis_stale_seconds()
        if stale_seconds is None
        else stale_seconds
    )
    cutoff = now - timedelta(seconds=stale_seconds)
    stale = AnalysisJob.objects.filter(
        state=AnalysisJob.State.QUEUED,
        lease_until__isnull=True,
        updated_at__lt=cutoff,
    )
    requeued_ids = list(stale.values_list("pk", flat=True))
    return {"requeued": len(requeued_ids), "requeued_job_ids": requeued_ids}


def recover_expired_analysis_jobs(
    *, now=None, max_attempts=DEFAULT_MAX_ATTEMPTS
):
    """Requeue jobs whose worker disappeared with the lease still held.

    The lease deadline is the per-attempt timeout: a live worker renews it
    after every chunk. Requeued jobs keep their checkpoint, so the next claim
    resumes instead of restarting.
    """

    now = now or timezone.now()
    stale = AnalysisJob.objects.filter(
        state=AnalysisJob.State.RUNNING,
        lease_until__lt=now,
    )
    requeued = 0
    failed = 0
    requeued_ids = []
    for job in stale:
        job.lease_owner = ""
        job.lease_until = None
        if job.attempts < max_attempts:
            job.state = AnalysisJob.State.QUEUED
            job.error = "lease_expired: requeued after worker timeout."
            requeued += 1
            requeued_ids.append(job.pk)
        else:
            job.state = AnalysisJob.State.FAILED
            job.error = (
                "lease_expired: max attempts reached "
                f"({job.attempts}/{max_attempts})."
            )
            failed += 1
        job.save(
            update_fields=(
                "state",
                "error",
                "lease_owner",
                "lease_until",
                "updated_at",
            )
        )
    return {
        "requeued": requeued,
        "failed": failed,
        "requeued_job_ids": requeued_ids,
    }


def sweep_stale_tasks(*, now=None):
    """Move every abandoned async record into a terminal state."""

    jobs = recover_expired_analysis_jobs(now=now)
    queued = recover_stale_queued_analysis_jobs(now=now)
    counts = {
        "questions_failed": expire_stale_questions(now=now),
        "reports_expired": expire_stale_reports(now=now),
        "jobs_requeued": jobs["requeued"] + queued["requeued"],
        "jobs_failed": jobs["failed"],
        "requeued_job_ids": jobs["requeued_job_ids"]
        + queued["requeued_job_ids"],
    }
    if any(
        counts[key]
        for key in (
            "questions_failed",
            "reports_expired",
            "jobs_requeued",
            "jobs_failed",
        )
    ):
        logger.warning("chat analysis stale task sweep: %s", counts)
    return counts
