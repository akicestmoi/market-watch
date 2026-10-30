"""Scrape FRED observations and FRED release dates."""

from datetime import date, datetime
from datetime import timezone as datetime_timezone
from typing import TypedDict

import requests
from cachetools.func import ttl_cache
from django.conf import settings
from django.utils import timezone
from pydantic import TypeAdapter, ValidationError

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.config import (
    FRED_OBSERVATION_START,
    FRED_OBSERVATIONS_URL,
    FRED_RELEASE_DATES_URL,
    FRED_RELEASE_ID_BY_TECHNICAL_NAME,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)


class _FredObservation(TypedDict, total=False):
    """One FRED observation row (fields we read)."""

    date: str
    value: str


class _FredObservationsPayload(TypedDict, total=False):
    """FRED ``series/observations`` JSON root (fields we read)."""

    observations: list[_FredObservation]


_FRED_OBSERVATIONS_ADAPTER = TypeAdapter(_FredObservationsPayload)


def _parse_fred_observations(
    payload: _FredObservationsPayload,
) -> list[ScrapingResult]:
    """Parse FRED observation rows into scraping results (newest first)."""
    economic_data: list[ScrapingResult] = []
    for observation in payload.get("observations", []):
        period_label = observation.get("date")
        raw_value = observation.get("value")
        if not period_label or raw_value is None or raw_value == ".":
            continue
        try:
            period = datetime.strptime(period_label, "%Y-%m-%d").date()
            data_value = float(raw_value)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(key=lambda row: row["period"] or date.min, reverse=True)
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_fred(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get FRED series observations (all rows, or a single matching period).

    Source: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
    """
    api_key = (getattr(settings, "FRED_API_KEY", None) or "").strip()
    if not api_key:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="FRED_API_KEY is not configured.",
            )
        ]

    response = requests.get(
        FRED_OBSERVATIONS_URL,
        params={
            "series_id": ticker,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": FRED_OBSERVATION_START,
            "sort_order": "desc",
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping FRED data: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        payload = _FRED_OBSERVATIONS_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Invalid FRED observations JSON: {exc}",
            )
        ]

    economic_data = _parse_fred_observations(payload)
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No FRED observations found."
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


class _FredReleaseDate(TypedDict, total=False):
    """One FRED release date row (fields we read)."""

    date: str


class _FredReleaseDatesPayload(TypedDict, total=False):
    """FRED ``release/dates`` JSON root (fields we read)."""

    release_dates: list[_FredReleaseDate]


_FRED_RELEASE_DATES_ADAPTER = TypeAdapter(_FredReleaseDatesPayload)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_fred(name: str) -> list[datetime]:
    """Get upcoming FRED release dates for a seeded technical release name.

    Source: https://fred.stlouisfed.org/docs/api/fred/release_dates.html
    """
    release_id = FRED_RELEASE_ID_BY_TECHNICAL_NAME.get(name)
    if release_id is None:
        logger.warning(f"No FRED release_id mapping for technical_name: {name}")
        return []

    api_key = (getattr(settings, "FRED_API_KEY", None) or "").strip()
    if not api_key:
        logger.warning("FRED_API_KEY is not configured; skipping FRED schedule.")
        return []

    today = timezone.now().date()
    # ``realtime_start=today`` is required: without it, ``sort_order=asc`` +
    # ``limit`` returns the oldest historical dates and long-history releases
    # (e.g. G.17 / release 13) never reach upcoming schedule rows.
    response = requests.get(
        FRED_RELEASE_DATES_URL,
        params={
            "release_id": release_id,
            "api_key": api_key,
            "file_type": "json",
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": 100,
            "realtime_start": today.isoformat(),
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping FRED release dates: {response.text}")
        return []

    try:
        payload = _FRED_RELEASE_DATES_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        logger.warning(f"Invalid FRED release dates JSON: {exc}")
        return []

    upcoming: list[datetime] = []
    for release_date_row in payload.get("release_dates", []):
        date_label = release_date_row.get("date")
        if not date_label:
            continue
        try:
            release_date = datetime.strptime(date_label, "%Y-%m-%d").date()
        except ValueError:
            continue
        if release_date < today:
            continue
        upcoming.append(
            datetime(
                release_date.year,
                release_date.month,
                release_date.day,
                tzinfo=datetime_timezone.utc,
            )
        )
        if len(upcoming) >= 2:
            break
    return upcoming
