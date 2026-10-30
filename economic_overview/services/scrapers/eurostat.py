"""Scrape Eurostat economic series and the Eurostat release calendar."""

import json
import re
from datetime import date, datetime, timedelta
from typing import TypedDict

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.utils import timezone
from pydantic import TypeAdapter, ValidationError

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from economic_overview.models import (
    EconomicDataLocationChoices,
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    EUROSTAT_API_DEFAULT_PARAMS,
    EUROSTAT_GEO_FOR_EU_LOCATION,
    EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS,
    EUROSTAT_PUBLICATION_SCHEDULE_URL,
    EUROSTAT_SERIES_TEMPLATES,
    EUROSTAT_STATISTICS_API_BASE_URL,
    EurostatQueryParams,
    EurostatTickerParams,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)


class EurostatJsonStatCategory(TypedDict, total=False):
    """JSON-stat category block (period labels → flat positions)."""

    # Usage of dict: keys are dynamic JSON-stat category labels (e.g. time periods).
    index: dict[str, int]


class EurostatJsonStatDimension(TypedDict, total=False):
    """JSON-stat dimension block."""

    category: EurostatJsonStatCategory


class EurostatJsonStatPayload(TypedDict):
    """Eurostat Statistics API JSON-stat subset used for scraping."""

    id: list[str]
    size: list[int]
    # Usage of dict: keys are JSON-stat flat indexes; values are observation numbers.
    value: dict[str, float | int | None]
    # Usage of dict: keys are dynamic dimension ids (freq, unit, time, …).
    dimension: dict[str, EurostatJsonStatDimension]


_EUROSTAT_JSONSTAT_ADAPTER = TypeAdapter(EurostatJsonStatPayload)


def _decode_eurostat_flat_index(flat_index: int, sizes: list[int]) -> list[int]:
    """Decode a JSON-stat flat index into per-dimension coordinates."""
    coordinates: list[int] = []
    remaining = flat_index
    for size in reversed(sizes):
        coordinates.append(remaining % size)
        remaining //= size
    return list(reversed(coordinates))


def _parse_eurostat_period_label(period_label: str) -> date | None:
    """Parse Eurostat time labels (``YYYY-MM``, ``YYYY-Qn``, or annual ``YYYY``)."""
    monthly_match = re.fullmatch(r"(\d{4})-(\d{2})", period_label)
    if monthly_match:
        year = int(monthly_match.group(1))
        month = int(monthly_match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
        return None
    quarterly_match = re.fullmatch(r"(\d{4})-Q([1-4])", period_label)
    if quarterly_match:
        year = int(quarterly_match.group(1))
        quarter = int(quarterly_match.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)
    annual_match = re.fullmatch(r"(\d{4})", period_label)
    if annual_match:
        return date(int(annual_match.group(1)), 1, 1)
    return None


def _parse_eurostat_jsonstat_values(
    payload: EurostatJsonStatPayload,
) -> list[ScrapingResult]:
    """Parse Eurostat Statistics API JSON-stat ``value`` / ``dimension`` payload."""
    dimension_ids = payload["id"]
    sizes = payload["size"]
    values = payload["value"]
    dimensions = payload["dimension"]
    if "time" not in dimension_ids:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="Eurostat payload missing time."
            )
        ]

    time_dimension = dimensions.get("time", EurostatJsonStatDimension())
    time_category = time_dimension.get("category", EurostatJsonStatCategory())
    time_index = time_category.get("index")
    if time_index is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Eurostat time index is not a mapping.",
            )
        ]
    position_to_period = {
        position: period_label for period_label, position in time_index.items()
    }
    time_dimension_offset = dimension_ids.index("time")

    economic_data: list[ScrapingResult] = []
    for flat_index_str, raw_value in values.items():
        try:
            flat_index = int(flat_index_str)
            coordinates = _decode_eurostat_flat_index(flat_index, sizes)
            time_position = coordinates[time_dimension_offset]
            period_label = position_to_period[time_position]
            period = _parse_eurostat_period_label(period_label)
            if period is None:
                continue
            data_value = float(raw_value) if raw_value is not None else None
            if data_value is None:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )

    economic_data.sort(
        key=lambda row: row["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _build_eurostat_request_params(
    series_id: str, location: str
) -> EurostatTickerParams | None:
    """Build Statistics API dataset + filters for a configured Eurostat series."""
    template = next(
        (
            series_template
            for series_template in EUROSTAT_SERIES_TEMPLATES
            if series_template.series_id == series_id
        ),
        None,
    )
    if template is None:
        return None
    geo = (
        EUROSTAT_GEO_FOR_EU_LOCATION
        if location == EconomicDataLocationChoices.EU
        else location
    )
    params: EurostatQueryParams = {**template.params, "geo": geo}
    return EurostatTickerParams(dataset=template.dataset, params=params)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_eurostat(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
    location: str = "",
) -> list[ScrapingResult]:
    """Get Eurostat economic data (all rows, or a single matching period).

    Dataset path and filters come from the configured series ID (seed ticker) and
    indicator ``location`` as geo. Periods are ``YYYY-MM``, ``YYYY-Qn``, or annual
    ``YYYY``.

    Source: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/
    """
    if frequency not in (
        EconomicPublicationFrequencyChoices.MONTHLY,
        EconomicPublicationFrequencyChoices.QUARTERLY,
        EconomicPublicationFrequencyChoices.ANNUAL,
    ):
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for Eurostat scrape: {frequency}",
            )
        ]
    ticker_params = _build_eurostat_request_params(ticker, location)
    if ticker_params is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Eurostat ticker: {ticker}",
            )
        ]

    eurostat_url = f"{EUROSTAT_STATISTICS_API_BASE_URL}{ticker_params['dataset']}"
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    eurostat_request_params: dict[str, str] = {
        "format": EUROSTAT_API_DEFAULT_PARAMS["format"],
        "lang": EUROSTAT_API_DEFAULT_PARAMS["lang"],
    }
    for param_key, param_value in ticker_params["params"].items():
        assert isinstance(param_value, str)
        eurostat_request_params[param_key] = param_value
    response = requests.get(
        eurostat_url,
        params=eurostat_request_params,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Eurostat data: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        payload = _EUROSTAT_JSONSTAT_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Invalid Eurostat JSON-stat: {exc}",
            )
        ]

    economic_data = _parse_eurostat_jsonstat_values(payload)
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No Eurostat values found."
            )
        ]
    if economic_data[0]["data_value"] is None and economic_data[0]["period"] is None:
        return economic_data

    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


