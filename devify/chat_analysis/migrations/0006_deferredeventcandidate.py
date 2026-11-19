import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_analysis', '0005_questionanswer_thread'),
        ('chat_domain', '0001_initial'),
        ('spaces', '0002_space_uuid_primary_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeferredEventCandidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('ambiguous_target', 'Ambiguous target'), ('missing_context', 'Missing context'), ('conflicting_evidence', 'Conflicting evidence')], max_length=24)),
                ('question', models.CharField(max_length=300)),
                ('urgent', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')], default='pending', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='chat_domain.conversation')),
                ('message', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='chat_domain.message')),
                ('resolution_suggestion', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='chat_analysis.eventsuggestion')),
                ('resolved_event', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='chat_analysis.event')),
                ('space', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spaces.space')),
            ],
            options={
                'indexes': [models.Index(fields=['conversation', 'status', '-created_at', '-id'], name='defer_chat_status_recent'), models.Index(fields=['space', 'status', 'urgent', 'created_at'], name='defer_space_review')],
            },
        ),
    ]
