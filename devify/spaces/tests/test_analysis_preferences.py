import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from spaces.services import SpaceBootstrapService


@pytest.mark.django_db
def test_analysis_preferences_persist_and_validate():
    user = User.objects.create_user(username="preferences-owner")
    space = SpaceBootstrapService.ensure_personal_space(user)
    client = APIClient()
    client.force_authenticate(user=user)
    url = f"/api/v1/spaces/{space.pk}/workflow-config"
    initial = client.get(url)
    assert initial.status_code == 200
    prefs = initial.data["data"]["chat_analysis_preferences"]
    assert prefs["event_granularity"] == "balanced"
    prefs.update(event_granularity="coarse", lookback_days=30)
    result = client.patch(
        url, {"chat_analysis_preferences": prefs}, format="json"
    )
    assert result.status_code == 200
    assert client.get(url).data["data"]["chat_analysis_preferences"] == prefs
    assert (
        client.patch(
            url,
            {"chat_analysis_preferences": {"auto_analyze": False}},
            format="json",
        ).status_code
        == 400
    )
    prefs["event_granularity"] = "invalid"
    assert (
        client.patch(
            url, {"chat_analysis_preferences": prefs}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.get(url).data["data"]["chat_analysis_preferences"][
            "event_granularity"
        ]
        == "coarse"
    )


@pytest.mark.django_db
def test_auto_analyze_is_a_true_compatibility_field_not_a_privacy_switch():
    from spaces.models import SpaceWorkflowConfig

    user = User.objects.create_user(username="auto-analysis-owner")
    space = SpaceBootstrapService.ensure_personal_space(user)
    client = APIClient()
    client.force_authenticate(user=user)
    url = f"/api/v1/spaces/{space.pk}/workflow-config"
    prefs = client.get(url).data["data"]["chat_analysis_preferences"]
    assert prefs["auto_analyze"] is True

    assert (
        client.patch(
            url, {"chat_analysis_preferences": prefs}, format="json"
        ).status_code
        == 200
    )
    config = SpaceWorkflowConfig.objects.get(space=space)
    before_version = config.version
    prefs["auto_analyze"] = False
    response = client.patch(
        url, {"chat_analysis_preferences": prefs}, format="json"
    )
    assert response.status_code == 400
    assert "not supported" in str(response.data).lower()
    config.refresh_from_db()
    assert config.version == before_version
    assert config.chat_analysis_preferences["auto_analyze"] is True

    # A historical false was never an effective off-switch. Do not mutate it
    # during reads or unrelated configuration updates.
    config.chat_analysis_preferences = prefs
    config.save(update_fields=("chat_analysis_preferences",))
    returned = client.get(url).data["data"]["chat_analysis_preferences"]
    assert returned["auto_analyze"] is True
    assert (
        client.patch(url, {"language": "en"}, format="json").status_code == 200
    )
    config.refresh_from_db()
    assert config.chat_analysis_preferences["auto_analyze"] is False
    assert (
        client.patch(
            url, {"chat_analysis_preferences": returned}, format="json"
        ).status_code
        == 200
    )
    config.refresh_from_db()
    assert config.chat_analysis_preferences["auto_analyze"] is True


@pytest.mark.parametrize(
    "types,expected",
    [
        (["group", "direct", "group"], ["direct", "group"]),
        (["direct", "future"], ["direct", "future"]),
        (
            ["group", {"unexpected": True}, 1],
            ["group", {"unexpected": True}, 1],
        ),
        (None, None),
        (42, 42),
    ],
)
def test_conversation_type_normalization_is_safe_and_does_not_mutate(
    types, expected
):
    from copy import deepcopy

    from spaces.models import effective_chat_analysis_preferences

    preferences = {"conversation_types": types}
    original = deepcopy(preferences)
    result = effective_chat_analysis_preferences(preferences)
    assert result["conversation_types"] == expected
    assert preferences == original
