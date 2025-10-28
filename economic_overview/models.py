from typing import List

from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.models import BaseLogModel, BaseModel


class EconomicDataLocationChoices(models.TextChoices):
    """Economic Data Location Choices."""

    US = "US", _("United States")
    EU = "EU", _("Europe")
    FR = "FR", _("France")
    JP = "JP", _("Japan")

    @classmethod
    def ordered(cls) -> List[str]:
        """Ordered list of economic data location choices."""
        order = ["US", "EU", "FR", "JP"]
        return [cls[value] for value in order]


class EconomicDataSourceChoices(models.TextChoices):
    """Economic Data Source Choices."""

    INSEE = "INSEE", _("INSEE")


class EconomicDataCategoryChoices(models.TextChoices):
    """Economic Data Category Choices."""

    GROWTH = "GROWTH", _("Growth")
    INFLATION = "INFLATION", _("Inflation")
    GOVERNMENT = "GOVERNMENT", _("Government")
    LABOUR = "LABOUR", _("Labour")
    HOUSING = "HOUSING", _("Housing")
    PRODUCTION = "PRODUCTION", _("Production")
    CONFIDENCE = "CONFIDENCE", _("Confidence")
    SALES = "SALES", _("Sales")
    CENTRAL_BANKS = "CENTRAL_BANKS", _("Central Banks")

    @classmethod
    def ordered(cls) -> List[str]:
        """Ordered list of economic data category choices."""
        order = [
            "GROWTH",
            "INFLATION",
            "GOVERNMENT",
            "LABOUR",
            "HOUSING",
            "PRODUCTION",
            "CONFIDENCE",
            "SALES",
            "CENTRAL_BANKS",
        ]
        return [cls[value] for value in order]


class EconomicPublicationFrequencyChoices(models.TextChoices):
    """Economic Publication Frequency Choices."""

    MONTHLY = "MONTHLY", _("Monthly")
    QUARTERLY = "QUARTERLY", _("Quarterly")
    ANNUAL = "ANNUAL", _("Annual")


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

    def __str__(self):
        return f"{self.name}"


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
