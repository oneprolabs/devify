from django.db import migrations, models
import spaces.models


class Migration(migrations.Migration):
    dependencies = [("spaces", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="spaceworkflowconfig",
            name="chat_analysis_preferences",
            field=models.JSONField(
                default=spaces.models.default_chat_analysis_preferences
            ),
        ),
    ]
