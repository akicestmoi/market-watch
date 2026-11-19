"""Customs trade ranking model."""

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)


class TradeTypeChoices(models.TextChoices):
    """Merchandise vs energy customs trade ranking family."""

    MERCHANDISE = "MERCHANDISE", _("Merchandise")
    ENERGY = "ENERGY", _("Energy")


class TradeFlowChoices(models.TextChoices):
    """Import or export direction for customs trade rankings."""

    IMPORT = "IMPORT", _("Import")
    EXPORT = "EXPORT", _("Export")


class TradeBreakdownChoices(models.TextChoices):
    """How a trade ranking is broken down for charts and storage."""

    PRODUCT = "PRODUCT", _("By Product")
    PARTNER = "PARTNER", _("By Partner")
    PRODUCT_PARTNER = "PRODUCT_PARTNER", _("By Product and Partner")


class TradeRankingModel(BaseModel):
    """One customs trade ranking (Top-N list item or product×partner cell)."""

    trade_type = models.CharField(
        max_length=16,
        choices=TradeTypeChoices.choices,
        help_text="Whether this ranking belongs to merchandise trade or energy trade.",
    )
    location = models.CharField(
        max_length=8,
        choices=EconomicDataLocationChoices.choices,
        help_text="Reporter economy for this customs ranking (US, FR, or JP).",
    )
    period = models.DateField(
        help_text="Calendar year of the ranking, stamped on 1 January of that year.",
    )
    flow = models.CharField(
        max_length=8,
        choices=TradeFlowChoices.choices,
        help_text="Whether this ranking is for imports or exports.",
    )
    breakdown = models.CharField(
        max_length=16,
        choices=TradeBreakdownChoices.choices,
        help_text=(
            "By product, by partner, or product×partner cell "
            "(product filters on the charts use product×partner)."
        ),
    )
    rank = models.PositiveSmallIntegerField(
        help_text="1-based place on this ranking set by trade value.",
    )
    product_code = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text=(
            "Product / HS code. Empty for partner-only Top-N rankings; "
            "set for product Top-N and product×partner cells."
        ),
    )
    product_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Human-readable product name. Empty when no product is listed.",
    )
    partner_code = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text=(
            "Partner country code. Empty for product-only Top-N rankings; "
            "set for partner Top-N and product×partner cells."
        ),
    )
    partner_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Human-readable partner name. Empty when no partner is listed.",
    )
    trade_value = models.FloatField(
        help_text=(
            "Trade value in the reporter's native currency "
            "(EUR for FR, USD for US, JPY for JP)."
        ),
    )
    source = models.CharField(
        max_length=32,
        choices=EconomicDataSourceChoices.choices,
        help_text=(
            "Who published the customs figures "
            "(Eurostat Comext, Census, or Japan Customs)."
        ),
    )

    class Meta:
        """Uniqueness and lookup indexes for trade ranking sets."""

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "trade_type",
                    "location",
                    "period",
                    "flow",
                    "breakdown",
                    "product_code",
                    "partner_code",
                ),
                name="uniq_trade_ranking_cell",
            ),
            models.UniqueConstraint(
                fields=(
                    "trade_type",
                    "location",
                    "period",
                    "flow",
                    "breakdown",
                    "rank",
                ),
                condition=Q(
                    breakdown__in=[
                        TradeBreakdownChoices.PRODUCT,
                        TradeBreakdownChoices.PARTNER,
                    ]
                ),
                name="uniq_trade_ranking_topn_rank",
            ),
            models.UniqueConstraint(
                fields=(
                    "trade_type",
                    "location",
                    "period",
                    "flow",
                    "breakdown",
                    "product_code",
                    "rank",
                ),
                condition=Q(breakdown=TradeBreakdownChoices.PRODUCT_PARTNER),
                name="uniq_trade_ranking_product_partner_rank",
            ),
        ]
        indexes = [
            models.Index(
                fields=("trade_type", "location", "period", "flow", "breakdown"),
                name="idx_trade_ranking_slice",
            ),
            models.Index(
                fields=(
                    "trade_type",
                    "location",
                    "period",
                    "flow",
                    "breakdown",
                    "product_code",
                ),
                name="idx_trade_ranking_product",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.trade_type} {self.location} {self.flow} {self.breakdown} "
            f"{self.product_code}/{self.partner_code} "
            f"#{self.rank} {self.period.year}"
        )
