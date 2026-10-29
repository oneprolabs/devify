from django.contrib import admin

from spaces.models import Space, SpaceAuditLog, SpaceMembership, SpacePolicy


class ReadOnlyModelAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Space)
class SpaceAdmin(ReadOnlyModelAdmin):
    list_display = ("id", "name", "kind", "owner", "status", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("name", "slug")


@admin.register(SpaceMembership)
class SpaceMembershipAdmin(ReadOnlyModelAdmin):
    list_display = ("space", "user", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("space__name", "user__username", "user__email")


@admin.register(SpacePolicy)
class SpacePolicyAdmin(ReadOnlyModelAdmin):
    list_display = (
        "singleton_key",
        "allow_user_create_spaces",
        "max_invited_users",
    )


@admin.register(SpaceAuditLog)
class SpaceAuditLogAdmin(ReadOnlyModelAdmin):
    list_display = (
        "created_at",
        "actor",
        "space",
        "action",
        "resource_type",
        "resource_id",
    )
    list_filter = ("action", "resource_type")
    search_fields = ("action", "resource_type", "resource_id")
