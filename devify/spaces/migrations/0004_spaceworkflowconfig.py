from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("spaces", "0003_spacetakeover"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="SpaceWorkflowConfig", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("text_llm_config_uuid", models.UUIDField(blank=True, null=True)), ("image_llm_config_uuid", models.UUIDField(blank=True, null=True)),
        ("language", models.CharField(default="zh-CN", max_length=32)), ("scene", models.CharField(default="chat", max_length=80)),
        ("prompt_overrides", models.JSONField(blank=True, default=dict)), ("attachment_policy", models.CharField(default="available", max_length=32)),
        ("auto_process", models.BooleanField(default=True)), ("processing_paused", models.BooleanField(default=False)), ("version", models.PositiveIntegerField(default=1)),
        ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ("space", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="workflow_config", to="spaces.space")),
        ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_space_workflow_configs", to=settings.AUTH_USER_MODEL)),
    ])]
