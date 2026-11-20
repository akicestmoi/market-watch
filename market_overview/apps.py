"""Django app config for market overview."""

from importlib import import_module

from django.apps import AppConfig

_MODEL_MODULES = [
    "market_overview.models.market_prices",
    "market_overview.models.sector_analysis",
    "market_overview.models.earnings",
]


class MarketOverviewConfig(AppConfig):
    """App configuration for market overview."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "market_overview"

    def ready(self) -> None:
        """Import model modules so Django registers every model."""
        for module_name in _MODEL_MODULES:
            import_module(module_name)
