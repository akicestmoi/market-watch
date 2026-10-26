"""Django app config for the core project package."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """App configuration for the core project package."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
