"""Space invitation and ownership operations."""

from django.db import transaction

from spaces.models import Space, SpaceMembership, SpacePolicy
from spaces.services.audit import audit_space_action


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
        member_count = (
            SpaceMembership.objects.filter(
                space=space,
                status__in=(
                    SpaceMembership.Status.ACTIVE,
                    SpaceMembership.Status.INVITED,
                ),
            )
            .exclude(user_id=space.owner_id)
            .count()
        )
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
    target = (
        SpaceMembership.objects.select_for_update()
        .filter(
            space=space,
            user=user,
            status=SpaceMembership.Status.ACTIVE,
        )
        .first()
    )
    if not target:
        raise ValueError("The new owner must be an active space member.")
    current_owner = (
        SpaceMembership.objects.select_for_update()
        .filter(
            space=space,
            user_id=space.owner_id,
            status=SpaceMembership.Status.ACTIVE,
            role=SpaceMembership.Role.OWNER,
        )
        .first()
    )
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
