"""Django app config for economic overview."""

from importlib import import_module

from django.apps import AppConfig

_MODEL_MODULES = [
    "economic_overview.models.economic_indicators",
    "economic_overview.models.industry_profitability",
    "economic_overview.models.publication",
    "economic_overview.models.trade_ranking",
]


class EconomicOverviewConfig(AppConfig):
    """App configuration for economic overview."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "economic_overview"

    def ready(self) -> None:
        """Import model modules so Django registers every model."""
        for module_name in _MODEL_MODULES:
            import_module(module_name)
