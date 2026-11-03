"""Shared types and helpers for economic data scrapers."""

from datetime import date, datetime
from typing import TypedDict

from django.utils import timezone

from economic_overview.models import EconomicPublicationFrequencyChoices


class ScrapingResult(TypedDict):
    """Scraped economic indicator value for one period, or add a miss comment."""

    period: date | None
    data_value: float | None
    comment: str


def filter_upcoming_publication_dates(
    publication_datetimes: list[datetime],
    *,
    as_of: datetime | None = None,
    limit: int = 2,
) -> list[datetime]:
    """Keep upcoming publication datetimes (at most 'limit').

    At most two are returned by default: schedule update maps [0]/[1] onto
    current/next after rolling the just-released slot into previous; past dates
    must not be fed again.
    """
    reference_datetime = as_of if as_of is not None else timezone.now()
    upcoming_publication_dates = [
        publication_datetime
        for publication_datetime in publication_datetimes
        if publication_datetime >= reference_datetime
    ]
    # Default limit 2 keeps current and next; past dates must not be fed again.
    return upcoming_publication_dates[:limit]


def filter_scraping_results_by_target_period(
    economic_data: list[ScrapingResult],
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Filter scraped values to a single target period label when requested."""
    if not target_period:
        return economic_data
    for scraping_result in economic_data:
        period = scraping_result["period"]
        if period is None:
            continue
        if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
            if period.strftime("%Y-%m") == target_period:
                return [scraping_result]
        elif frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
            quarter = (period.month - 1) // 3 + 1
            if target_period in {
                period.strftime("%Y-%m"),
                f"{period.year}-Q{quarter}",
                f"{period.year}-T{quarter}",
            }:
                return [scraping_result]
        elif frequency == EconomicPublicationFrequencyChoices.ANNUAL:
            if period.strftime("%Y") == target_period:
                return [scraping_result]
    return [
        ScrapingResult(period=None, data_value=None, comment="Target period not found.")
    ]
