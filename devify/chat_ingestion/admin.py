from django.contrib import admin

from chat_ingestion.models import UploadBatch, UploadItem


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id", "space", "uploaded_by", "source_type", "status", "created_at"
    )
    list_filter = ("source_type", "status")
    search_fields = ("idempotency_key", "archive_sha256", "source_account_id")
    readonly_fields = [field.name for field in UploadBatch._meta.fields]


@admin.register(UploadItem)
class UploadItemAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "path", "status", "message_count")
    list_filter = ("status",)
    search_fields = ("path", "sha256")
    readonly_fields = [field.name for field in UploadItem._meta.fields]
