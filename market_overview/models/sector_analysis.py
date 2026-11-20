"""Daily subsector weight, return, and contribution for equity-index sector analysis."""

from django.db import models

from core.models import BaseModel
from market_overview.models.common import EquityIndexChoices


class IndexSubsectorDailyMoveModel(BaseModel):
    """One day's weight, return, contribution, and top names for one index subsector."""

    date = models.DateField(
        help_text="Trading day these subsector figures are for.",
    )
    equity_index = models.CharField(
        max_length=16,
        choices=EquityIndexChoices.choices,
        help_text=(
            "Parent equity index this subsector belongs to "
            "(S&P 500, CAC 40, or Nikkei 225)."
        ),
    )
    sector = models.CharField(
        max_length=100,
        help_text="Parent sector name from the single-names catalog.",
    )
    subsector = models.CharField(
        max_length=100,
        help_text="Subsector name from the single-names catalog.",
    )
    weight = models.FloatField(
        help_text=(
            "Share of the parent index in this subsector, in percent "
            "(for example 3.2 means 3.2% of the index)."
        ),
    )
    daily_return = models.FloatField(
        help_text=(
            "Weight-renormalized day move of names in this subsector, in percent "
            "(for example 1.5 means +1.5%)."
        ),
    )
    contribution = models.FloatField(
        help_text=(
            "How many percentage points of the index day move came from this "
            "subsector (weight as a fraction times daily return)."
        ),
    )
    top_movers = models.JSONField(
        default=list,
        help_text=(
            "Up to three companies in this subsector with the largest absolute "
            "index contribution. Each entry has company name, ticker, weight "
            "percent, daily return percent, and index contribution."
        ),
    )

    class Meta:
        """Unique daily move per index subsector."""

        constraints = [
            models.UniqueConstraint(
                fields=["equity_index", "date", "sector", "subsector"],
                name="unique_index_subsector_daily_move",
            )
        ]
