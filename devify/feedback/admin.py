from django.contrib import admin

from feedback.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "category",
        "status",
        "assigned_to",
        "created_at",
    ]
    list_filter = ["status", "category"]
    search_fields = ["description", "user__username"]
    readonly_fields = [
        "id",
        "user",
        "client_id",
        "fingerprint",
        "category",
        "description",
        "contact",
        "context",
        "diagnostics",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
