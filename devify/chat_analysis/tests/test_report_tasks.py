from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from chat_analysis.models import Report
from chat_analysis.report_tasks import generate_report_task
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def make_report(owner, slug="report-task-team"):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return Report.objects.create(
        space=space,
        created_by=owner,
        request_key=f"{slug}-request",
        title="Task report",
        status=Report.Status.QUEUED,
        body="# Rule fallback",
        processing={"generator": "llm_pending"},
    )


def test_report_task_replaces_fallback_body_with_valid_llm_output():
    owner = User.objects.create_user(username="report-task-owner")
    report = make_report(owner)
    output = {
        "body": "# LLM report\n\nConfirmed follow-up.",
        "sections": [],
    }
    with patch(
        "chat_analysis.report_tasks.LLMTracker.call_and_track",
        return_value=(output, {"model": "test-model"}),
    ) as call:
        result = generate_report_task.run(report.pk)

    report.refresh_from_db()
    assert result["status"] == Report.Status.READY
    assert report.body == output["body"]
    assert report.processing["generator"] == "llm"
    call.assert_called_once()


def test_report_task_keeps_fallback_as_partial_when_llm_fails():
    owner = User.objects.create_user(username="report-task-failed")
    report = make_report(owner, "report-task-failed-team")
    with patch(
        "chat_analysis.report_tasks.LLMTracker.call_and_track",
        side_effect=RuntimeError("provider unavailable"),
    ):
        result = generate_report_task.run(report.pk)

    report.refresh_from_db()
    assert result["status"] == Report.Status.PARTIAL
    assert report.body == "# Rule fallback"
    assert report.processing["generator"] == "llm_failed"
