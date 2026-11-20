"""Shared market-overview choices used by more than one domain module."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import get_choice_from_label, get_choice_labels


class LocationChoices(models.TextChoices):
    """Market and economy location codes for assets and prices."""

    US = "US", _("United States")
    EU = "EU", _("Europe")
    DE = "DE", _("Germany")
    FR = "FR", _("France")
    JP = "JP", _("Japan")

    @classmethod
    def from_label(cls, label: str) -> "LocationChoices":
        """Return the location choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["LocationChoices"]:
        """Ordered list of location choices."""
        order = ["US", "EU", "DE", "FR", "JP"]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in 'ordered()' order."""
        return get_choice_labels(cls)


class EquityIndexChoices(models.TextChoices):
    """Equity index whose single-name basket we rebuild for sector analysis."""

    SPX = "SPX", _("S&P 500")
    CAC40 = "CAC40", _("CAC 40")
    NIKKEI225 = "NIKKEI225", _("Nikkei 225")

    @classmethod
    def from_label(cls, label: str) -> "EquityIndexChoices":
        """Return the equity-index choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in declaration order."""
        return get_choice_labels(cls)
