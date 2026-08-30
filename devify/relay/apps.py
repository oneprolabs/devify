"""Django app config for Relay."""

from django.apps import AppConfig


class RelayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "relay"
    verbose_name = "Relay"

    def ready(self):
        from django.utils.translation import gettext_lazy as _

        from core.app_registry import APP_REGISTRY

        import relay.tasks  # noqa: F401
        import relay.celery_bootstrap  # noqa: F401

        APP_REGISTRY.register(
            key="relay",
            name=_("Relay"),
            name_zh=_("智能投递"),
            path="/apps/relay",
            description=_("Route workflow completions to external tools."),
            order=10,
        )
