import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_profile_language'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TauriAuthorizationCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_hash', models.CharField(max_length=128, unique=True)),
                ('client_id', models.CharField(max_length=100)),
                ('redirect_uri', models.CharField(max_length=500)),
                ('code_challenge', models.CharField(max_length=128)),
                ('device_label', models.CharField(blank=True, max_length=120)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tauri_authorization_codes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['user', 'created_at'], name='accounts_ta_user_id_e5b7ef_idx'), models.Index(fields=['expires_at', 'used_at'], name='accounts_ta_expires_c4ee53_idx')],
            },
        ),
    ]
