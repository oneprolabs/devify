"""Space audit entry creation."""

from spaces.models import SpaceAuditLog


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
