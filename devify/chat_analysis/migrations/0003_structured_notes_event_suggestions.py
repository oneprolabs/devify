import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_analysis', '0002_report_snapshot'),
        ('spaces', '0003_spacetakeover'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='generation_version',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='note',
            name='structured_data',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='EventSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=500)),
                ('summary', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('analysis_job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_suggestions', to='chat_analysis.analysisjob')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_event_suggestions', to=settings.AUTH_USER_MODEL)),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suggestion_sources', to='chat_analysis.event')),
                ('note', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_suggestions', to='chat_analysis.note')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_event_suggestions', to=settings.AUTH_USER_MODEL)),
                ('space', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chat_event_suggestions', to='spaces.space')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [models.Index(fields=['space', 'status', 'created_at'], name='chat_analys_space_i_74a9a3_idx')],
                'constraints': [models.UniqueConstraint(fields=('analysis_job', 'note', 'event_key'), name='unique_chat_event_suggestion')],
            },
        ),
    ]
