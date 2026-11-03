from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis.models import AnalysisJob, QuestionAnswer, Report
from chat_analysis.services import create_analysis_job
from chat_analysis.task_status import (
    expire_stale_questions,
    expire_stale_reports,
    recover_expired_analysis_jobs,
    sweep_stale_tasks,
)
from chat_analysis.tasks import sweep_stale_async_tasks
from chat_domain.models import Conversation
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug="task-status-team"):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def make_question(owner, space, key="question"):
    return QuestionAnswer.objects.create(
        space=space,
        created_by=owner,
        question=key,
        status=QuestionAnswer.Status.QUEUED,
    )


def make_report(owner, space, *, body="", key="report"):
    return Report.objects.create(
        space=space,
        created_by=owner,
        request_key=key,
        title=key,
        status=Report.Status.QUEUED,
        body=body,
        processing={"generator": "llm_pending"},
    )


def make_job(owner, space, key="job"):
    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="local-account",
        source_conversation_id=key,
        identity_key=f"wechat:local-account:{key}",
        title=key,
    )
    return create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key=key,
        start_seq=0,
        end_seq=3,
        input_version="wechat.v1",
    )


def age(instance, seconds):
    stamp = timezone.now() - timedelta(seconds=seconds)
    type(instance).objects.filter(pk=instance.pk).update(updated_at=stamp)


def test_stale_queued_question_fails_with_timeout_reason():
    owner = User.objects.create_user(username="task-status-question")
    space = make_space(owner)
    stale = make_question(owner, space, "stale")
    fresh = make_question(owner, space, "fresh")
    age(stale, 3600)

    assert expire_stale_questions(timeout_seconds=900) == 1

    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert stale.status == QuestionAnswer.Status.FAILED
    assert stale.error.startswith("timeout:")
    assert fresh.status == QuestionAnswer.Status.QUEUED


def test_stale_report_keeps_readable_body_as_partial():
    owner = User.objects.create_user(username="task-status-report")
    space = make_space(owner)
    empty = make_report(owner, space, key="empty")
    partial = make_report(owner, space, body="# Snapshot", key="partial")
    fresh = make_report(owner, space, key="fresh")
    age(empty, 3600)
    age(partial, 3600)

    assert expire_stale_reports(timeout_seconds=1800) == 2

    empty.refresh_from_db()
    partial.refresh_from_db()
    fresh.refresh_from_db()
    assert empty.status == Report.Status.FAILED
    assert partial.status == Report.Status.PARTIAL
    assert partial.body == "# Snapshot"
    assert partial.processing["generator"] == "llm_timeout"
    assert partial.processing["error"].startswith("timeout:")
    assert fresh.status == Report.Status.QUEUED


def test_expired_lease_requeues_job_and_exhausted_job_fails():
    owner = User.objects.create_user(username="task-status-job")
    space = make_space(owner)
    retryable = make_job(owner, space, "retryable")
    exhausted = make_job(owner, space, "exhausted")
    now = timezone.now()
    AnalysisJob.objects.filter(pk=retryable.pk).update(
        state=AnalysisJob.State.RUNNING,
        attempts=1,
        lease_owner="worker-1",
        lease_until=now - timedelta(seconds=5),
        checkpoint={"last_ingest_seq": 2},
    )
    AnalysisJob.objects.filter(pk=exhausted.pk).update(
        state=AnalysisJob.State.RUNNING,
        attempts=3,
        lease_owner="worker-2",
        lease_until=now - timedelta(seconds=5),
    )

    result = recover_expired_analysis_jobs(now=now, max_attempts=3)

    assert result["requeued"] == 1
    assert result["failed"] == 1
    assert result["requeued_job_ids"] == [retryable.pk]
    retryable.refresh_from_db()
    exhausted.refresh_from_db()
    assert retryable.state == AnalysisJob.State.QUEUED
    assert retryable.checkpoint == {"last_ingest_seq": 2}
    assert retryable.lease_owner == ""
    assert retryable.error.startswith("lease_expired:")
    assert exhausted.state == AnalysisJob.State.FAILED
    assert "max attempts" in exhausted.error


def test_live_lease_is_left_alone():
    owner = User.objects.create_user(username="task-status-live")
    space = make_space(owner)
    job = make_job(owner, space, "live")
    AnalysisJob.objects.filter(pk=job.pk).update(
        state=AnalysisJob.State.RUNNING,
        lease_owner="worker-1",
        lease_until=timezone.now() + timedelta(seconds=120),
    )

    assert recover_expired_analysis_jobs() == {
        "requeued": 0,
        "failed": 0,
        "requeued_job_ids": [],
    }


def test_sweep_task_redispatches_recovered_jobs():
    owner = User.objects.create_user(username="task-status-sweep")
    space = make_space(owner)
    job = make_job(owner, space, "sweep")
    AnalysisJob.objects.filter(pk=job.pk).update(
        state=AnalysisJob.State.RUNNING,
        attempts=1,
        lease_owner="worker-1",
        lease_until=timezone.now() - timedelta(seconds=5),
    )

    with patch(
        "chat_analysis.tasks.execute_analysis_job_task.delay"
    ) as dispatch:
        result = sweep_stale_async_tasks.run()

    dispatch.assert_called_once_with(job.pk)
    assert result["jobs_requeued"] == 1
    assert "requeued_job_ids" not in result


def test_sweep_counts_are_zero_when_everything_is_terminal():
    owner = User.objects.create_user(username="task-status-clean")
    make_space(owner)

    counts = sweep_stale_tasks()

    assert counts["questions_failed"] == 0
    assert counts["reports_expired"] == 0
    assert counts["jobs_requeued"] == 0
    assert counts["jobs_failed"] == 0
