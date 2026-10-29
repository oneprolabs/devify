from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Space",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("kind", models.CharField(choices=[("personal", "Personal"), ("team", "Team")], max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("suspended", "Suspended"), ("archived", "Archived")], default="active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_spaces", to=settings.AUTH_USER_MODEL)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_spaces", to=settings.AUTH_USER_MODEL)),
                ("personal_owner", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="personal_space", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name", "id")},
        ),
        migrations.CreateModel(
            name="SpacePolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.CharField(default="default", editable=False, max_length=20, unique=True)),
                ("allow_user_create_spaces", models.BooleanField(default=False)),
                ("max_invited_users", models.PositiveIntegerField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_space_policies", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SpaceAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=80)),
                ("resource_type", models.CharField(blank=True, max_length=80)),
                ("resource_id", models.CharField(blank=True, max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="space_audit_events", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="spaces.space")),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(fields=["space", "created_at"], name="spaces_spac_space_i_8958d5_idx"),
                    models.Index(fields=["actor", "created_at"], name="spaces_spac_actor_i_0f74de_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SpaceMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("owner", "Owner"), ("maintainer", "Maintainer"), ("user", "User"), ("guest", "Guest")], max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("invited", "Invited"), ("removed", "Removed")], default="active", max_length=20)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="space_invitations_sent", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="spaces.space")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="space_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "status"], name="spaces_spac_user_id_7d3d54_idx"),
                    models.Index(fields=["space", "status", "role"], name="spaces_spac_space_i_af7cbe_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("space", "user"), name="unique_space_membership")],
            },
        ),
    ]
