"""Persisted market-analysis models (DailyRecap) and news-source enums."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class NewsSourceChoices(models.TextChoices):
    """Registered news scrapers (mapped to discover functions in code)."""

    BOURSIER_CLOTURE_PARIS = "BOURSIER_CLOTURE_PARIS", _("Boursier — Clôture Paris")
    SWISSINFO_MARKET_WRAP = "SWISSINFO_MARKET_WRAP", _("Swissinfo — Markets Wrap")


class DailyRecapModel(BaseModel):
    """AI-generated daily financial news analysis."""

    reporting_date = models.DateField(unique=True)
    title = models.CharField(max_length=300)
    main_summary = models.TextField(
        help_text="High-level worldwide mainline (not detailed)."
    )
    us_summary = models.TextField(blank=True, default="")
    eur_summary = models.TextField(blank=True, default="")
    jp_summary = models.TextField(blank=True, default="")
    additional_summary = models.TextField(
        blank=True,
        default="",
        help_text="Commodities, crypto, notable RoW / non-core-zone items.",
    )
    source_urls = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-reporting_date", "-date_added"]

    def __str__(self) -> str:
        return f"Recap {self.reporting_date}: {self.title[:60]}"
