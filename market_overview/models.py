from typing import List, cast

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseLogModel, BaseModel


class AssetClassChoices(models.TextChoices):
    """Asset Class Choices."""

    STOCKS = "STOCKS", _("Stocks")
    RATES = "RATES", _("Interest Rates")
    FX = "FX", _("Exchange Rates")
    CRYPTO = "CRYPTO", _("Crypto Exchange Rates")
    COMMODITIES = "COMMODITIES", _("Commodities")
    OTHERS = "OTHERS", _("Others")


class AssetTypeChoices(models.TextChoices):
    """Asset Type Choices."""

    EQUITY_INDEX = "EQUITY_INDEX", _("Equity Index")
    INTERBANK_RATE = "INTERBANK_RATE", _("Interbank Rate")
    GOVERNMENT_BOND_RATE = "GOVERNMENT_BOND_RATE", _("Government Bond Rate")
    FX_SPOT_RATE = "FX_SPOT_RATE", _("FX Spot Rate")
    CRYPTO_SPOT_RATE = "CRYPTO_SPOT_RATE", _("Cryptocurrency Spot Rate")
    COMMODITIY_FUTURE_SPOT_PRICE = "COMMODITIY_FUTURE_SPOT_PRICE", _(
        "Commodity Future Spot Price"
    )
    VOLATILITY_INDEX = "VOLATILITY_INDEX", _("Volatility Index")


class LocationChoices(models.TextChoices):
    """Location Choices."""

    US = "US", _("United States")
    EU = "EU", _("Europe")
    DE = "DE", _("Germany")
    FR = "FR", _("France")
    JP = "JP", _("Japan")

    @classmethod
    def from_label(cls, label) -> "LocationChoices":
        for choice in cls:
            if choice.label == label:
                return cast(LocationChoices, choice.value)
        raise ValueError(
            f"Choice does not exist, available choices: {[choice.value for choice in LocationChoices]}"
        )

    @classmethod
    def ordered(cls) -> List["LocationChoices"]:
        """Ordered list of economic data location choices."""
        order = ["US", "EU", "DE", "FR", "JP"]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> List[str]:
        """Get labels of location choices."""
        return [cast(str, choice.label) for choice in cls.ordered()]


class PriceSourceChoices(models.TextChoices):
    """Price Source Choices."""

    GOV_TREASURY_DEPT = "GOV_TREASURY_DEPT", _("US Treasury Department")
    NYFED = "NYFED", _("New York Federal Reserve")
    FRED = "FRED", _("Federal Reserve Bank of St Louis")
    WEBSTAT = "WEBSTAT", _("Webstat, Banque de France")
    BUNDESBANK = "BUNDESBANK", _("Deutsche Bundesbank")
    BOJ = "BOJ", _("Bank of Japan")
    BB = "BB", _("Japan Bond Trading")
    GLOBAL_RATES = "GLOBAL_RATES", _("GlobalRates.com")
    YAHOO = "YAHOO", _("Yahoo Finance")


class AssetModel(BaseModel):
    """Asset Model."""

    id = models.IntegerField(unique=True)
    asset_class = models.CharField(max_length=50, choices=AssetClassChoices.choices)
    location = models.CharField(
        max_length=2, choices=LocationChoices.choices, null=True, blank=True
    )
    short_name = models.CharField(max_length=100, primary_key=True)
    full_name = models.CharField(max_length=100)
    maturity = models.FloatField(null=True, blank=True)
    asset_type = models.CharField(
        max_length=100,
        choices=AssetTypeChoices.choices,
        null=True,
        blank=True,
        default=None,
    )
    ticker = models.CharField(max_length=100)
    source = models.CharField(max_length=100, choices=PriceSourceChoices.choices)

    def __str__(self):
        return f"{self.short_name}"


class MarketPriceModel(BaseModel):
    """Market Price Model."""

    asset = models.ForeignKey(
        AssetModel,
        to_field="short_name",
        db_column="asset_short_name",
        on_delete=models.CASCADE,
        related_name="market_prices",
    )
    date = models.DateField()
    price = models.FloatField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True, default="")

    def convert_to_dict(self, remove_foreign_key: bool = False) -> dict:
        """Override convert_to_dict to include asset identifiers."""
        data = super().convert_to_dict(remove_foreign_key=remove_foreign_key)
        asset = getattr(self, "asset", None)
        if asset:
            data["asset_id"] = asset.id
            data["asset_short_name"] = asset.short_name
        return data


class PriceUpdateLogModel(BaseLogModel):
    """Price Update Log Model."""

    fk_name = "market_price"
    market_price = models.ForeignKey(
        "MarketPriceModel", on_delete=models.CASCADE, related_name="price_update_logs"
    )
