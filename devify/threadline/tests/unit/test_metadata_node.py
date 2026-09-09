from types import SimpleNamespace
from unittest.mock import Mock, patch

from threadline.agents.email_state import has_node_errors
from threadline.agents.nodes.metadata_node import MetadataNode
from threadline.agents.progress import (
    estimate_initial_workflow_units,
    estimate_prepare_workflow_units,
)


def _state(metadata):
    return {
        "subject": "Build notification",
        "summary_title": "Build completed",
        "summary_content": "The release build completed successfully.",
        "prompt_config": {"metadata_prompt": "Extract metadata"},
        "text_llm_config_uuid": None,
        "metadata": metadata,
        "node_errors": {},
        "force": False,
    }


@patch("threadline.agents.nodes.metadata_node.LLMTracker.call_and_track")
def test_ingestion_metadata_does_not_skip_metadata_extraction(mock_call):
    mock_call.return_value = (
        {
            "category": "Infrastructure",
            "participants": [],
            "timeline": [],
            "keywords": ["release build"],
        },
        {},
    )
    state = _state(
        {
            "content_type": "message/rfc822",
            "eml_file": "/tmp/email.eml",
            "original_size": 1024,
            "saved_size": 1024,
        }
    )

    result = MetadataNode()(state)

    assert result["metadata"] == mock_call.return_value[0]
    assert not has_node_errors(result)
    mock_call.assert_called_once()


@patch("threadline.agents.nodes.metadata_node.LLMTracker.call_and_track")
def test_custom_extracted_metadata_is_reused(mock_call):
    metadata = {"custom_tags": ["feedback"]}

    result = MetadataNode()(_state(metadata))

    assert result["metadata"] == metadata
    mock_call.assert_not_called()


def test_ingestion_metadata_is_included_in_progress_estimates():
    ingestion_metadata = {"eml_file": "/tmp/email.eml"}
    attachments = Mock()
    attachments.filter.return_value = []
    email = SimpleNamespace(
        attachments=attachments,
        text_content="",
        llm_content=None,
        summary_title="Build completed",
        summary_data={"details": "Done"},
        metadata=ingestion_metadata,
    )

    initial_units = estimate_initial_workflow_units(email=email)
    prepared_units = estimate_prepare_workflow_units(
        state={
            "attachments": [],
            "summary_title": email.summary_title,
            "summary_data": email.summary_data,
            "metadata": ingestion_metadata,
        }
    )

    assert initial_units["metadata"] == 1
    assert prepared_units["metadata"] == 1
