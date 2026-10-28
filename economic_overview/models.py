"""Economic indicator, observation, and publication-schedule models."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseLogModel, BaseModel, get_choice_from_label, get_choice_labels


class EconomicDataLocationChoices(models.TextChoices):
    """Economic Data Location Choices."""

    US = "US", _("United States")
    EU = "EU", _("Europe")
    FR = "FR", _("France")
    JP = "JP", _("Japan")

    @classmethod
    def from_label(cls, label: str) -> "EconomicDataLocationChoices":
        """Return the location choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["EconomicDataLocationChoices"]:
        """Ordered list of economic data location choices."""
        order = ["US", "EU", "FR", "JP"]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in ``ordered()`` order."""
        return get_choice_labels(cls)


class EconomicDataSourceChoices(models.TextChoices):
    """Economic Data Source Choices."""

    INSEE = "INSEE", _("INSEE")
    EUROSTAT = "EUROSTAT", _("Eurostat")
    JP_CABINET_OFFICE = "JP_CABINET_OFFICE", _("Japan Cabinet Office")


class EconomicDataCategoryChoices(models.TextChoices):
    """Economic Data Category Choices."""

    GROWTH = "GROWTH", _("Growth")
    INFLATION = "INFLATION", _("Inflation")
    GOVERNMENT = "GOVERNMENT", _("Government")
    PRODUCTION = "PRODUCTION", _("Production")
    SALES = "SALES", _("Sales")
    LABOUR = "LABOUR", _("Labour")
    HOUSING = "HOUSING", _("Housing")
    CONFIDENCE = "CONFIDENCE", _("Confidence")

    @classmethod
    def from_label(cls, label: str) -> "EconomicDataCategoryChoices":
        """Return the category choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["EconomicDataCategoryChoices"]:
        """Ordered list of economic data category choices."""
        order = [
            "GROWTH",
            "INFLATION",
            "GOVERNMENT",
            "PRODUCTION",
            "SALES",
            "LABOUR",
            "HOUSING",
            "CONFIDENCE",
        ]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in ``ordered()`` order."""
        return get_choice_labels(cls)


class EconomicPublicationFrequencyChoices(models.TextChoices):
    """Economic Publication Frequency Choices."""

    MONTHLY = "MONTHLY", _("Monthly")
    QUARTERLY = "QUARTERLY", _("Quarterly")
    ANNUAL = "ANNUAL", _("Annual")


class IndicatorBaseUnitChoices(models.TextChoices):
    """Information about the base unit of the indicator.

    INDEX — index based on 100 for the base year
    PERCENT — rate / ratio stored as percent points
    K / M / B — currency magnitude at which the value is stored;
    """

    INDEX = "INDEX", _("Index")
    PERCENT = "PERCENT", _("Percent")
    K = "K", _("Thousands")
    M = "M", _("Millions")
    B = "B", _("Billions")


class EconomicIndicatorInformationModel(BaseModel):
    """Economic Indicator Information Model."""

    id = models.IntegerField(primary_key=True)
    location = models.CharField(
        max_length=255, choices=EconomicDataLocationChoices.choices
    )
    category = models.CharField(
        max_length=255, choices=EconomicDataCategoryChoices.choices
    )
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    technical_name = models.CharField(max_length=255)
    frequency = models.CharField(
        max_length=255, choices=EconomicPublicationFrequencyChoices.choices
    )
    source = models.CharField(max_length=255, choices=EconomicDataSourceChoices.choices)
    ticker = models.CharField(max_length=255)
    base_unit = models.CharField(
        max_length=16,
        choices=IndicatorBaseUnitChoices.choices,
        blank=True,
        default="",
    )
    base_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Index base year when base_unit is INDEX (e.g. 2010 = 100).",
    )

    def __str__(self):
        return f"{self.name}"

    def display_name(self) -> str:
        """Default display name where the base unit is specified."""
        if self.base_unit == IndicatorBaseUnitChoices.INDEX and self.base_year:
            return f"{self.type} (base year: {self.base_year})"
        if self.base_unit == IndicatorBaseUnitChoices.PERCENT:
            return f"{self.type} (in %)"
        if self.base_unit in {
            IndicatorBaseUnitChoices.K,
            IndicatorBaseUnitChoices.M,
            IndicatorBaseUnitChoices.B,
        }:
            return f"{self.type} (in {self.base_unit})"
        return self.type


class PublicationScheduleModel(BaseModel):
    """Publication Schedule Model."""

    indicator = models.ForeignKey(
        EconomicIndicatorInformationModel,
        on_delete=models.CASCADE,
        related_name="publication_schedule",
    )
    previous_publication_date = models.DateTimeField(null=True, blank=True)
    current_publication_date = models.DateTimeField(null=True, blank=True)
    next_publication_date = models.DateTimeField(null=True, blank=True)


class EconomicDataModel(BaseModel):
    """Economic Data Model."""

    indicator = models.ForeignKey(
        EconomicIndicatorInformationModel,
        on_delete=models.CASCADE,
        related_name="economic_data",
    )
    period = models.DateField(null=True, blank=True)
    data_value = models.FloatField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    def get_period_display(self):
        """Get period display."""
        if not self.period:
            return None
        match self.indicator.frequency:
            case EconomicPublicationFrequencyChoices.MONTHLY:
                month_str = self.period.strftime("%b")
                year_short = self.period.strftime("%y")
                return f"{month_str}.{year_short}"
            case EconomicPublicationFrequencyChoices.QUARTERLY:
                quarter = (self.period.month - 1) // 3 + 1
                year_short = self.period.year % 100
                return f"{year_short:02d}Q{quarter}"
            case EconomicPublicationFrequencyChoices.ANNUAL:
                return self.period.strftime("%Y")


class EconomicDataUpdateLogModel(BaseLogModel):
    """Economic Data Update Log Model."""

    fk_name = "economic_data"
    economic_data = models.ForeignKey(
        "EconomicDataModel",
        on_delete=models.CASCADE,
        related_name="economic_data_update_logs",
    )
