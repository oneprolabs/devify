import pytest

from chat_analysis.token_budget import MessageExceedsBudget, take_message_window


def test_window_obeys_full_request_budget_and_preserves_order():
    messages = ["abcd", "efgh", "ij"]
    count_request = lambda chunk: 5 + sum(len(x) for x in chunk)
    assert take_message_window(messages, count_request, 13) == messages[:2]
    assert take_message_window(messages[2:], count_request, 13) == messages[2:]


def test_overlong_single_message_is_not_silently_dropped():
    with pytest.raises(MessageExceedsBudget):
        take_message_window(["x" * 20], lambda chunk: sum(map(len, chunk)), 10)


def test_invalid_or_impossible_budget_is_not_treated_as_success():
    with pytest.raises(ValueError):
        take_message_window(["a"], len, 0)
    with pytest.raises(ValueError):
        take_message_window([], lambda chunk: 11, 10)


def test_budget_reserves_output_and_counts_complete_model_request(monkeypatch):
    import litellm
    from agentcore_metering.adapters.django.services import runtime_config

    from chat_analysis.token_budget import request_budget

    params = {
        "model": "openai/gpt-4o",
        "max_tokens": 2048,
        "api_base": "https://api.openai.com/v1",
    }
    monkeypatch.setattr(runtime_config, "get_litellm_params", lambda: params)
    monkeypatch.setattr(
        litellm,
        "get_model_info",
        lambda model: {"litellm_provider": "openai", "max_input_tokens": 8192},
    )

    def count_tokens(*, model, messages):
        assert model == "gpt-4o"
        assert messages == [
            {"role": "system", "content": "prompt"},
            {"role": "user", "content": "文本😀"},
        ]
        return 17

    monkeypatch.setattr(litellm, "token_counter", count_tokens)
    budget, count = request_budget(12000)
    assert budget == 6144
    assert count("prompt", "文本😀") == 17 + 64

    params["api_base"] = "https://example.invalid/v1"
    _, count = request_budget(12000)
    assert count("prompt", "文本😀") == 64 + len("prompt文本😀".encode())
