from django.db import models
from django.utils.translation import gettext_lazy as _


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


class EconomicPublicationFrequencyChoices(models.TextChoices):
    """Economic Publication Frequency Choices."""

    DAILY = "DAILY", _("Growth")
    WEEKLY = "WEEKLY", _("Weekly")
    MONTHLY = "MONTHLY", _("Monthly")
    QUATERLY = "QUATERLY", _("Quaterly")
    YEARLY = "YEARLY", _("Yearly")
