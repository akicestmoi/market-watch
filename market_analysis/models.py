"""Persisted market-analysis models (DailyRecap) and news-source enums."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class ArticleRegionChoices(models.TextChoices):
    """UI / catalog region for a scraped market wrap."""

    GLOBAL = "GLOBAL", _("Global")
    US = "US", _("US")
    EU = "EU", _("EU")
    FR = "FR", _("FR")
    JP = "JP", _("JP")


class NewsSourceChoices(models.TextChoices):
    """Registered news scrapers (mapped to discover functions in code)."""

    BOURSIER_CLOTURE_PARIS = "BOURSIER_CLOTURE_PARIS", _("Boursier — Clôture Paris")
    SWISSINFO_MARKET_WRAP = "SWISSINFO_MARKET_WRAP", _("Swissinfo — Markets Wrap")
    TOKYO_CLOSING_BELL = "TOKYO_CLOSING_BELL", _("Tokyo Closing Bell")
    TBS_JAPAN_MARKETS = "TBS_JAPAN_MARKETS", _("TBS Bloomberg — 日本市況")
    TBS_US_MARKETS = "TBS_US_MARKETS", _("TBS Bloomberg — 米国市況")
    BOURSORAMA = "BOURSORAMA", _("Boursorama")
    ZONEBOURSE = "ZONEBOURSE", _("Zonebourse")
    NEWSQUAWK_US_MARKET_WRAP = (
        "NEWSQUAWK_US_MARKET_WRAP",
        _("Newsquawk — US Market Wrap"),
    )
    THE_EDGE_GLOBAL_MARKETS = (
        "THE_EDGE_GLOBAL_MARKETS",
        _("The Edge — Global Markets"),
    )
    CNBC_STOCK_MARKET_DAILY_RECAP = (
        "CNBC_STOCK_MARKET_DAILY_RECAP",
        _("CNBC — Stock Market Daily Recap"),
    )


class DailyRecapModel(BaseModel):
    """AI-generated daily financial news analysis."""

    reporting_date = models.DateField(
        unique=True,
        help_text="Market session / calendar day this recap covers.",
    )
    title = models.CharField(
        max_length=300,
        help_text="Short headline for the daily recap.",
    )
    main_summary = models.TextField(
        help_text="High-level worldwide mainline (not detailed)."
    )
    us_summary = models.TextField(
        blank=True,
        default="",
        help_text="US-focused market wrap section; empty when not covered.",
    )
    eur_summary = models.TextField(
        blank=True,
        default="",
        help_text="Euro-area / Europe-focused market wrap section; empty when not covered.",
    )
    jp_summary = models.TextField(
        blank=True,
        default="",
        help_text="Japan-focused market wrap section; empty when not covered.",
    )
    additional_summary = models.TextField(
        blank=True,
        default="",
        help_text="Commodities, crypto, notable RoW / non-core-zone items.",
    )
    source_urls = models.JSONField(
        default=list,
        blank=True,
        help_text="List of article URLs used as inputs for this recap.",
    )
    model_name = models.CharField(
        max_length=100,
        help_text="LLM model id that generated this recap.",
    )
    prompt_version = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Prompt / instruction version stamp for reproducibility.",
    )

    class Meta:
        """Daily recap model metadata (newest reporting date first)."""

        ordering = ["-reporting_date", "-date_added"]

    def __str__(self) -> str:
        return f"Recap {self.reporting_date}: {self.title[:60]}"
