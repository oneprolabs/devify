from importlib import import_module

from django.apps import AppConfig


class SpacesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "spaces"

    def ready(self):
        import_module("spaces.signals")
