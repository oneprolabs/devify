from chat_sources.adapters import capabilities_for
from chat_sources.models import Source
from django.db import transaction

from spaces.services import SpacePermissionService, audit_space_action


@transaction.atomic
def get_or_create_upload_source(*, space, actor, channel_type, account_key):
    external_account_key = account_key or "unknown"
    provider = "tauri_upload"
    source, created = Source.objects.get_or_create(
        space=space,
        channel_type=channel_type,
        provider=provider,
        external_account_key=external_account_key,
        defaults={
            "display_name": external_account_key,
            "capabilities": capabilities_for(channel_type, provider),
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if created:
        audit_space_action(
            actor=actor,
            space=space,
            action="chat.source_created",
            resource_type="source",
            resource_id=source.pk,
            metadata={
                "channel_type": channel_type,
                "provider": provider,
            },
        )
    return source


def can_manage_source(user, source):
    if getattr(user, "is_staff", False):
        return SpacePermissionService.has_active_takeover(user, source.space)
    membership = SpacePermissionService.membership(user, source.space)
    return SpacePermissionService.can_manage(membership)