class EurostatCalendarEvent(TypedDict, total=False):
    """One FullCalendar event from Eurostat eventsJson (fields we read)."""

    title: str
    start: str


class EurostatPublicationScheduleRow(TypedDict):
    """One normalized Eurostat publication schedule row before DataFrame load."""

    name: str
    publication_date: str | None


_EUROSTAT_CALENDAR_EVENTS_ADAPTER = TypeAdapter(list[EurostatCalendarEvent])


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_eurostat_publication_schedule() -> pd.DataFrame:
    """Get Eurostat publication schedule.

    Source: https://ec.europa.eu/eurostat/news/release-calendar/
    JSON feed: https://ec.europa.eu/eurostat/o/calendars/eventsJson
    Event ``start`` values are UTC (``…Z``); the UI labels Europe/Luxembourg.
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
    range_start = timezone.now()
    range_end = range_start + timedelta(days=EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS)
    response = requests.get(
        EUROSTAT_PUBLICATION_SCHEDULE_URL,
        params={
            "start": range_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": range_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Eurostat publication schedule: {response.text}")
        return default_df

    try:
        raw_payload = json.loads(response.content)
        events = _EUROSTAT_CALENDAR_EVENTS_ADAPTER.validate_python(raw_payload)
    except (TypeError, json.JSONDecodeError, ValidationError):
        logger.warning("Invalid Eurostat publication schedule JSON")
        return default_df

    records: list[EurostatPublicationScheduleRow] = []
    for event in events:
        records.append(
            EurostatPublicationScheduleRow(
                name=event.get("title", ""),
                publication_date=event.get("start"),
            )
        )

    df = pd.DataFrame(records)
    if df.empty:
        return default_df
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_eurostat(name: str) -> list[datetime]:
    """Get publication dates from Eurostat."""
    publication_schedule = _get_eurostat_publication_schedule()
    publication_dates = publication_schedule[publication_schedule["name"] == name][
        "publication_date"
    ]
    return [
        pd_timestamp.to_pydatetime() for pd_timestamp in publication_dates.tolist()[:2]
    ]
