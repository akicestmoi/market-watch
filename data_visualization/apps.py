"""Django app config for data visualization."""

from django.apps import AppConfig


class DataVisualizationConfig(AppConfig):
    """App configuration for data visualization."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "data_visualization"
