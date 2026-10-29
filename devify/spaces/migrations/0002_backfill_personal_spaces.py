from django.conf import settings
from django.db import migrations


def create_personal_spaces(apps, schema_editor):
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split(".", 1)
    user_model = apps.get_model(user_app_label, user_model_name)
    space_model = apps.get_model("spaces", "Space")
    membership_model = apps.get_model("spaces", "SpaceMembership")

    database = schema_editor.connection.alias
    for user in user_model.objects.using(database).order_by("pk").iterator():
        space, _ = space_model.objects.using(database).get_or_create(
            personal_owner_id=user.pk,
            defaults={
                "name": f"{user.username[:112]}'s Space",
                "slug": f"personal-{user.pk}",
                "kind": "personal",
                "owner_id": user.pk,
                "created_by_id": user.pk,
            },
        )
        membership_model.objects.using(database).get_or_create(
            space_id=space.pk,
            user_id=user.pk,
            defaults={
                "role": "owner",
                "status": "active",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("spaces", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_personal_spaces, migrations.RunPython.noop),
    ]
