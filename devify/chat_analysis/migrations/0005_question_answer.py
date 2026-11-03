import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chat_analysis', '0004_topic_subscription'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('question', models.CharField(max_length=2000)),
                ('scope', models.JSONField(blank=True, default=dict)),
                ('answer', models.TextField(blank=True)),
                ('citations', models.JSONField(blank=True, default=list)),
                ('usage', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('ready', 'Ready'), ('failed', 'Failed')], default='queued', max_length=20)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chat_questions', to=settings.AUTH_USER_MODEL)),
                ('space', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chat_questions', to='spaces.space')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [models.Index(fields=['space', 'created_by', 'created_at'], name='chat_analys_space_i_7063fe_idx'), models.Index(fields=['space', 'status', 'created_at'], name='chat_analys_space_i_5ca75a_idx')],
            },
        ),
    ]
