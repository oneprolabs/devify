import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_ingestion', '0001_initial'),
        ('chat_sources', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadbatch',
            name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='upload_batches', to='chat_sources.source'),
        ),
    ]
