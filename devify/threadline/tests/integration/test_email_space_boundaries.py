"""Legacy email endpoints must respect the space boundary.

Threadline still exposes per-user endpoints such as ``/threadlines/<uuid>``.
Those used to filter by owner only, so a member removed from a team space
kept reading the mail they had uploaded to it. Every space-bound read now
also checks the current space permission.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from spaces.models import Space, SpaceMembership, SpaceTakeover
from threadline.tests.fixtures.factories import (
    EmailAttachmentFactory,
    EmailMessageFactory,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug="email-boundary-team"):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def mailbox():
    owner = User.objects.create_user(username="email-boundary-owner")
    space = make_space(owner)
    message = EmailMessageFactory(user=owner, space=space)
    attachment = EmailAttachmentFactory(
        user=owner, email_message=message, filename="quote.pdf"
    )
    return {
        "owner": owner,
        "space": space,
        "message": message,
        "attachment": attachment,
    }


def test_space_member_reads_message(mailbox):
    client = client_for(mailbox["owner"])

    detail = client.get(
        reverse("threadlines-detail", kwargs={"uuid": mailbox["message"].uuid})
    )

    assert detail.status_code == 200


def test_outsider_cannot_read_by_guessing_the_uuid(mailbox):
    outsider = User.objects.create_user(username="email-boundary-outsider")
    make_space(outsider, slug="email-boundary-other")
    client = client_for(outsider)

    detail = client.get(
        reverse("threadlines-detail", kwargs={"uuid": mailbox["message"].uuid})
    )

    assert detail.status_code == 404


def test_removed_member_loses_access_to_their_old_uploads(mailbox):
    removed = User.objects.create_user(username="email-boundary-removed")
    SpaceMembership.objects.create(
        space=mailbox["space"],
        user=removed,
        role=SpaceMembership.Role.USER,
        status=SpaceMembership.Status.REMOVED,
    )
    # The row is still owned by the removed member; only the space check
    # stands between them and the message.
    mailbox["message"].user = removed
    mailbox["message"].save(update_fields=("user",))
    client = client_for(removed)

    detail = client.get(
        reverse("threadlines-detail", kwargs={"uuid": mailbox["message"].uuid})
    )
    listing = client.get(reverse("threadlines-list"))

    assert detail.status_code == 404
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total"] == 0


def test_staff_reads_space_mail_only_through_the_space_api(mailbox):
    """Legacy endpoints stay per-user; staff use the space API."""

    staff = User.objects.create_user(
        username="email-boundary-staff", is_staff=True
    )
    space = mailbox["space"]
    email_uuid = mailbox["message"].uuid
    legacy_url = reverse("threadlines-detail", kwargs={"uuid": email_uuid})
    space_url = reverse(
        "space-email-detail",
        kwargs={"space_id": space.pk, "email_uuid": email_uuid},
    )
    client = client_for(staff)

    assert client.get(legacy_url).status_code == 404
    assert client.get(space_url).status_code == 404

    SpaceTakeover.objects.create(
        space=space, admin=staff, reason="incident review"
    )
    assert client.get(space_url).status_code == 200
    # The legacy per-user endpoint never widens to staff.
    assert client.get(legacy_url).status_code == 404


def test_unbound_legacy_mail_stays_readable_by_its_owner(mailbox):
    owner = mailbox["owner"]
    legacy = EmailMessageFactory(user=owner, space=None)
    client = client_for(owner)

    response = client.get(
        reverse("threadlines-detail", kwargs={"uuid": legacy.uuid})
    )

    assert response.status_code == 200


def test_archived_space_stays_readable(mailbox):
    space = mailbox["space"]
    space.status = Space.Status.ARCHIVED
    space.save(update_fields=("status", "updated_at"))
    client = client_for(mailbox["owner"])

    response = client.get(
        reverse("threadlines-detail", kwargs={"uuid": mailbox["message"].uuid})
    )

    assert response.status_code == 200
