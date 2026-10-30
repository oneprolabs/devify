from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_tauri_devices"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name="TauriAuthorizationCode", new_name="DesktopAuthorizationCode"),
        migrations.RenameModel(old_name="TauriDevice", new_name="DesktopDevice"),
        migrations.AlterField(
            model_name="desktopauthorizationcode",
            name="user",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="desktop_authorization_codes", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="desktopdevice",
            name="user",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="desktop_devices", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameIndex(model_name="desktopauthorizationcode", old_name="accounts_ta_user_id_e5b7ef_idx", new_name="accounts_de_user_id_dbadb7_idx"),
        migrations.RenameIndex(model_name="desktopauthorizationcode", old_name="accounts_ta_expires_c4ee53_idx", new_name="accounts_de_expires_fd16d6_idx"),
        migrations.RenameIndex(model_name="desktopdevice", old_name="accounts_ta_user_id_a56fc2_idx", new_name="accounts_de_user_id_28002f_idx"),
        migrations.RemoveConstraint(model_name="desktopdevice", name="unique_tauri_device"),
        migrations.AddConstraint(
            model_name="desktopdevice",
            constraint=models.UniqueConstraint(fields=("user", "device_id"), name="unique_desktop_device"),
        ),
    ]
