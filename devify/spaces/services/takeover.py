"""Administrative space takeover operations."""

from django.db import transaction
from django.utils import timezone

from spaces.models import SpaceMembership, SpaceTakeover
from spaces.services.audit import audit_space_action


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
