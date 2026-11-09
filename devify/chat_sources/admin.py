from chat_sources.models import Source, SourceImport
from django.contrib import admin


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "space",
        "channel_type",
        "provider",
        "display_name",
        "status",
    )
    list_filter = ("channel_type", "provider", "status")
    search_fields = ("display_name", "external_account_key")
    readonly_fields = [field.name for field in Source._meta.fields]


@admin.register(SourceImport)
class SourceImportAdmin(admin.ModelAdmin):
    list_display = ("id", "space", "source", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = [field.name for field in SourceImport._meta.fields]
