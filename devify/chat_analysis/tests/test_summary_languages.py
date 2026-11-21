"""Output language is client input, independent of system-template catalogs."""

import pytest
from rest_framework import serializers

from chat_analysis.summaries.serializers import SummaryCreate


@pytest.mark.parametrize(
    "language",
    ["中文", "English", "按原文语言", "auto", "zh-CN", "en-US", "es", "fr-FR"],
)
def test_client_language_is_preserved(language):
    serializer = SummaryCreate()
    value = serializer.fields["language"].run_validation(language)
    assert serializer.validate_language(value) == language


def test_omitted_language_keeps_the_released_api_default():
    field = SummaryCreate().fields["language"]
    assert field.run_validation(serializers.empty) == "中文"


@pytest.mark.parametrize("language", ["unknown", "跟随界面", "", "en_US"])
def test_invalid_language_is_rejected(language):
    with pytest.raises(serializers.ValidationError):
        serializer = SummaryCreate()
        value = serializer.fields["language"].run_validation(language)
        serializer.validate_language(value)
