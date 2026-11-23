"""Choose an ordered message window against a full-request token counter."""


def request_budget(configured_limit):
    """Use the same model and output allowance as the LLM tracker."""
    import litellm
    import tiktoken
    from agentcore_metering.adapters.django.services.runtime_config import (
        get_litellm_params,
    )
    from django.conf import settings

    try:
        params = get_litellm_params(
            model_uuid=settings.CHAT_ANALYSIS_MODEL_UUID
        )
    except ValueError:
        params = {}
    model = params.get("model", "")
    try:
        model_info = litellm.get_model_info(model) if model else {}
    except Exception:
        model_info = {}
    input_limit = model_info.get("max_input_tokens")
    if input_limit:
        output = (
            params.get("max_tokens")
            or model_info.get("max_output_tokens")
            or 0
        )
        configured_limit = min(configured_limit, input_limit - output)

    # Only opt into a tokenizer we can identify. Proxies and unknown models
    # use a conservative byte count, with room for provider-side framing.
    tokenizer_model = model.removeprefix("openai/")
    use_tokenizer = False
    api_base = (params.get("api_base") or "").rstrip("/")
    if api_base in ("", "https://api.openai.com/v1") and (
        model_info.get("litellm_provider") == "openai"
    ):
        try:
            tiktoken.encoding_name_for_model(tokenizer_model)
            use_tokenizer = True
        except KeyError:
            pass

    def count(prompt, content):
        if use_tokenizer:
            try:
                return 64 + litellm.token_counter(
                    model=tokenizer_model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": content},
                    ],
                )
            except (ValueError, OSError):
                pass
        return 64 + len(prompt.encode("utf-8")) + len(content.encode("utf-8"))

    return configured_limit, count


class MessageExceedsBudget(ValueError):
    """The request cannot fit the model input budget."""


def take_message_window(messages, count_request, input_budget):
    if input_budget <= 0 or count_request([]) > input_budget:
        raise MessageExceedsBudget(
            "The request overhead exceeds the input budget."
        )
    window = []
    for message in messages:
        candidate = window + [message]
        if count_request(candidate) > input_budget:
            if not window:
                raise MessageExceedsBudget(
                    "One message exceeds the model input budget."
                )
            break
        window = candidate
    return window
