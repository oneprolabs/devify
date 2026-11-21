"""Summary admission must acquire user locks before expiring records."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from chat_analysis.summaries import views


class StopAfterExpiry(Exception):
    """Stop the unit probe before any database writes or dispatch."""


@pytest.mark.parametrize("view_type", [views.SummaryList, views.SummaryDetail])
def test_create_and_retry_lock_user_before_expiring_records(view_type):
    operations = []
    users = Mock()
    users.select_for_update.return_value.get.side_effect = (
        lambda **kwargs: operations.append("user_lock")
    )

    def expire():
        operations.append("expire_summaries")
        raise StopAfterExpiry

    request = SimpleNamespace(user=SimpleNamespace(pk=1), data={})
    with (
        patch.object(views, "summary_space", return_value=object()),
        patch.object(views, "SummaryCreate") as serializer,
        patch.object(views.ChatSummary.objects, "filter") as summaries,
        patch.object(
            views,
            "get_user_model",
            return_value=SimpleNamespace(objects=users),
        ),
        patch.object(views, "expire_stale_summaries", side_effect=expire),
    ):
        serializer.return_value.validated_data = {"request_key": "probe"}
        summaries.return_value.first.return_value = None
        args = (request, "space")
        if view_type is views.SummaryDetail:
            args += (42,)
        with pytest.raises(StopAfterExpiry):
            view_type.post.__wrapped__(view_type(), *args)
    assert operations == ["user_lock", "expire_summaries"]
