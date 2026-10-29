from django.db import transaction
from django.utils import timezone

from spaces.models import (
    Space,
    SpaceAuditLog,
    SpaceMembership,
    SpacePolicy,
    SpaceTakeover,
)


class SpaceBootstrapService:
    @staticmethod
    @transaction.atomic
    def ensure_personal_space(user):
        space, _ = Space.objects.get_or_create(
            personal_owner=user,
            defaults={
                "name": f"{user.get_username()[:112]}'s Space",
                "slug": SpaceBootstrapService._personal_slug(user),
                "kind": Space.Kind.PERSONAL,
                "owner": user,
                "created_by": user,
            },
        )
        SpaceMembership.objects.get_or_create(
            space=space,
            user=user,
            defaults={
                "role": SpaceMembership.Role.OWNER,
                "status": SpaceMembership.Status.ACTIVE,
            },
        )
        return space

    @staticmethod
    def _personal_slug(user):
        return f"personal-{user.pk}"


class SpacePermissionService:
    ADMIN_ROLES = {
        SpaceMembership.Role.OWNER,
        SpaceMembership.Role.MAINTAINER,
    }
    WRITE_ROLES = ADMIN_ROLES | {SpaceMembership.Role.USER}

    @staticmethod
    def membership(user, space):
        return SpaceMembership.objects.filter(
            user=user,
            space=space,
            status=SpaceMembership.Status.ACTIVE,
        ).first()

    @classmethod
    def can_manage(cls, membership):
        return bool(
            membership
            and membership.status == SpaceMembership.Status.ACTIVE
            and membership.role in cls.ADMIN_ROLES
        )

    @classmethod
    def can_write(cls, membership):
        return bool(
            membership
            and membership.status == SpaceMembership.Status.ACTIVE
            and membership.role in cls.WRITE_ROLES
        )

    @classmethod
    def can_read(cls, user, space):
        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False):
            return cls.has_active_takeover(user, space)
        return cls.membership(user, space) is not None

    @classmethod
    def can_upload(cls, user, space):
        if (
            not getattr(user, "is_authenticated", False)
            or space.status != Space.Status.ACTIVE
        ):
            return False
        if getattr(user, "is_staff", False):
            return cls.has_active_takeover(user, space)
        return cls.can_write(cls.membership(user, space))

    @classmethod
    def can_delete_resource(cls, user, space, uploaded_by_id):
        if (
            not getattr(user, "is_authenticated", False)
            or space.status != Space.Status.ACTIVE
        ):
            return False
        if getattr(user, "is_staff", False):
            return cls.has_active_takeover(user, space)
        membership = cls.membership(user, space)
        if not membership:
            return False
        return cls.can_manage(membership) or user.pk == uploaded_by_id

    @staticmethod
    def has_active_takeover(user, space):
        return SpaceTakeover.objects.filter(
            admin=user,
            space=space,
            active=True,
        ).exists()


@transaction.atomic
def invite_member(*, actor, space, user, role):
    space = Space.objects.select_for_update().get(pk=space.pk)
    membership = SpaceMembership.objects.filter(space=space, user=user).first()
    if membership and membership.status != SpaceMembership.Status.REMOVED:
        raise ValueError("User is already a space member or invited.")
    SpacePolicy.objects.get_or_create(singleton_key="default")
    policy = SpacePolicy.objects.select_for_update().get(
        singleton_key="default"
    )
    if policy.max_invited_users is not None:
        member_count = SpaceMembership.objects.filter(
            space=space,
            status__in=(
                SpaceMembership.Status.ACTIVE,
                SpaceMembership.Status.INVITED,
            ),
        ).exclude(user_id=space.owner_id).count()
        if member_count >= policy.max_invited_users:
            raise ValueError("The space member limit has been reached.")
    if membership:
        membership.role = role
        membership.status = SpaceMembership.Status.INVITED
        membership.invited_by = actor
        membership.joined_at = None
        membership.save(
            update_fields=(
                "role",
                "status",
                "invited_by",
                "joined_at",
                "updated_at",
            )
        )
    else:
        membership = SpaceMembership.objects.create(
            space=space,
            user=user,
            role=role,
            status=SpaceMembership.Status.INVITED,
            invited_by=actor,
        )
    audit_space_action(
        actor=actor,
        space=space,
        action="membership.invited",
        resource_type="user",
        resource_id=user.pk,
        metadata={"role": role},
    )
    return membership


@transaction.atomic
def takeover_space(*, admin, space, reason, owner_user=None):
    takeover = SpaceTakeover.objects.create(
        space=space,
        admin=admin,
        reason=reason,
    )
    if owner_user:
        membership, _ = SpaceMembership.objects.get_or_create(
            space=space,
            user=owner_user,
            defaults={
                "role": SpaceMembership.Role.OWNER,
                "status": SpaceMembership.Status.ACTIVE,
                "joined_at": timezone.now(),
            },
        )
        membership.role = SpaceMembership.Role.OWNER
        membership.status = SpaceMembership.Status.ACTIVE
        membership.joined_at = membership.joined_at or timezone.now()
        membership.save(
            update_fields=("role", "status", "joined_at", "updated_at")
        )
        space.owner = owner_user
        space.save(update_fields=("owner", "updated_at"))
    audit_space_action(
        actor=admin,
        space=space,
        action="space.taken_over",
        metadata={
            "reason": reason,
            "assigned_owner_id": owner_user.pk if owner_user else None,
        },
    )
    return takeover


@transaction.atomic
def transfer_space_ownership(*, actor, space, user):
    space = Space.objects.select_for_update().get(pk=space.pk)
    if space.kind == Space.Kind.PERSONAL:
        raise ValueError("Personal space ownership cannot be transferred.")
    if space.status != Space.Status.ACTIVE:
        raise ValueError("Space is not active.")
    if space.owner_id != actor.pk:
        raise PermissionError("Only the current owner can transfer ownership.")
    if user.pk == actor.pk:
        raise ValueError("The new owner must be another member.")
    target = SpaceMembership.objects.select_for_update().filter(
        space=space,
        user=user,
        status=SpaceMembership.Status.ACTIVE,
    ).first()
    if not target:
        raise ValueError("The new owner must be an active space member.")
    current_owner = SpaceMembership.objects.select_for_update().filter(
        space=space,
        user_id=space.owner_id,
        status=SpaceMembership.Status.ACTIVE,
        role=SpaceMembership.Role.OWNER,
    ).first()
    if not current_owner:
        raise ValueError("The current owner membership is missing.")
    current_owner.role = SpaceMembership.Role.MAINTAINER
    current_owner.save(update_fields=("role", "updated_at"))
    target.role = SpaceMembership.Role.OWNER
    target.save(update_fields=("role", "updated_at"))
    previous_owner_id = space.owner_id
    space.owner = user
    space.save(update_fields=("owner", "updated_at"))
    audit_space_action(
        actor=actor,
        space=space,
        action="space.ownership_transferred",
        resource_type="user",
        resource_id=user.pk,
        metadata={"previous_owner_id": previous_owner_id},
    )
    return space


def get_space_policy():
    policy, _ = SpacePolicy.objects.get_or_create(singleton_key="default")
    return policy


def audit_space_action(
    *, actor, space, action, resource_type="", resource_id="", metadata=None
):
    return SpaceAuditLog.objects.create(
        actor=actor,
        space=space,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else "",
        metadata=metadata or {},
    )
