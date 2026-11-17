import pytest
from django.contrib.auth.models import User

from chat_ingestion.models import UploadBatch
from chat_ingestion.views import _can_operate_batch
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.PERSONAL,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return space


def test_staff_owner_can_operate_own_upload_batch():
    """A staff account acts through its membership, not only via takeover."""
    staff = User.objects.create_user(username="staff-owner", is_staff=True)
    space = make_space(staff, "staff-owner-space")
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=staff,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="staff-batch-1",
    )

    assert _can_operate_batch(staff, batch) is True

    other_staff = User.objects.create_user(
        username="other-staff", is_staff=True
    )
    assert _can_operate_batch(other_staff, batch) is False
