"""Keep summary tasks and endpoints compatible when Python modules move."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from celery import current_app
from django.urls import resolve

from chat_analysis.summaries.services import dispatch
from chat_analysis.summaries.tasks import generate_chat_summary
from chat_analysis.summaries.views import SummaryDetail, SummaryList

TASK_NAME = "chat_analysis.summary_tasks.generate_chat_summary"


def test_summary_urls_resolve_to_the_collected_views():
    space_id = "00000000-0000-0000-0000-000000000001"
    base = f"/api/v1/spaces/{space_id}/chat-summaries"
    listing = resolve(base)
    detail = resolve(f"{base}/42")
    assert listing.url_name == "chat-summary-list"
    assert listing.func.view_class is SummaryList
    assert detail.url_name == "chat-summary-detail"
    assert detail.func.view_class is SummaryDetail


def test_summary_task_keeps_its_wire_name_and_autodiscovery_export():
    from chat_analysis.tasks import generate_chat_summary as discovered

    assert discovered is generate_chat_summary
    assert generate_chat_summary.name == TASK_NAME
    assert current_app.tasks[TASK_NAME].run == generate_chat_summary.run
    assert generate_chat_summary.max_retries == 0
    assert generate_chat_summary.soft_time_limit == 270
    assert generate_chat_summary.time_limit == 300


def test_summary_dispatch_uses_the_existing_queue_and_token():
    summary = SimpleNamespace(pk=42, dispatch_token="token-1")
    with patch.object(generate_chat_summary, "apply_async") as enqueue:
        dispatch(summary)
    enqueue.assert_called_once_with(
        args=[42, "token-1"], queue="chat_analysis"
    )


def test_rejected_summary_claim_does_not_call_the_model():
    with (
        patch(
            "chat_analysis.summaries.tasks.ChatSummary.objects.filter"
        ) as query,
        patch(
            "chat_analysis.summaries.tasks.LLMTracker.call_and_track"
        ) as model,
    ):
        scope = query.return_value
        scope.filter.return_value.update.return_value = 0
        result = generate_chat_summary.run(42, "stale-token")
    assert result == {"summary_id": 42, "claimed": False}
    query.assert_called_once_with(pk=42, dispatch_token="stale-token")
    scope.filter.assert_called_once_with(status="queued")
    scope.select_related.assert_not_called()
    model.assert_not_called()


def test_duplicate_summary_delivery_calls_the_model_once(settings):
    settings.CHAT_ANALYSIS_MODEL_UUID = None
    record = SimpleNamespace(created_by=object(), space=object())
    with (
        patch(
            "chat_analysis.summaries.tasks.ChatSummary.objects.filter"
        ) as query,
        patch(
            "chat_analysis.summaries.tasks.can_use_chat_summary",
            return_value=True,
        ),
        patch(
            "chat_analysis.summaries.tasks.SpacePermissionService.can_upload",
            return_value=True,
        ),
        patch(
            "chat_analysis.summaries.tasks.summary_content",
            return_value="input",
        ),
        patch(
            "chat_analysis.summaries.tasks.request_budget",
            return_value=(12000, Mock(return_value=1)),
        ),
        patch(
            "chat_analysis.summaries.tasks.LLMTracker.call_and_track",
            return_value=("  ## Summary  ", {"model": "test-model"}),
        ) as model,
    ):
        scope = query.return_value
        scope.select_related.return_value.get.return_value = record
        # First delivery claims and completes; the duplicate cannot claim.
        updates = scope.filter.return_value.update
        updates.side_effect = [1, 1, 0]
        first = generate_chat_summary.run(42, "token-1")
        duplicate = generate_chat_summary.run(42, "token-1")
    assert first == {"summary_id": 42, "status": "ready", "persisted": True}
    assert duplicate == {"summary_id": 42, "claimed": False}
    model.assert_called_once()
    completed = updates.call_args_list[1].kwargs
    assert completed["status"] == "ready"
    assert completed["body"] == "## Summary"
    assert completed["input_messages"] == []
    assert completed["model"] == "test-model"


def test_dispatch_failure_only_fails_the_matching_queued_attempt():
    summary = SimpleNamespace(pk=42, dispatch_token="token-1")
    with (
        patch.object(
            generate_chat_summary,
            "apply_async",
            side_effect=RuntimeError("broker unavailable"),
        ),
        patch(
            "chat_analysis.summaries.services.ChatSummary.objects.filter"
        ) as query,
    ):
        dispatch(summary)
    query.assert_called_once_with(
        pk=42, status="queued", dispatch_token="token-1"
    )
    assert query.return_value.update.call_args.kwargs["status"] == "failed"
