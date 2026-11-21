"""Displayed daily AI usage must match quota admission."""

from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from chat_analysis.models import ChatSummary, QuestionAnswer
from chat_domain.models import Conversation, Message, MessagePart
from chat_ingestion.models import UploadBatch
from spaces.models import SpaceQuota
from spaces.services import quotas
from spaces.views import configuration as views


@pytest.mark.parametrize(
    "questions,summaries,limit",
    [(0, 1, 1), (1, 0, 1), (1, 2, 4), (0, 0, 1)],
)
def test_quota_usage_includes_summaries(questions, summaries, limit):
    space = SimpleNamespace(pk=UUID(int=1), memberships=Mock())
    space.memberships.filter.return_value.count.return_value = 1
    quota = SpaceQuota(space_id=space.pk, daily_ai_calls=limit)
    now = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
    with ExitStack() as stack:
        stack.enter_context(
            patch("django.utils.timezone.now", return_value=now)
        )
        stack.enter_context(
            patch.object(quotas, "get_space_quota", return_value=quota)
        )
        qa = stack.enter_context(
            patch.object(QuestionAnswer.objects, "filter")
        )
        qa.return_value.count.return_value = questions
        chat = stack.enter_context(patch.object(ChatSummary.objects, "filter"))
        chat.return_value.count.return_value = summaries
        for model in [Conversation, Message, MessagePart]:
            query = stack.enter_context(patch.object(model.objects, "filter"))
            query.return_value.count.return_value = 0
        uploads = stack.enter_context(
            patch.object(UploadBatch.objects, "filter")
        )
        uploads.return_value.exclude.return_value.aggregate.return_value = {
            "total": 0
        }
        stack.enter_context(
            patch.object(views, "get_object_or_404", return_value=space)
        )
        stack.enter_context(
            patch.object(
                views.SpacePermissionService, "can_read", return_value=True
            )
        )
        stack.enter_context(
            patch.object(
                SpaceQuota.objects,
                "get_or_create",
                return_value=(quota, False),
            )
        )
        blocked = quotas.check_daily_ai_quota(space)
        response = views.SpaceQuotaUsageAPIView().get(
            SimpleNamespace(user=object()), space.pk
        )
    used = response.data["data"]["usage"]["daily_ai_calls_used"]
    assert used == questions + summaries
    assert bool(blocked) == (used >= limit)
    # Admission and display must count the same space and day boundary.
    assert chat.call_count == 2
    assert qa.call_args_list[0] == qa.call_args_list[1]
    assert chat.call_args_list[0] == chat.call_args_list[1]
    assert qa.call_args == chat.call_args
