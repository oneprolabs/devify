from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feedback"
    verbose_name = "问题反馈"

    def ready(self):
        from feedback import signals  # noqa: F401
