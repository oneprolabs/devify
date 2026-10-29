import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_ingestion.models import UploadBatch
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def test_space_member_can_list_upload_batches():
    owner = User.objects.create_user(username="list-upload-owner")
    space = Space.objects.create(
        name="Upload list",
        slug="upload-list-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="list-1",
    )
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        f"/api/v1/spaces/{space.pk}/chat/uploads?page_size=1"
    )

    assert response.status_code == 200
    assert len(response.data["data"]["list"]) == 1
    assert response.data["data"]["pagination"]["page_size"] == 1
