"""Central bank, meeting, STIR futures, and related data models."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import (
    BaseLogModel,
    BaseModel,
    get_choice_from_label,
    get_choice_labels,
)
from market_overview.models import LocationChoices


class CentralBankChoices(models.TextChoices):
    """Central Bank Choices."""

    FRB = "FRB", _("Federal Reserve (FRB)")
    BOJ = "BOJ", _("Bank of Japan (BOJ)")
    ECB = "ECB", _("European Central Bank (ECB)")

    @classmethod
    def from_label(cls, label: str) -> "CentralBankChoices":
        """Return the central-bank choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["CentralBankChoices"]:
        """Ordered list of central bank choices."""
        order = ["FRB", "ECB", "BOJ"]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in 'ordered()' order."""
        return get_choice_labels(cls)

    def get_location(self) -> LocationChoices:
        """Return the economic / market location associated with this central bank."""
        match self:
            case CentralBankChoices.FRB:
                return LocationChoices.US
            case CentralBankChoices.BOJ:
                return LocationChoices.JP
            case CentralBankChoices.ECB:
                return LocationChoices.EU
            case _:
                raise ValueError(f"No location configured for {self}")


class CentralBankMeetingStatusChoices(models.TextChoices):
    """Lifecycle of a stored policy meeting for calendar vs key-rate ingest."""

    UPCOMING = "UPCOMING", _("Upcoming")
    OCCURRED = "OCCURRED", _("Occurred")
    RATES_INGESTED = "RATES_INGESTED", _("Rates ingested")


class CentralBankMeetingModel(BaseModel):
    """Central Bank Meeting Model."""

    central_bank = models.CharField(
        max_length=255,
        choices=CentralBankChoices.choices,
        help_text="Central bank that holds this policy meeting.",
    )
    date = models.DateTimeField(
        help_text=(
            "Scheduled announcement time in UTC (local announcement time converted on ingest)."
        ),
    )
    status = models.CharField(
        max_length=32,
        choices=CentralBankMeetingStatusChoices.choices,
        default=CentralBankMeetingStatusChoices.UPCOMING,
        help_text=(
            "UPCOMING: scheduled time not yet reached. "
            "OCCURRED: announcement time past, key rates not ingested yet. "
            "RATES_INGESTED: decision-day key rates ingested for the display date."
        ),
    )


class CentralBankDataModel(BaseModel):
    """Central Bank Data Model."""

    cb_data_id = models.IntegerField(
        default=None,
        null=True,
        blank=True,
        help_text="Stable series id from central_banks_data.json.",
    )
    central_bank = models.CharField(
        max_length=255,
        choices=CentralBankChoices.choices,
        help_text="Central bank to which this data set belongs.",
    )
    short_name = models.CharField(
        max_length=255,
        default="",
        help_text="Short series code (e.g. BOJ_MUTAN, ECB_Deposit).",
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Human-readable series name for UI / recap cards.",
    )
    date = models.DateField(
        help_text="Key-rate date (display calendar day, not a datetime).",
    )
    value = models.FloatField(
        null=True,
        blank=True,
        default=None,
        help_text="Key-rate level; null when the scrape found none.",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        default="",
        help_text="Optional scrape / ingest note.",
    )


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

    central_bank = models.CharField(
        max_length=255,
        choices=CentralBankChoices.choices,
        help_text="Central bank to which this contract belongs.",
    )
    short_name = models.CharField(
        max_length=255,
        choices=StirFuturesNameChoices.choices,
        help_text="Contract family short code (FF1M / ESTR3M / MUTAN3M).",
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Human-readable futures contract name.",
    )
    maturity = models.TextField(
        blank=True,
        null=True,
        help_text="Contract maturity label (e.g. 26.03).",
    )
    first_accrual_date = models.DateField(
        null=True,
        blank=True,
        default=None,
        help_text="First accrual date when the source provides one.",
    )
    last_accrual_date = models.DateField(
        null=True,
        blank=True,
        default=None,
        help_text="Last accrual date when the source provides one.",
    )
    date = models.DateField(
        help_text="Price date.",
    )
    price = models.FloatField(
        null=True,
        blank=True,
        default=None,
        help_text="Settled / last price; null when missing.",
    )
    source = models.CharField(
        max_length=255,
        choices=StirFuturesSourceChoices.choices,
        help_text="Upstream price source.",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        default="",
        help_text="Optional scrape / ingest note.",
    )


class StirFuturesPriceUpdateLogModel(BaseLogModel):
    """Stir Futures Price Update Log Model."""

    fk_name = "stir_futures"
    stir_futures = models.ForeignKey(
        "StirFuturesModel",
        on_delete=models.CASCADE,
        related_name="stir_futures_price_update_logs",
        help_text="STIR futures this price-update log belongs to.",
    )
