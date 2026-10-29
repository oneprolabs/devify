from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.utils import timezone

from threadline.models import (
    EmailAttachment, EmailMailbox, EmailMessage, _assign_personal_space,
)
from spaces.models import (
    Space, SpaceAuditLog, SpaceMembership, SpacePolicy, SpaceTakeover,
)
from spaces.services import SpaceBootstrapService, SpacePermissionService


@pytest.mark.django_db
@pytest.mark.integration
def test_personal_space_bootstrap_is_idempotent():
    user = User.objects.create_user(username="space-user", password="secret")

    first = SpaceBootstrapService.ensure_personal_space(user)
    second = SpaceBootstrapService.ensure_personal_space(user)

    assert first.pk == second.pk
    assert Space.objects.filter(personal_owner=user).count() == 1
    assert SpaceMembership.objects.filter(
        space=first,
        user=user,
        role=SpaceMembership.Role.OWNER,
        status=SpaceMembership.Status.ACTIVE,
    ).count() == 1


@pytest.mark.django_db
@pytest.mark.integration
def test_team_space_creation_requires_global_policy_for_regular_user():
    user = User.objects.create_user(username="regular", password="secret")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/spaces",
        {"name": "Team Space", "slug": "team-space"},
        format="json",
    )

    assert response.status_code == 403
    assert not Space.objects.filter(slug="team-space").exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_team_space_creation_creates_owner_and_audit_log_when_enabled():
    user = User.objects.create_user(username="creator", password="secret")
    SpacePolicy.objects.create(allow_user_create_spaces=True)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/spaces",
        {"name": "Team Space", "slug": "team-space"},
        format="json",
    )

    assert response.status_code == 201
    space = Space.objects.get(slug="team-space")
    assert response.data["data"]["role"] == SpaceMembership.Role.OWNER
    assert SpaceMembership.objects.get(
        space=space,
        user=user,
    ).role == SpaceMembership.Role.OWNER
    assert SpaceAuditLog.objects.filter(
        space=space,
        action="space.created",
        actor=user,
    ).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_space_list_only_returns_active_memberships():
    user = User.objects.create_user(username="member", password="secret")
    personal = SpaceBootstrapService.ensure_personal_space(user)
    other = Space.objects.create(
        name="Other",
        slug="other-space",
        kind=Space.Kind.TEAM,
    )
    SpaceMembership.objects.create(
        space=other,
        user=user,
        role=SpaceMembership.Role.GUEST,
        status=SpaceMembership.Status.REMOVED,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/spaces")

    assert response.status_code == 200
    assert [item["id"] for item in response.data["data"]] == [
        personal.id,
    ]


@pytest.mark.parametrize(
    ("role", "can_manage", "can_write"),
    [
        (SpaceMembership.Role.OWNER, True, True),
        (SpaceMembership.Role.MAINTAINER, True, True),
        (SpaceMembership.Role.USER, False, True),
        (SpaceMembership.Role.GUEST, False, False),
    ],
)
def test_role_permission_matrix(role, can_manage, can_write):
    membership = SpaceMembership(role=role)
    assert SpacePermissionService.can_manage(membership) is can_manage
    assert SpacePermissionService.can_write(membership) is can_write


def test_missing_membership_has_no_permissions():
    assert not SpacePermissionService.can_manage(None)
    assert not SpacePermissionService.can_write(None)


@pytest.mark.parametrize(
    "status",
    [SpaceMembership.Status.INVITED, SpaceMembership.Status.REMOVED],
)
def test_inactive_membership_has_no_permissions(status):
    membership = SpaceMembership(
        role=SpaceMembership.Role.OWNER,
        status=status,
    )
    assert not SpacePermissionService.can_manage(membership)
    assert not SpacePermissionService.can_write(membership)


@pytest.mark.django_db
@pytest.mark.integration
def test_resource_permission_matrix_requires_takeover_for_global_admin():
    owner = User.objects.create_user(username="resource-owner")
    member = User.objects.create_user(username="resource-member")
    guest = User.objects.create_user(username="resource-guest")
    admin = User.objects.create_user(username="resource-admin", is_staff=True)
    space = Space.objects.create(
        name="Resource Team",
        slug="resource-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    for user, role in (
        (owner, SpaceMembership.Role.OWNER),
        (member, SpaceMembership.Role.USER),
        (guest, SpaceMembership.Role.GUEST),
    ):
        SpaceMembership.objects.create(space=space, user=user, role=role)

    assert SpacePermissionService.can_read(member, space)
    assert SpacePermissionService.can_upload(member, space)
    assert SpacePermissionService.can_delete_resource(
        member, space, member.pk
    )
    assert not SpacePermissionService.can_delete_resource(
        member, space, owner.pk
    )
    assert SpacePermissionService.can_read(guest, space)
    assert not SpacePermissionService.can_upload(guest, space)
    assert SpacePermissionService.can_delete_resource(
        owner, space, member.pk
    )
    assert not SpacePermissionService.can_read(admin, space)

    SpaceTakeover.objects.create(
        space=space, admin=admin, reason="audit", active=True
    )
    assert SpacePermissionService.can_read(admin, space)
    assert SpacePermissionService.can_upload(admin, space)
    assert SpacePermissionService.can_delete_resource(
        admin, space, member.pk
    )


def test_inactive_space_disallows_upload_and_delete_without_queries():
    user = User(pk=1, is_staff=True)
    space = Space(status=Space.Status.ARCHIVED)
    with patch.object(SpacePermissionService, "has_active_takeover") as lookup:
        assert not SpacePermissionService.can_upload(user, space)
        assert not SpacePermissionService.can_delete_resource(user, space, 1)
        lookup.assert_not_called()


def test_personal_space_default_applies_only_to_new_unassigned_records():
    email = EmailMessage(user_id=10)
    with patch(
        "threadline.models._ensure_personal_space_id", return_value=42
    ) as ensure:
        _assign_personal_space(email)
        _assign_personal_space(email)
        assert email.space_id == 42
        ensure.assert_called_once_with(10)

    email.space_id = None
    email._state.adding = False
    with patch("threadline.models._ensure_personal_space_id") as ensure:
        _assign_personal_space(email)
        ensure.assert_not_called()


def test_new_attachment_inherits_its_parent_email_space():
    email = EmailMessage(pk=1, user_id=10, space_id=42)
    attachment = EmailAttachment(user_id=11, email_message=email)
    with patch("django.db.models.Model.save"):
        attachment.save()
    assert attachment.space_id == 42


@pytest.mark.django_db
@pytest.mark.integration
def test_member_invitation_and_role_boundaries():
    owner = User.objects.create_user(username="owner")
    manager = User.objects.create_user(username="manager")
    invited = User.objects.create_user(username="invited")
    space = Space.objects.create(
        name="Team", slug="member-team", kind=Space.Kind.TEAM, owner=owner,
    )
    for user, role in ((owner, "owner"), (manager, "maintainer")):
        SpaceMembership.objects.create(space=space, user=user, role=role)
    client = APIClient()
    client.force_authenticate(user=manager)
    base = f"/api/v1/spaces/{space.pk}/members"

    response = client.post(
        base, {"user_id": invited.pk, "role": "user"}, format="json"
    )
    assert response.status_code == 201
    assert client.post(f"{base}/{invited.pk}/accept").status_code == 403
    assert client.patch(
        f"{base}/{invited.pk}", {"role": "owner"}, format="json"
    ).status_code == 403
    assert client.delete(f"{base}/{owner.pk}").status_code == 403
    client.force_authenticate(user=invited)
    assert client.post(f"{base}/{invited.pk}/accept").status_code == 200
    assert client.post(
        base, {"user_id": owner.pk, "role": "user"}, format="json"
    ).status_code == 403
    assert client.delete(f"{base}/{invited.pk}").status_code == 204
    membership = SpaceMembership.objects.get(space=space, user=invited)
    assert membership.status == "removed"
    assert Space.objects.filter(pk=space.pk).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_invitation_limit_excludes_owner_not_inviter():
    owner = User.objects.create_user(username="limit-owner")
    manager = User.objects.create_user(username="limit-manager")
    invited = User.objects.create_user(username="limit-invited")
    space = Space.objects.create(
        name="Team", slug="limit-team", kind=Space.Kind.TEAM, owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    SpaceMembership.objects.create(
        space=space, user=manager, role="maintainer"
    )
    SpacePolicy.objects.create(max_invited_users=1)
    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.post(
        f"/api/v1/spaces/{space.pk}/members",
        {"user_id": invited.pk, "role": "user"}, format="json",
    )
    assert response.status_code == 409


@pytest.mark.django_db
@pytest.mark.integration
def test_takeover_is_audited_and_does_not_replace_existing_owner():
    owner = User.objects.create_user(username="takeover-owner")
    other = User.objects.create_user(username="takeover-other")
    admin = User.objects.create_user(username="takeover-admin", is_staff=True)
    space = Space.objects.create(
        name="Team", slug="takeover-team", kind=Space.Kind.TEAM, owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    client = APIClient()
    url = f"/api/v1/spaces/{space.pk}/takeover"
    client.force_authenticate(user=other)
    assert client.post(
        url, {"reason": "recovery"}, format="json"
    ).status_code == 403
    client.force_authenticate(user=admin)
    assert client.post(
        url, {"reason": "recovery", "owner_user_id": other.pk}, format="json"
    ).status_code == 409
    assert client.post(
        url, {"reason": "recovery"}, format="json"
    ).status_code == 201
    assert SpaceTakeover.objects.filter(
        space=space, admin=admin, active=True
    ).exists()
    assert SpaceAuditLog.objects.filter(
        space=space, actor=admin, action="space.taken_over"
    ).exists()
    assert client.delete(url).status_code == 204
    assert SpaceAuditLog.objects.filter(
        space=space, actor=admin, action="space.takeover_ended"
    ).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_only_global_admin_can_list_ownerless_team_spaces():
    admin = User.objects.create_user(username="orphan-admin", is_staff=True)
    user = User.objects.create_user(username="orphan-user")
    orphan = Space.objects.create(
        name="Ownerless", slug="ownerless-team", kind=Space.Kind.TEAM
    )
    Space.objects.create(
        name="Owned", slug="owned-team", kind=Space.Kind.TEAM, owner=user
    )
    client = APIClient()
    client.force_authenticate(user=user)
    assert client.get("/api/v1/admin/spaces/ownerless").status_code == 403
    client.force_authenticate(user=admin)
    response = client.get("/api/v1/admin/spaces/ownerless")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["data"]] == [orphan.id]


@pytest.mark.django_db
@pytest.mark.integration
def test_space_lifecycle_permissions():
    owner = User.objects.create_user(username="lifecycle-owner")
    manager = User.objects.create_user(username="lifecycle-manager")
    member = User.objects.create_user(username="lifecycle-member")
    space = Space.objects.create(
        name="Lifecycle Team",
        slug="lifecycle-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    SpaceMembership.objects.create(
        space=space, user=manager, role="maintainer"
    )
    SpaceMembership.objects.create(space=space, user=member, role="user")
    client = APIClient()
    url = f"/api/v1/spaces/{space.pk}"

    client.force_authenticate(user=manager)
    assert client.patch(
        url, {"name": "Renamed Team"}, format="json"
    ).status_code == 200
    assert client.patch(
        url, {"status": "archived"}, format="json"
    ).status_code == 403
    client.force_authenticate(user=member)
    assert client.patch(
        url, {"name": "Nope"}, format="json"
    ).status_code == 403
    client.force_authenticate(user=owner)
    response = client.patch(url, {"status": "archived"}, format="json")
    assert response.status_code == 200
    assert response.data["data"]["status"] == "archived"
    assert client.post(
        f"/api/v1/spaces/{space.pk}/members",
        {"user_id": member.pk, "role": "user"},
        format="json",
    ).status_code == 409
    assert client.patch(
        url, {"status": "active"}, format="json"
    ).status_code == 200
    assert SpaceAuditLog.objects.filter(
        space=space, action="space.updated", actor=owner
    ).count() == 2


@pytest.mark.django_db
@pytest.mark.integration
def test_personal_space_cannot_be_archived():
    user = User.objects.create_user(username="personal-lifecycle")
    space = Space.objects.get(personal_owner=user)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        f"/api/v1/spaces/{space.pk}", {"status": "archived"}, format="json"
    )

    assert response.status_code == 409


@pytest.mark.django_db
@pytest.mark.integration
def test_suspended_space_cannot_be_reactivated_by_owner():
    owner = User.objects.create_user(username="suspended-owner")
    space = Space.objects.create(
        name="Suspended",
        slug="suspended-space",
        kind=Space.Kind.TEAM,
        owner=owner,
        status=Space.Status.SUSPENDED,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.patch(
        f"/api/v1/spaces/{space.pk}", {"status": "active"}, format="json"
    )
    assert response.status_code == 409
    space.refresh_from_db()
    assert space.status == Space.Status.SUSPENDED


@pytest.mark.django_db
@pytest.mark.integration
def test_space_email_api_uses_space_membership_not_uploader():
    owner = User.objects.create_user(username="email-api-owner")
    member = User.objects.create_user(username="email-api-member")
    removed = User.objects.create_user(username="email-api-removed")
    admin = User.objects.create_user(username="email-api-admin", is_staff=True)
    space = Space.objects.create(
        name="Email API Team",
        slug="email-api-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    SpaceMembership.objects.create(space=space, user=member, role="user")
    SpaceMembership.objects.create(
        space=space, user=removed, role="user", status="removed"
    )
    email = EmailMessage.objects.create(
        user=owner,
        space=space,
        message_id="space-api-message",
        subject="Shared subject",
        sender="owner@example.com",
        recipients="team@example.com",
        received_at=timezone.now(),
    )
    client = APIClient()
    list_url = f"/api/v1/spaces/{space.pk}/emails"
    detail_url = f"{list_url}/{email.uuid}"
    client.force_authenticate(user=member)

    response = client.get(list_url)
    assert response.status_code == 200
    assert response.data["data"]["pagination"]["total"] == 1
    assert response.data["data"]["list"][0]["id"] == email.id
    assert client.get(detail_url).data["data"]["subject"] == "Shared subject"

    client.force_authenticate(user=removed)
    assert client.get(list_url).status_code == 404
    client.force_authenticate(user=admin)
    assert client.get(list_url).status_code == 404
    takeover = SpaceTakeover.objects.create(
        space=space, admin=admin, reason="audit"
    )
    assert client.get(list_url).status_code == 200
    assert client.get(detail_url).status_code == 200
    assert SpaceAuditLog.objects.filter(
        actor=admin, space=space, action="email.list_viewed",
        metadata__takeover_id=takeover.pk,
    ).exists()
    assert SpaceAuditLog.objects.filter(
        actor=admin, space=space, action="email.viewed",
        resource_id=str(email.pk), metadata__takeover_id=takeover.pk,
    ).exists()
    takeover.active = False
    takeover.save(update_fields=("active",))
    assert client.get(detail_url).status_code == 404


@pytest.mark.django_db
@pytest.mark.integration
def test_space_email_detail_rejects_email_from_another_space():
    user = User.objects.create_user(username="email-cross-space-user")
    other = User.objects.create_user(username="email-cross-space-other")
    email = EmailMessage.objects.create(
        user=other,
        message_id="other-space-email",
        subject="Private subject",
        sender="other@example.com",
        recipients="other@example.com",
        received_at=timezone.now(),
    )
    personal_space = Space.objects.get(personal_owner=user)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(
        f"/api/v1/spaces/{personal_space.pk}/emails/{email.uuid}"
    )
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.integration
def test_space_email_delete_allows_uploader_manager_and_taken_over_admin():
    owner = User.objects.create_user(username="email-delete-owner")
    member = User.objects.create_user(username="email-delete-member")
    admin = User.objects.create_user(
        username="email-delete-admin", is_staff=True
    )
    space = Space.objects.create(
        name="Delete Team",
        slug="delete-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    SpaceMembership.objects.create(space=space, user=member, role="user")

    def create_email(user, message_id):
        return EmailMessage.objects.create(
            user=user,
            space=space,
            message_id=message_id,
            subject=message_id,
            sender="sender@example.com",
            recipients="team@example.com",
            received_at=timezone.now(),
        )

    owner_email = create_email(owner, "owner-delete-email")
    member_email = create_email(member, "member-delete-email")
    client = APIClient()
    owner_url = f"/api/v1/spaces/{space.pk}/emails/{owner_email.uuid}"
    member_url = f"/api/v1/spaces/{space.pk}/emails/{member_email.uuid}"

    client.force_authenticate(user=member)
    assert client.delete(owner_url).status_code == 403
    assert client.delete(member_url).status_code == 204
    assert not EmailMessage.objects.filter(pk=member_email.pk).exists()

    client.force_authenticate(user=admin)
    assert client.delete(owner_url).status_code == 404
    takeover = SpaceTakeover.objects.create(
        space=space, admin=admin, reason="cleanup"
    )
    assert client.delete(owner_url).status_code == 204
    assert SpaceAuditLog.objects.filter(
        space=space,
        actor=admin,
        action="email.deleted",
        resource_id=str(owner_email.pk),
        metadata__takeover_id=takeover.pk,
    ).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_user_can_list_own_invitations_only():
    owner = User.objects.create_user(username="invite-list-owner")
    invited = User.objects.create_user(username="invite-list-user")
    other = User.objects.create_user(username="invite-list-other")
    space = Space.objects.create(
        name="Invitation Team",
        slug="invitation-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    SpaceMembership.objects.create(
        space=space,
        user=invited,
        role="guest",
        status="invited",
        invited_by=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=other,
        role="guest",
        status="invited",
        invited_by=owner,
    )
    client = APIClient()
    client.force_authenticate(user=invited)

    response = client.get("/api/v1/spaces/invitations")

    assert response.status_code == 200
    assert response.data["data"] == [
        {
            "space_id": space.id,
            "space_name": space.name,
            "space_slug": space.slug,
            "role": "guest",
            "invited_by_id": owner.id,
        }
    ]


@pytest.mark.django_db
@pytest.mark.integration
def test_only_owner_can_transfer_team_ownership():
    owner = User.objects.create_user(username="transfer-owner")
    manager = User.objects.create_user(username="transfer-manager")
    member = User.objects.create_user(username="transfer-member")
    space = Space.objects.create(
        name="Transfer Team",
        slug="transfer-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(space=space, user=owner, role="owner")
    SpaceMembership.objects.create(
        space=space, user=manager, role="maintainer"
    )
    SpaceMembership.objects.create(space=space, user=member, role="user")
    client = APIClient()
    url = f"/api/v1/spaces/{space.pk}/ownership"
    client.force_authenticate(user=manager)
    assert client.post(
        url, {"user_id": member.pk}, format="json"
    ).status_code == 403
    client.force_authenticate(user=owner)

    response = client.post(url, {"user_id": member.pk}, format="json")

    assert response.status_code == 200
    space.refresh_from_db()
    assert space.owner_id == member.id
    assert (
        SpaceMembership.objects.get(space=space, user=owner).role
        == "maintainer"
    )
    new_owner = SpaceMembership.objects.get(space=space, user=member)
    assert new_owner.role == "owner"
    assert SpaceAuditLog.objects.filter(
        space=space, actor=owner, action="space.ownership_transferred"
    ).exists()


@pytest.mark.django_db
@pytest.mark.integration
def test_new_email_resources_default_to_the_users_personal_space():
    user = User.objects.create_user(username="email-space-user")
    space = Space.objects.get(personal_owner=user)
    mailbox = EmailMailbox.objects.create(
        user=user,
        name="Personal mailbox",
        imap_host="imap.example.com",
        username="user@example.com",
        password="secret",
    )
    email = EmailMessage.objects.create(
        user=user,
        message_id="space-message-1",
        subject="Subject",
        sender="sender@example.com",
        recipients="user@example.com",
        received_at=timezone.now(),
    )
    attachment = EmailAttachment.objects.create(
        user=user,
        email_message=email,
        filename="note.txt",
        safe_filename="note.txt",
        content_type="text/plain",
        file_size=4,
        file_path="/tmp/note.txt",
    )

    assert mailbox.space_id == space.id
    assert email.space_id == space.id
    assert attachment.space_id == space.id
