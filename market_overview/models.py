from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.models import BaseLogModel, BaseModel


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
    def from_label(cls, label) -> str:
        for choice in cls:
            if choice.label == label:
                return str(choice.value)
        raise ValueError(
            f"Choice does not exist, available choices: {[choice.value for choice in LocationChoices]}"
        )


class SourceChoices(models.TextChoices):
    """Source Choices."""

    GOV_TREASURY_DEPT = "GOV_TREASURY_DEPT", _("US Treasury Department")
    NYFED = "NYFED", _("New York Federal Reserve")
    FRED = "FRED", _("Federal Reserve Bank of St Louis")
    WEBSTAT = "WEBSTAT", _("Webstat, Banque de France")
    BUNDESBANK = "BUNDESBANK", _("Deutsche Bundesbank")
    BOJ = "BOJ", _("Bank of Japan")
    BB = "BB", _("Japan Bond Trading")
    GLOBAL_RATES = "GLOBAL_RATES", _("GlobalRates.com")
    YAHOO = "YAHOO", _("Yahoo Finance")


class MarketPriceModel(BaseModel):
    """Market Price Model."""

    date = models.DateField()
    asset_class = models.CharField(max_length=50, choices=AssetClassChoices.choices)
    location = models.CharField(
        max_length=2, choices=LocationChoices.choices, null=True, blank=True
    )
    short_name = models.CharField(max_length=100, default="")
    full_name = models.CharField(max_length=100, default="")
    price = models.FloatField(null=True, blank=True)
    maturity = models.FloatField(null=True, blank=True)
    asset_type = models.CharField(
        max_length=100,
        choices=AssetTypeChoices.choices,
        null=True,
        blank=True,
        default=None,
    )
    source = models.CharField(max_length=100, choices=SourceChoices.choices)
    comment = models.TextField(null=True, blank=True, default="")

    class Meta:
        unique_together = ("short_name", "date")

    def __str__(self):
        return f"{self.short_name}_({self.date})"


class PriceUpdateLogModel(BaseLogModel):
    """Price Update Log Model."""

    fk_name = "asset"
    asset = models.ForeignKey(
        "MarketPriceModel", on_delete=models.CASCADE, related_name="price_update_logs"
    )
