import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chat_analysis', '0005_question_answer'),
        ('spaces', '0003_spacetakeover'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EventTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag_key', models.CharField(max_length=120)),
                ('label', models.CharField(max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_chat_event_tags', to=settings.AUTH_USER_MODEL)),
                ('space', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chat_event_tags', to='spaces.space')),
            ],
            options={'ordering': ('label', 'id'), 'indexes': [models.Index(fields=['space', 'label'], name='chat_analys_space_i_8392db_idx')], 'constraints': [models.UniqueConstraint(fields=('space', 'tag_key'), name='unique_chat_event_tag_key')]},
        ),
        migrations.CreateModel(
            name='EventTagAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_event_tag_assignments', to=settings.AUTH_USER_MODEL)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tag_assignments', to='chat_analysis.event')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_assignments', to='chat_analysis.eventtag')),
            ],
            options={'ordering': ('id',), 'indexes': [models.Index(fields=['tag', 'event'], name='chat_analys_tag_id_782924_idx')], 'constraints': [models.UniqueConstraint(fields=('event', 'tag'), name='unique_chat_event_tag_assignment')]},
        ),
    ]
