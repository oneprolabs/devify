from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("chat_analysis", "0006_event_tags")]
    operations = [migrations.AlterField(model_name="analysisjob", name="state", field=models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("ready", "Ready"), ("partial", "Partial"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="queued", max_length=20))]
