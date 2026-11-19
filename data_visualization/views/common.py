"""Shared helpers for data_visualization page views."""

from datetime import date, datetime
from typing import NamedTuple

from django.http import HttpRequest

from core.services.calendar import (
    get_market_watch_as_of_date,
    get_previous_business_day,
)


class RecapReferenceDates(NamedTuple):
    """Reference and previous dates parsed from a recap page query string."""

    reference_date: date
    previous_date: date
    default_reference_date: date
    default_previous_date: date


def parse_recap_reference_and_previous_dates(
    request: HttpRequest,
) -> RecapReferenceDates:
    """Parse reference and previous dates from GET params with market-watch defaults."""
    default_reference_date = get_market_watch_as_of_date()
    reference_date = request.GET.get(
        "reference_date", default_reference_date.isoformat()
    )
    reference_date = datetime.fromisoformat(reference_date).date()

    default_previous_date = get_previous_business_day(default_reference_date)
    previous_date = request.GET.get(
        "previous_date",
        default_previous_date.isoformat(),
    )
    previous_date = datetime.fromisoformat(previous_date).date()
    return RecapReferenceDates(
        reference_date=reference_date,
        previous_date=previous_date,
        default_reference_date=default_reference_date,
        default_previous_date=default_previous_date,
    )


def get_recap_dates_base_context(dates: RecapReferenceDates) -> dict[str, str]:
    """Return ISO date strings shared by recap pages that use reference/previous dates."""
    # Usage of dict: template context keys for the shared recap date fields.
    return {
        "reference_date": dates.reference_date.isoformat(),
        "previous_date": dates.previous_date.isoformat(),
        "default_reference_date": dates.default_reference_date.isoformat(),
        "default_previous_date": dates.default_previous_date.isoformat(),
    }
