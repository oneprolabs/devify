import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chat_analysis', '0003_structured_notes_event_suggestions'),
        ('spaces', '0003_spacetakeover'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TopicSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('instruction', models.TextField()),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('include_open', models.BooleanField(default=True)),
                ('period', models.CharField(choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month')], default='week', max_length=10)),
                ('time_local', models.TimeField(blank=True, null=True)),
                ('timezone', models.CharField(default='Asia/Shanghai', max_length=64)),
                ('enabled', models.BooleanField(default=True)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chat_topic_subscriptions', to=settings.AUTH_USER_MODEL)),
                ('space', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chat_topic_subscriptions', to='spaces.space')),
            ],
            options={
                'ordering': ('-updated_at', '-id'),
                'indexes': [models.Index(fields=['space', 'enabled', 'updated_at'], name='chat_analys_space_i_f47172_idx'), models.Index(fields=['created_by', 'space'], name='chat_analys_created_32bb0a_idx')],
                'constraints': [models.UniqueConstraint(fields=('space', 'created_by', 'title'), name='unique_chat_topic_title')],
            },
        ),
    ]
