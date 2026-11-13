import pytest


@pytest.fixture(autouse=True)
def parse_uploads_inline(settings, tmp_path):
    """Keep parser assertions deterministic without requiring a broker."""
    settings.CHAT_UPLOAD_PARSE_INLINE = True
    settings.CHAT_UPLOAD_ANALYSIS_INLINE = True
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    settings.CHAT_MEDIA_DIR = str(tmp_path / "chat_media")
