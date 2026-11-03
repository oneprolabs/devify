"""Space context is checked before app metadata or account stats are read."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from relay.views import AppsAPIView

pytestmark = pytest.mark.unit


def request(user_id=1, **query):
    return SimpleNamespace(user=SimpleNamespace(id=user_id), query_params=query)


def test_unscoped_apps_keep_legacy_account_behavior():
    with patch("relay.views.APP_REGISTRY.list_apps", return_value=[]) as listing:
        response = AppsAPIView().get(request())
    assert response.status_code == 200
    listing.assert_called_once()
    assert listing.call_args.args[0].id == 1
    assert listing.call_args.kwargs == {}


@pytest.mark.parametrize("space_id", ["0", "bad", "-1", "99999999999999999999", "１２"])
def test_invalid_space_id_rejected(space_id):
    with patch("relay.views.APP_REGISTRY.list_apps") as listing:
        response = AppsAPIView().get(request(space_id=space_id))
    assert response.status_code == 400
    listing.assert_not_called()


def test_team_space_is_authorized_before_filtering():
    space = SimpleNamespace(kind="team", personal_owner_id=None)
    with patch("relay.views.get_object_or_404", return_value=space), patch(
        "spaces.services.SpacePermissionService.can_read", return_value=True
    ), patch("relay.views.APP_REGISTRY.list_apps", return_value=[]) as listing:
        response = AppsAPIView().get(request(space_id="12"))
    assert response.status_code == 200
    assert listing.call_args.kwargs["space_kind"] == "team"


@pytest.mark.parametrize("kind,owner,allowed", [("team", None, False), ("personal", 2, True)])
def test_denied_or_someone_elses_personal_space_never_lists_apps(kind, owner, allowed):
    space = SimpleNamespace(kind=kind, personal_owner_id=owner)
    with patch("relay.views.get_object_or_404", return_value=space), patch(
        "spaces.services.SpacePermissionService.can_read", return_value=allowed
    ), patch("relay.views.APP_REGISTRY.list_apps") as listing:
        response = AppsAPIView().get(request(space_id="12"))
    assert response.status_code == 404
    listing.assert_not_called()
