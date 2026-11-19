"""Economic indicator catalog, stored values, update logs, and indicator choices."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import (
    BaseLogModel,
    BaseModel,
    get_choice_from_label,
    get_choice_labels,
)
from economic_overview.models.common import (
    INDICATOR_CURRENCY_SYMBOL_BY_CODE,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)


class EconomicDataCategoryChoices(models.TextChoices):
    """Top-level economic indicator categories."""

    HOUSEHOLD = "HOUSEHOLD", _("Household")
    BUSINESS = "BUSINESS", _("Business")
    MACROECONOMICS = "MACROECONOMICS", _("Macroeconomics")
    GOVERNMENT = "GOVERNMENT", _("Government")

    @classmethod
    def from_label(cls, label: str) -> "EconomicDataCategoryChoices":
        """Return the category choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["EconomicDataCategoryChoices"]:
        """Ordered list of economic data category choices."""
        order = [
            "MACROECONOMICS",
            "HOUSEHOLD",
            "BUSINESS",
            "GOVERNMENT",
        ]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in 'ordered()' order."""
        return get_choice_labels(cls)


class EconomicDataSubcategoryChoices(models.TextChoices):
    """Thematic subcategory under a top-level economic category."""

    GROWTH = "GROWTH", _("Growth")
    TRADE = "TRADE", _("Trade")
    LABOUR = "LABOUR", _("Labour")
    INEQUALITY = "INEQUALITY", _("Inequality")
    INCOME = "INCOME", _("Income")
    SAVING = "SAVING", _("Saving")
    DEBT = "DEBT", _("Debt")
    SALES = "SALES", _("Sales")
    PRICES = "PRICES", _("Prices")
    HOUSING = "HOUSING", _("Housing")
    CONFIDENCE = "CONFIDENCE", _("Confidence")
    INVESTMENT = "INVESTMENT", _("Investment")
    COST = "COST", _("Cost")
    PRODUCTION = "PRODUCTION", _("Production")
    BUDGET = "BUDGET", _("Budget")
    FINANCING = "FINANCING", _("Financing")

    @classmethod
    def from_label(cls, label: str) -> "EconomicDataSubcategoryChoices":
        """Return the subcategory choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["EconomicDataSubcategoryChoices"]:
        """Ordered list of economic data subcategory choices."""
        order = [
            "GROWTH",
            "TRADE",
            "LABOUR",
            "INEQUALITY",
            "INCOME",
            "SAVING",
            "DEBT",
            "SALES",
            "PRICES",
            "HOUSING",
            "CONFIDENCE",
            "INVESTMENT",
            "COST",
            "PRODUCTION",
            "BUDGET",
            "FINANCING",
        ]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in 'ordered()' order."""
        return get_choice_labels(cls)


class IndicatorMeasureTypeChoices(models.TextChoices):
    """How an indicator value should be read."""

    FLOW = "FLOW", _("Flow")
    STOCK = "STOCK", _("Stock")
    RATE = "RATE", _("Rate")
    INDEX = "INDEX", _("Index")
    RATIO = "RATIO", _("Ratio")
    DERIVED = "DERIVED", _("Derived")


class IndicatorPriceBasisChoices(models.TextChoices):
    """Whether an Abs amount is at current prices or volume / chain-linked.

    Used in the recap hover bubble and to pick Nominal vs Real GDP for vsGDP /
    percent-of-GDP maths. Not a DB column — resolved from the series label.
    """

    NOMINAL = "NOMINAL", _("Nominal")
    REAL = "REAL", _("Real")


class IndicatorExpansionRelationChoices(models.TextChoices):
    """How a nested indicator relates to its parent on expandable recap lines."""

    COMPONENT = "COMPONENT", _("Component")
    RELATED = "RELATED", _("Related")


class EconomicPublicationFrequencyChoices(models.TextChoices):
    """How often an economic indicator is published (monthly, quarterly, or annual)."""

    MONTHLY = "MONTHLY", _("Monthly")
    QUARTERLY = "QUARTERLY", _("Quarterly")
    ANNUAL = "ANNUAL", _("Annual")


class IndicatorDisplayModeChoices(models.TextChoices):
    """Default / selectable transform for an indicator's displayed values."""

    RAW = "Raw", _("Raw")
    MONTH = "MoM", _("MoM")
    QUARTER = "QoQ", _("QoQ")
    ANNUALIZED_QUARTER = "QoQy", _("QoQy")
    ANNUAL = "YoY", _("YoY")
    VS_GDP = "vsGDP", _("vsGDP")
    YTD_RAW = "YTDRaw", _("YTDRaw")
    YTD_YOY = "YTDYoY", _("YTDYoY")
    YTD_VS_GDP = "YTDvsGDP", _("YTDvsGDP")
    REL_QOQ = "Rel QoQ", _("Rel QoQ")
    REL_YOY = "Rel YoY", _("Rel YoY")
    CONTR_QOQ = "Contr QoQ", _("Contr QoQ")
    CONTR_YOY = "Contr YoY", _("Contr YoY")
    YTD_REL_QOQ = "YTDRelQoQ", _("YTDRelQoQ")
    YTD_REL_YOY = "YTDRelYoY", _("YTDRelYoY")
    YTD_CONTR_QOQ = "YTDContrQoQ", _("YTDContrQoQ")
    YTD_CONTR_YOY = "YTDContrYoY", _("YTDContrYoY")


