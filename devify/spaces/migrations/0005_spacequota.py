from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    dependencies = [("spaces", "0004_spaceworkflowconfig"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="SpaceQuota", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("max_members", models.PositiveIntegerField(blank=True, null=True)), ("storage_limit_bytes", models.PositiveBigIntegerField(blank=True, null=True)), ("daily_ai_calls", models.PositiveIntegerField(blank=True, null=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ("space", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="quota", to="spaces.space")),
        ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_space_quotas", to=settings.AUTH_USER_MODEL)),
    ])]
