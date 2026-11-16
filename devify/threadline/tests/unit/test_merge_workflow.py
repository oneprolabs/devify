"""
Unit tests for merge workflow enqueue behavior.
"""

from unittest.mock import patch

import pytest

from threadline.services.merge_workflow import enqueue_merge_workflow
from threadline.state_machine import EmailStatus
from threadline.tests.fixtures.factories import EmailMessageFactory


@pytest.mark.django_db
class TestMergeWorkflow:
    @patch("threadline.tasks.email_merge.process_email_merge.apply_async")
    def test_enqueue_merge_workflow_marks_target_processing_before_queueing(
        self,
        mock_delay,
        test_user,
        django_capture_on_commit_callbacks,
    ):
        email = EmailMessageFactory(
            user=test_user,
            status=EmailStatus.FETCHED.value,
        )

        with django_capture_on_commit_callbacks(execute=True):
            result = enqueue_merge_workflow(email, trigger_source="api_merge")

        email.refresh_from_db()
        assert result.id == email.id
        assert email.status == EmailStatus.PROCESSING.value
        assert email.metadata["processing_progress"]["percent"] == 0
        mock_delay.assert_called_once()
        assert mock_delay.call_args.kwargs["args"] == [str(email.pk)]
        assert mock_delay.call_args.kwargs["kwargs"] == {
            "force": False, "language": None, "scene": None,
            "trigger_source": "api_merge",
        }
