"""Watchlist companies for equity-index earnings monitoring."""

from django.db import models

from core.models import BaseModel
from market_overview.models.common import EquityIndexChoices


class EarningsWatchlistModel(BaseModel):
    """One top-weight company with upcoming, current, and previous earnings."""

    company = models.CharField(
        max_length=200,
        help_text="Company display name on the earnings watchlist.",
    )
    ticker = models.CharField(
        max_length=32,
        unique=True,
        help_text="Yahoo Finance ticker used to scrape prices and earnings.",
    )
    equity_index = models.CharField(
        max_length=16,
        choices=EquityIndexChoices.choices,
        help_text=(
            "Parent equity index this watchlist name belongs to "
            "(S&P 500, CAC 40, or Nikkei 225)."
        ),
    )
    weight_pct = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Latest share of the parent index for this company, in percent "
            "(for example 7.7 means 7.7%). Empty until weights are refreshed."
        ),
    )

    upcoming_announcement_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled earnings call time in UTC. Empty when unknown.",
    )
    upcoming_reporting_period_end = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Fiscal period end for the upcoming earnings release. Empty when unknown."
        ),
    )
    upcoming_eps_expected = models.FloatField(
        null=True,
        blank=True,
        help_text="Consensus EPS expected for the upcoming earnings release. Empty when unknown.",
    )
    upcoming_revenue_expected = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Consensus total revenue expected for the upcoming earnings release. "
            "Empty when unknown."
        ),
    )

    current_reporting_period_end = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Fiscal period end for the latest reported results. Empty when unknown."
        ),
    )
    current_eps = models.FloatField(
        null=True,
        blank=True,
        help_text="Reported EPS for the latest reported results. Empty when unknown.",
    )
    current_eps_expected = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Consensus EPS that was expected for the latest reported results. Empty when unknown."
        ),
    )
    current_revenue_expected = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Consensus total revenue that was expected for the latest reported results. "
            "Empty when unknown."
        ),
    )
    current_revenue = models.FloatField(
        null=True,
        blank=True,
        help_text="Reported total revenue for the latest reported results. Empty when unknown.",
    )
    current_operating_income = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Reported operating income for the latest reported results. Empty when unknown."
        ),
    )
    current_gross_profit = models.FloatField(
        null=True,
        blank=True,
        help_text="Reported gross profit for the latest reported results. Empty when unknown.",
    )
    current_ebitda = models.FloatField(
        null=True,
        blank=True,
        help_text="Reported EBITDA for the latest reported results. Empty when unknown.",
    )

    previous_reporting_period_end = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Fiscal period end for the results before the latest. Empty when unknown."
        ),
    )
    previous_eps = models.FloatField(
        null=True,
        blank=True,
        help_text="Reported EPS for the results before the latest. Empty when unknown.",
    )
    previous_eps_expected = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Consensus EPS that was expected for the results before the latest. "
            "Empty when unknown."
        ),
    )
    previous_revenue_expected = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Consensus total revenue that was expected for the results before "
            "the latest. Empty when unknown."
        ),
    )
    previous_revenue = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Reported total revenue for the results before the latest. "
            "Empty when unknown."
        ),
    )
    previous_operating_income = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Reported operating income for the results before the latest. "
            "Empty when unknown."
        ),
    )
    previous_gross_profit = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Reported gross profit for the results before the latest. "
            "Empty when unknown."
        ),
    )
    previous_ebitda = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Reported EBITDA for the results before the latest. Empty when unknown."
        ),
    )

    class Meta:
        """Watchlist ordering helpers."""

        indexes = [
            models.Index(fields=["equity_index", "weight_pct"]),
        ]
