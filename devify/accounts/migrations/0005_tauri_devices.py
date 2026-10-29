import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_tauri_authorization_code'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TauriDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_id', models.CharField(max_length=100)),
                ('label', models.CharField(blank=True, max_length=120)),
                ('platform', models.CharField(blank=True, max_length=40)),
                ('status', models.CharField(choices=[('active', 'Active'), ('revoked', 'Revoked')], default='active', max_length=20)),
                ('last_seen_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tauri_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['user', 'status', 'last_seen_at'], name='accounts_ta_user_id_a56fc2_idx')],
                'constraints': [models.UniqueConstraint(fields=('user', 'device_id'), name='unique_tauri_device')],
            },
        ),
    ]