class PublicationScheduleModeChoices(models.TextChoices):
    """How this indicator gets release timing for ingest scheduling."""

    CALENDAR = "CALENDAR", _("Official calendar")
    MONTHLY_UPDATE = "MONTHLY_UPDATE", _("Monthly update")


class EconomicIndicatorInformationModel(BaseModel):
    """Catalog metadata for one economic indicator series."""

    id = models.IntegerField(
        primary_key=True,
        help_text="Fixed id from the economic catalog file.",
    )
    location = models.CharField(
        max_length=255,
        choices=EconomicDataLocationChoices.choices,
        help_text="Country or region this indicator covers.",
    )
    category = models.CharField(
        max_length=255,
        choices=EconomicDataCategoryChoices.choices,
        help_text="Main theme: household, business, macroeconomics, or government.",
    )
    subcategory = models.CharField(
        max_length=255,
        choices=EconomicDataSubcategoryChoices.choices,
        help_text="Finer theme within the category (growth, inflation, labour, and so on).",
    )
    series_label = models.CharField(
        max_length=255,
        help_text=(
            "Short shared label used on charts and in dropdowns (same across countries)."
        ),
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Full display name, usually including the country.",
    )
    technical_name = models.CharField(
        max_length=255,
        help_text="Name used by the publisher when it differs from our display name.",
    )
    frequency = models.CharField(
        max_length=255,
        choices=EconomicPublicationFrequencyChoices.choices,
        help_text="Publication frequency (monthly / quarterly / annual).",
    )
    source = models.CharField(
        max_length=255,
        choices=EconomicDataSourceChoices.choices,
        help_text="Where we fetch this indicator from.",
    )
    ticker = models.CharField(
        max_length=255,
        help_text="Publisher series code used when fetching data.",
    )
    base_unit = models.CharField(
        max_length=16,
        choices=IndicatorBaseUnitChoices.choices,
        blank=True,
        default="",
        help_text=(
            "Unit of the stored value: index, percent, or an amount scale "
            "(thousands / millions / billions)."
        ),
    )
    base_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="For index series, the year when the index equals 100 (for example 2010).",
    )
    base_currency = models.CharField(
        max_length=8,
        choices=IndicatorBaseCurrencyChoices.choices,
        blank=True,
        default="",
        help_text="Currency for amount series (for example USD). Empty for indexes and percents.",
    )
    default_mode = models.CharField(
        max_length=32,
        choices=IndicatorDisplayModeChoices.choices,
        default=IndicatorDisplayModeChoices.RAW,
        help_text="How the value is shown by default on the recap and charts pages.",
    )
    measure_type = models.CharField(
        max_length=16,
        choices=IndicatorMeasureTypeChoices.choices,
        default=IndicatorMeasureTypeChoices.FLOW,
        help_text=(
            "What kind of number this is: a flow, stock, rate, index, ratio, "
            "or a value we build ourselves (for example an OECD output gap)."
        ),
    )
    parent_series_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Parent indicator's series label in the same location for expandable "
            "recap lines; empty when this indicator is top-level."
        ),
    )
    expansion_relation = models.CharField(
        max_length=16,
        choices=IndicatorExpansionRelationChoices.choices,
        blank=True,
        default="",
        help_text=(
            "How a nested indicator relates to its parent. Component children can use "
            "share and contribution modes; related children only nest for "
            "detail. Empty when this is not a child."
        ),
    )
    is_hidden = models.BooleanField(
        default=False,
        help_text=(
            "When true, we still store and fetch the series (for example Nominal "
            "GDP used for percent-of-GDP), but it never appears on the recap or charts."
        ),
    )
    publication_schedule_mode = models.CharField(
        max_length=32,
        choices=PublicationScheduleModeChoices.choices,
        default=PublicationScheduleModeChoices.CALENDAR,
        help_text=(
            "How we learn when a new value is out. Calendar mode reads an official "
            "release calendar. Monthly update mode has no dated calendar, so a "
            "first-of-month job checks for a newer value and stores it only when one appears."
        ),
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Short plain-English text shown in the recap hover bubble: what it "
            "measures, survey scope when useful, how the published level is "
            "expressed, how to read it, who publishes it, and any own-calculation "
            "details. See docs/INDICATORS.md."
        ),
    )
    source_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "Link or label shown in the hover bubble for the publisher page, "
            "or for a series we build ourselves."
        ),
    )

    def __str__(self):
        return f"{self.full_name}"

    def get_amount_unit_label(self) -> str | None:
        """Compact amount unit such as 'b$', or 'None' when not an amount."""
        if self.base_unit not in {
            IndicatorBaseUnitChoices.K,
            IndicatorBaseUnitChoices.M,
            IndicatorBaseUnitChoices.B,
        }:
            return None
        magnitude = self.base_unit.lower()
        if self.base_currency:
            currency_symbol = INDICATOR_CURRENCY_SYMBOL_BY_CODE.get(
                IndicatorBaseCurrencyChoices(self.base_currency),
                self.base_currency,
            )
            return f"{magnitude}{currency_symbol}"
        return magnitude

    def get_display_name(self) -> str:
        """Default display name; amount and percent units live on value cells."""
        if self.base_unit == IndicatorBaseUnitChoices.INDEX and self.base_year:
            return f"{self.series_label} (base year: {self.base_year})"
        return self.series_label


class EconomicDataModel(BaseModel):
    """One stored observation for an economic indicator and period."""

    indicator = models.ForeignKey(
        EconomicIndicatorInformationModel,
        on_delete=models.CASCADE,
        related_name="economic_data",
        help_text="Indicator this data point belongs to.",
    )
    period = models.DateField(
        null=True,
        blank=True,
        help_text="Start of the period this value covers (month, quarter, or year).",
    )
    data_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Stored value for that period. Empty when the value is missing.",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        help_text="Optional note from fetching or saving this value.",
    )

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
    """Change log for one stored economic indicator value."""

    fk_name = "economic_data"
    economic_data = models.ForeignKey(
        "EconomicDataModel",
        on_delete=models.CASCADE,
        related_name="economic_data_update_logs",
        help_text="Stored economic value this change log belongs to.",
    )
