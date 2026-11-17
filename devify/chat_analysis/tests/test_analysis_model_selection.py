from unittest.mock import patch

from chat_analysis.execution import _call_json
from chat_analysis.token_budget import request_budget


def test_chat_analysis_uses_configured_model(settings):
    settings.CHAT_ANALYSIS_MODEL_UUID = 'b09567aa-846a-44fe-9623-2eb4380a4156'
    with patch('chat_analysis.execution.request_budget', return_value=(1000, lambda *_: 1)), patch(
        'chat_analysis.execution.LLMTracker.call_and_track', return_value=({'facts': []}, {})
    ) as call:
        assert _call_json(prompt='test', content='test', node_name='chat_note') == {'facts': []}
    assert call.call_args.kwargs['model_uuid'] == settings.CHAT_ANALYSIS_MODEL_UUID


def test_budget_uses_the_same_chat_model(settings):
    settings.CHAT_ANALYSIS_MODEL_UUID = 'b09567aa-846a-44fe-9623-2eb4380a4156'
    with patch('agentcore_metering.adapters.django.services.runtime_config.get_litellm_params', return_value={}) as get_params:
        request_budget(12000)
    assert get_params.call_args.kwargs['model_uuid'] == settings.CHAT_ANALYSIS_MODEL_UUID
