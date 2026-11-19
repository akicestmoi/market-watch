"""Industry profitability models and classification choices."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)


class IndustryClassificationChoices(models.TextChoices):
    """Industry coding system used by stored industry profitability figures."""

    NACE_REV2_DIVISION = (
        "NACE_REV2_DIVISION",
        _("NACE Rev. 2 division (2-digit) — France"),
    )
    BEA_INDUSTRY = (
        "BEA_INDUSTRY",
        _("BEA GDP-by-industry detail — United States"),
    )
    MOF_CORPORATE_INDUSTRY = (
        "MOF_CORPORATE_INDUSTRY",
        _("MOF corporate survey industry — Japan"),
    )
    ESRI_ECONOMIC_ACTIVITY = (
        "ESRI_ECONOMIC_ACTIVITY",
        _("ESRI SNA economic activity — Japan"),
    )


class IndustryProfitabilityModel(BaseModel):
    """Annual industry turnover, operating profit, and GVA by classification."""

    location = models.CharField(
        max_length=8,
        choices=EconomicDataLocationChoices.choices,
        help_text="Economy this industry figure belongs to (US, FR, or JP).",
    )
    classification = models.CharField(
        max_length=32,
        choices=IndustryClassificationChoices.choices,
        help_text=(
            "Industry coding system for this figure (NACE / BEA / MOF survey, or "
            "ESRI SNA economic activity for Japan GVA contribution)."
        ),
    )
    industry_code = models.CharField(
        max_length=16,
        help_text=(
            "Source industry code at the configured aggregation "
            "(e.g. NACE C10, BEA 325, MOF Food, ESRI 3.1)."
        ),
    )
    industry_label = models.CharField(
        max_length=255,
        help_text="Human-readable industry name from the source for this code.",
    )
    period = models.DateField(
        help_text=(
            "Calendar / fiscal year of the figure, stamped on 1 January of that year "
            "(Japan MOF uses the fiscal-year start calendar year; ESRI uses the "
            "calendar year)."
        ),
    )
    turnover = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Sales or gross output for this industry and year, in the unit and "
            "currency below (Eurostat net turnover, BEA gross output, or MOF sales). "
            "Empty when we only have value-added from ESRI."
        ),
    )
    operating_profit = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Operating profit for this industry and year, in the unit and currency "
            "below (Eurostat or BEA gross operating surplus, or MOF operating "
            "profit). Empty when we only have value-added from ESRI."
        ),
    )
    gva = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Gross value added for this industry and year, in the unit and currency "
            "below (Eurostat SBS, BEA, or ESRI). Empty on MOF survey lines that "
            "have no value-added."
        ),
    )
    base_unit = models.CharField(
        max_length=8,
        choices=IndicatorBaseUnitChoices.choices,
        help_text=(
            "Amount magnitude of turnover, operating profit, and GVA "
            "(thousands, millions, or billions)."
        ),
    )
    base_currency = models.CharField(
        max_length=8,
        choices=IndicatorBaseCurrencyChoices.choices,
        help_text="Currency for turnover, operating profit, and value-added (EUR, USD, or JPY).",
    )
    source = models.CharField(
        max_length=32,
        choices=EconomicDataSourceChoices.choices,
        help_text=(
            "Who published the survey (Eurostat SBS, BEA, Japan MOF, or "
            "Japan Cabinet Office ESRI)."
        ),
    )

    class Meta:
        """One figure per location, classification, industry code, and year."""

        constraints = [
            models.UniqueConstraint(
                fields=("location", "classification", "industry_code", "period"),
                name="uniq_ind_profit_loc_class_code_period",
            )
        ]
        indexes = [
            models.Index(
                fields=("location", "classification", "period"),
                name="idx_ind_profit_loc_cls_prd",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.location} {self.classification} {self.industry_code} "
            f"{self.period.year}"
        )
