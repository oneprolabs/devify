import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ThreadlineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "threadline"
    app_label = "threadline"

    def ready(self):
        """Register signal handlers when the app is ready."""
        logger.info("ThreadlineConfig.ready() called")
        # Celery autodiscovery only imports the package entrypoint.
        # Import the concrete task modules explicitly so shared_task
        # decorators register every Threadline task in the worker registry.
        import threadline.tasks.email_merge  # noqa: F401
        import threadline.tasks.email_fetch  # noqa: F401
        import threadline.tasks.email_workflow  # noqa: F401
        import threadline.tasks.notifications  # noqa: F401
        import threadline.tasks.scheduler  # noqa: F401

        # Todos are a threadline feature, but the app centre lists them
        # beside Relay and Expense, so they register the same way.
        from django.utils.translation import gettext_lazy as _

        from core.app_registry import APP_REGISTRY
        from threadline.stats import todo_stats

        APP_REGISTRY.register(
            key="todos",
            name=_("Todos"),
            name_zh=_("待办事项"),
            path="/todos",
            description=_(
                "Collect the follow-ups a conversation produced in one "
                "place."
            ),
            order=30,
            stats=todo_stats,
        )
