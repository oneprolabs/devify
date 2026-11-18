from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chat_analysis", "0004_analysisjobmessage_error"),
    ]

    operations = [
        migrations.AddField(
            model_name="questionanswer",
            name="thread",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="turns",
                to="chat_analysis.questionanswer",
            ),
        ),
    ]
