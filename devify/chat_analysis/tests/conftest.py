import pytest


@pytest.fixture(autouse=True)
def rule_based_analysis_by_default(settings):
    """Keep rule-based assertions deterministic regardless of the environment.

    The dev container exports ``CHAT_ANALYSIS_LLM_ENABLED=true``, so without
    this a test that only cares about chunking would hit the LLM path and any
    failure there would turn into a retry instead of an assertion. Tests that
    exercise the model enable it themselves through the ``settings`` fixture.
    """

    settings.CHAT_ANALYSIS_LLM_ENABLED = False
