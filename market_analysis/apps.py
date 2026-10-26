"""Django app config for market analysis."""

from django.apps import AppConfig


class MarketAnalysisConfig(AppConfig):
    """App configuration for market analysis."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "market_analysis"
    verbose_name = "Market Analysis"
