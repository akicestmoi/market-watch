from typing import List

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseLogModel, BaseModel
from market_overview.models import LocationChoices


class CentralBankChoices(models.TextChoices):
    """Central Bank Choices."""

    FRB = "FRB", _("Federal Reserve (FRB)")
    BOJ = "BOJ", _("Bank of Japan (BOJ)")
    ECB = "ECB", _("European Central Bank (ECB)")

    @classmethod
    def ordered(cls) -> List["CentralBankChoices"]:
        """Ordered list of economic data location choices."""
        order = ["FRB", "ECB", "BOJ"]
        return [cls[value] for value in order]


CENTRAL_BANK_LOCATION_MAP = {
    CentralBankChoices.FRB: LocationChoices.US,
    CentralBankChoices.BOJ: LocationChoices.JP,
    CentralBankChoices.ECB: LocationChoices.EU,
}


class CentralBankMeetingModel(BaseModel):
    """Central Bank Meeting Model."""

    central_bank = models.CharField(max_length=255, choices=CentralBankChoices.choices)
    order = models.IntegerField()
    date = models.DateTimeField()


class CentralBankDataModel(BaseModel):
    """Central Bank Data Model."""

    cb_data_id = models.IntegerField(default=None, null=True, blank=True)
    central_bank = models.CharField(max_length=255, choices=CentralBankChoices.choices)
    short_name = models.CharField(max_length=255, default="")
    full_name = models.CharField(max_length=255)
    date = models.DateField()
    value = models.FloatField(null=True, blank=True, default=None)
    comment = models.TextField(null=True, blank=True, default="")


class StirFuturesNameChoices(models.TextChoices):
    """Stir Futures Name Choices."""

    FF1M = "FF1M", _("1 Month Fed Funds STIR Futures")
    ESTR3M = "ESTR3M", _("3 Month ESTR Futures")
    MUTAN3M = "MUTAN3M", _("3 Month Mutan STIR Futures")


class StirFuturesSourceChoices(models.TextChoices):
    """Stir Futures Source Choices."""

    YAHOO = "YAHOO", _("Yahoo Finance")
    TFX = "TFX", _("TFX")
    PDF = "PDF", _("PDF")


class StirFuturesModel(BaseModel):
    """Stir Futures Model."""

    central_bank = models.CharField(max_length=255, choices=CentralBankChoices.choices)
    short_name = models.CharField(
        max_length=255, choices=StirFuturesNameChoices.choices
    )
    full_name = models.CharField(max_length=255)
    maturity = models.TextField(blank=True, null=True)
    first_accrual_date = models.DateField(null=True, blank=True, default=None)
    last_accrual_date = models.DateField(null=True, blank=True, default=None)
    date = models.DateField()
    price = models.FloatField(null=True, blank=True, default=None)
    source = models.CharField(max_length=255, choices=StirFuturesSourceChoices.choices)
    comment = models.TextField(null=True, blank=True, default="")


class StirFuturesPriceUpdateLogModel(BaseLogModel):
    """Stir Futures Price Update Log Model."""

    fk_name = "stir_futures"
    stir_futures = models.ForeignKey(
        "StirFuturesModel",
        on_delete=models.CASCADE,
        related_name="stir_futures_price_update_logs",
    )
