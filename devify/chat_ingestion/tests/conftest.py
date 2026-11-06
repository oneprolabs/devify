import pytest


@pytest.fixture(autouse=True)
def parse_uploads_inline(settings):
    """Keep parser assertions deterministic without requiring a broker."""
    settings.CHAT_UPLOAD_PARSE_INLINE = True
    settings.CHAT_UPLOAD_ANALYSIS_INLINE = True
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
