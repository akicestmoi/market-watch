"""Asset, market-price, holiday, and price-update-log models."""

from enum import Enum

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import (
    BaseLogModel,
    BaseModel,
    get_choice_from_label,
    get_choice_labels,
)
from market_overview.models.common import LocationChoices


class AssetClassChoices(models.TextChoices):
    """Broad asset classes used in the market overview catalog."""

    STOCKS = "STOCKS", _("Stocks")
    RATES = "RATES", _("Interest Rates")
    FX = "FX", _("Exchange Rates")
    CRYPTO = "CRYPTO", _("Crypto Exchange Rates")
    COMMODITIES = "COMMODITIES", _("Commodities")
    OTHERS = "OTHERS", _("Others")

    @classmethod
    def from_label(cls, label: str) -> "AssetClassChoices":
        """Return the asset-class choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in declaration order."""
        return get_choice_labels(cls)


class AssetTypeChoices(models.TextChoices):
    """Finer instrument types within an asset class."""

    EQUITY_INDEX = "EQUITY_INDEX", _("Equity Index")
    INTERBANK_RATE = "INTERBANK_RATE", _("Interbank Rate")
    GOVERNMENT_BOND_RATE = "GOVERNMENT_BOND_RATE", _("Government Bond Rate")
    FX_SPOT_RATE = "FX_SPOT_RATE", _("FX Spot Rate")
    CRYPTO_SPOT_RATE = "CRYPTO_SPOT_RATE", _("Cryptocurrency Spot Rate")
    COMMODITIY_FUTURE_SPOT_PRICE = "COMMODITIY_FUTURE_SPOT_PRICE", _(
        "Commodity Future Spot Price"
    )
    VOLATILITY_INDEX = "VOLATILITY_INDEX", _("Volatility Index")


class PriceSourceChoices(models.TextChoices):
    """Where we fetch market prices from for each asset."""

    GOV_TREASURY_DEPT = "GOV_TREASURY_DEPT", _("US Treasury Department")
    NYFED = "NYFED", _("New York Federal Reserve")
    WEBSTAT = "WEBSTAT", _("Webstat, Banque de France")
    BUNDESBANK = "BUNDESBANK", _("Deutsche Bundesbank")
    BOJ = "BOJ", _("Bank of Japan")
    BB = "BB", _("Japan Bond Trading")
    GLOBAL_RATES = "GLOBAL_RATES", _("GlobalRates.com")
    YAHOO = "YAHOO", _("Yahoo Finance")


class SpecialComment(str, Enum):
    """Special comment enum."""

    BANK_HOLIDAY = "Bank holiday"


class AssetModel(BaseModel):
    """One tradable or reference instrument in the market catalog."""

    asset_id = models.IntegerField(
        help_text="Fixed numeric id from the asset catalog file.",
    )
    asset_class = models.CharField(
        max_length=50,
        choices=AssetClassChoices.choices,
        help_text="Broad asset class (stocks, rates, FX, crypto, commodities, …).",
    )
    location = models.CharField(
        max_length=2,
        choices=LocationChoices.choices,
        null=True,
        blank=True,
        help_text="Market / economy location when the asset is region-specific.",
    )
    short_name = models.CharField(
        max_length=100,
        primary_key=True,
        help_text="Short asset code used as primary key (e.g. SPX, US10Y).",
    )
    full_name = models.CharField(
        max_length=100,
        help_text="Full asset name shown in the UI.",
    )
    maturity = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Bond or rate maturity in years when the asset has one; "
            "empty for other instrument types."
        ),
    )
    asset_type = models.CharField(
        max_length=100,
        choices=AssetTypeChoices.choices,
        null=True,
        blank=True,
        default=None,
        help_text="Finer instrument type within the asset class.",
    )
    ticker = models.CharField(
        max_length=100,
        help_text="Publisher series code used when fetching prices.",
    )
    source = models.CharField(
        max_length=100,
        choices=PriceSourceChoices.choices,
        help_text="Where we fetch prices for this asset from.",
    )

    def __str__(self):
        return f"{self.short_name}"


class MarketPriceModel(BaseModel):
    """One settled or last price for an asset on a calendar day."""

    asset = models.ForeignKey(
        AssetModel,
        db_column="asset_short_name",
        on_delete=models.CASCADE,
        related_name="market_prices",
        help_text="Asset this price belongs to.",
    )
    date = models.DateField(
        help_text="Price date (calendar day).",
    )
    price = models.FloatField(
        null=True,
        blank=True,
        help_text="Settled or last price. Empty when missing.",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        default="",
        help_text="Optional note from fetching or saving (for example a bank holiday).",
    )

    class Meta:
        """Market price model metadata (unique per asset and date)."""

        constraints = [
            models.UniqueConstraint(
                fields=["asset", "date"],
                name="unique_market_price_per_asset_date",
            )
        ]

    def convert_to_dict(
        self,
        remove_foreign_key: bool = False,
        remove_auto_fields: bool = True,
        remove_cache_fields: bool = True,
        remove_specific_fields: list[str] = [],
    ) -> (
        dict
    ):  # Usage of dict: field keys vary by Django model until per-model TypedDicts exist.
        """Override convert_to_dict to include asset identifiers."""
        data = super().convert_to_dict(
            remove_foreign_key=remove_foreign_key,
            remove_auto_fields=remove_auto_fields,
            remove_cache_fields=remove_cache_fields,
            remove_specific_fields=remove_specific_fields,
        )
        asset = getattr(self, "asset", None)
        if asset and not remove_foreign_key:
            data["asset_id"] = asset.asset_id
            data["asset_short_name"] = asset.short_name
        return data


class PriceUpdateLogModel(BaseLogModel):
    """Change log for one market price update."""

    fk_name = "market_price"
    market_price = models.ForeignKey(
        "MarketPriceModel",
        on_delete=models.CASCADE,
        related_name="price_update_logs",
        help_text="Market price this update log belongs to.",
    )


class HolidayModel(BaseModel):
    """One market holiday on a calendar day for a location."""

    date = models.DateField(
        help_text="Calendar day of the market holiday.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Holiday display name (e.g. New Year's Day).",
    )
    location = models.CharField(
        max_length=100,
        choices=LocationChoices.choices,
        help_text="Market location for which this day is a holiday.",
    )
