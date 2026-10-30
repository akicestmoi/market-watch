"""Config for visualization services."""

from enum import Enum

from economic_overview.models import EconomicDataLocationChoices
from market_overview.models import LocationChoices

# ---------------------------------------------------------------------------
# Economic recap
# ---------------------------------------------------------------------------
"""Country columns shown on the Economic Recap table."""

ECONOMIC_RECAP_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
]
# Absolute observations kept per indicator for client Abs/QoQ/YoY (monthly YoY
# needs 12 lookback + a few points for Previous).
TIME_SERIES_HISTORY_WINDOW = 16

# ---------------------------------------------------------------------------
# Economic charts
# ---------------------------------------------------------------------------
"""Regions and EU country series for the Economic Charts page.

Europe stays a top-level region. Under Europe, each country-indicator pair is its own
selectable curve (DE / ES / IT / FR; same order as the default selection). France
also remains a standalone top-level region.
"""

ECONOMIC_CHARTS_LOCATIONS: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.US,
    EconomicDataLocationChoices.EU,
    EconomicDataLocationChoices.FR,
    EconomicDataLocationChoices.JP,
]
# Country series under Europe (selectable curves and default selection order).
ECONOMIC_CHARTS_EU_COUNTRIES: list[EconomicDataLocationChoices] = [
    EconomicDataLocationChoices.DE,
    EconomicDataLocationChoices.ES,
    EconomicDataLocationChoices.IT,
    EconomicDataLocationChoices.FR,
]
# Default confidence indicator type per single-region chart location (EU has none).
ECONOMIC_CHARTS_DEFAULT_CONFIDENCE_TYPE_BY_LOCATION: dict[
    EconomicDataLocationChoices, str
] = {
    EconomicDataLocationChoices.US: "Consumer Confidence",
    EconomicDataLocationChoices.FR: "Aggregate Business Confidence",
    EconomicDataLocationChoices.JP: "Manufacturing Business Confidence",
}

# ---------------------------------------------------------------------------
# Geographic grouping
# ---------------------------------------------------------------------------
"""Market-recap location buckets (North America / Europe / Asia)."""


class MarketRecapLocationEnum(str, Enum):
    """Geographic buckets for the market-recap price table only."""

    NA = "North America"
    EU = "Europe"
    ASIA = "Asia"
    NO_LOCATION = "No Location"

    def get_locations(self) -> list[LocationChoices]:
        """Return market locations that belong to this geographic group."""
        match self:
            case MarketRecapLocationEnum.NA:
                return [LocationChoices.US]
            case MarketRecapLocationEnum.EU:
                return [
                    LocationChoices.EU,
                    LocationChoices.DE,
                    LocationChoices.FR,
                ]
            case MarketRecapLocationEnum.ASIA:
                return [LocationChoices.JP]
            case MarketRecapLocationEnum.NO_LOCATION:
                return []


# ---------------------------------------------------------------------------
# FX matrix
# ---------------------------------------------------------------------------
"""Cross pairs to show and currency column order for the FX strength matrix."""

FX_PAIRS_FILTER = [
    "EURGBP",
    "EURCHF",
    "EURAUD",
    "EURCNY",
    "GBPJPY",
    "GBPCHF",
    "GBPAUD",
    "GBPCNY",
    "JPYCHF",
    "JPYAUD",
    "JPYCNY",
    "CHFAUD",
    "CHFCNY",
    "AUDCNY",
]
FX_MATRIX_ORDER = ["EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CNY"]
