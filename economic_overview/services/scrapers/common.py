"""Shared types and helpers for economic data scrapers."""

from datetime import date
from typing import TypedDict

from economic_overview.models import EconomicPublicationFrequencyChoices


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

    period: date | None
    data_value: float | None
    comment: str


def filter_scraping_results_by_target_period(
    economic_data: list[ScrapingResult],
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Filter scraped rows to a single target period label when requested."""
    if not target_period:
        return economic_data
    for row in economic_data:
        period = row["period"]
        if period is None:
            continue
        if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
            if period.strftime("%Y-%m") == target_period:
                return [row]
        elif frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
            quarter = (period.month - 1) // 3 + 1
            if target_period in {
                period.strftime("%Y-%m"),
                f"{period.year}-Q{quarter}",
                f"{period.year}-T{quarter}",
            }:
                return [row]
        elif frequency == EconomicPublicationFrequencyChoices.ANNUAL:
            if period.strftime("%Y") == target_period:
                return [row]
    return [
        ScrapingResult(period=None, data_value=None, comment="Target period not found.")
    ]
