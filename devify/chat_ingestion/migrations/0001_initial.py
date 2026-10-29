import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("spaces", "0003_spacetakeover"),
    ]
    operations = [
        migrations.CreateModel(
            name="UploadBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("source_type", models.CharField(choices=[("wechat", "WeChat"), ("whatsapp", "WhatsApp"), ("line", "LINE")], max_length=20)),
                ("source_account_id", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.CharField(max_length=255)),
                ("archive_sha256", models.CharField(blank=True, max_length=64)),
                ("archive_size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("created", "Created"), ("uploading", "Uploading"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="created", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("message_count", models.PositiveIntegerField(default=0)),
                ("duplicate_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="chat_upload_batches", to="spaces.space")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="chat_upload_batches", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(fields=["space", "status"], name="chat_ingest_space_i_f8629a_idx"),
                    models.Index(fields=["uploaded_by", "created_at"], name="chat_ingest_uploade_1251a8_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("space", "uploaded_by", "idempotency_key"), name="unique_chat_upload_idempotency")],
            },
        ),
        migrations.CreateModel(
            name="UploadItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(max_length=500)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("sha256", models.CharField(blank=True, max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("duplicate", "Duplicate"), ("failed", "Failed")], default="pending", max_length=20)),
                ("message_count", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="chat_ingestion.uploadbatch")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("batch", "path"), name="unique_chat_upload_item_path")],
            },
        ),
    ]
