"""Shared TextChoices and helpers used by more than one economic overview model."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import get_choice_from_label, get_choice_labels


class EconomicDataLocationChoices(models.TextChoices):
    """Country or region codes for economic data and charts."""

    US = "US", _("United States")
    EU = "EU", _("Europe")
    DE = "DE", _("Germany")
    ES = "ES", _("Spain")
    IT = "IT", _("Italy")
    FR = "FR", _("France")
    JP = "JP", _("Japan")

    @classmethod
    def from_label(cls, label: str) -> "EconomicDataLocationChoices":
        """Return the location choice matching the given display label."""
        return get_choice_from_label(cls, label)

    @classmethod
    def ordered(cls) -> list["EconomicDataLocationChoices"]:
        """Ordered list of economic data location choices."""
        order = ["US", "EU", "FR", "JP", "DE", "ES", "IT"]
        return [cls[value] for value in order]

    @classmethod
    def get_labels(cls) -> list[str]:
        """Display labels in 'ordered()' order."""
        return get_choice_labels(cls)


class EconomicDataSourceChoices(models.TextChoices):
    """Publishers and APIs we ingest economic series from."""

    INSEE = "INSEE", _("Institut National de la Statistique et des Études Économiques")
    EUROSTAT = "EUROSTAT", _("Statistical Office of the European Union")
    FRED = "FRED", _("Federal Reserve Economic Data")
    UNIV_MICHIGAN = "UNIV_MICHIGAN", _("University of Michigan")
    JP_CABINET_OFFICE = "JP_CABINET_OFFICE", _("Japan Cabinet Office (ESRI)")
    STAT_OF_JP = "STAT_OF_JP", _("Statistics of Japan")
    MLIT = "MLIT", _("Japan Ministry of Land, Infrastructure, Transport and Tourism")
    METI = "METI", _("Japan Ministry of Economy, Trade and Industry")
    BOJ = "BOJ", _("Bank of Japan")
    MOF = "MOF", _("Japan Ministry of Finance")
    ECB = "ECB", _("European Central Bank")
    IMF = "IMF", _("International Monetary Fund")
    OECD = "OECD", _("Organisation for Economic Co-operation and Development")
    BEA = "BEA", _("Bureau of Economic Analysis")
    BANQUE_DE_FRANCE = "BANQUE_DE_FRANCE", _("Banque de France")
    NAHB = "NAHB", _("United States National Association of Home Builders")
    ISM = "ISM", _("United States Institute for Supply Management")
    CONFERENCE_BOARD = "CONFERENCE_BOARD", _("United States Conference Board")
    CENSUS = "CENSUS", _("United States Census Bureau")
    JP_CUSTOMS = "JP_CUSTOMS", _("Japan Customs")
    TRADING_ECONOMICS = "TRADING_ECONOMICS", _("Trading Economics")
    WID = "WID", _("World Inequality Database")


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


class IndicatorAmountMagnitudeChoices(models.TextChoices):
    """Currency amount magnitude for storage (K/M/B) or display scaling (+T)."""

    K = "K", _("Thousands")
    M = "M", _("Millions")
    B = "B", _("Billions")
    T = "T", _("Trillions")

    @classmethod
    def ordered(cls) -> list["IndicatorAmountMagnitudeChoices"]:
        """Ascending magnitude ladder for display scaling (K → M → B → T)."""
        return [cls.K, cls.M, cls.B, cls.T]


class IndicatorBaseCurrencyChoices(models.TextChoices):
    """Currency for amount-based indicators (K / M / B base units)."""

    USD = "USD", _("USD")
    EUR = "EUR", _("EUR")
    JPY = "JPY", _("JPY")


# Compact display symbols for amount cells / axis labels (e.g. 't$', 'b€', 'm¥').
INDICATOR_CURRENCY_SYMBOL_BY_CODE: dict[IndicatorBaseCurrencyChoices, str] = {
    IndicatorBaseCurrencyChoices.USD: "$",
    IndicatorBaseCurrencyChoices.EUR: "€",
    IndicatorBaseCurrencyChoices.JPY: "¥",
}
