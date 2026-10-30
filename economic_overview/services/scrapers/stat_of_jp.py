"""Scrape Japan series from the e-Stat Statistics Dashboard API."""

import re
from datetime import date, datetime
from typing import TypedDict

import requests
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)
from economic_overview.services.config import (
    STAT_OF_JP_DATA_URL,
    STAT_OF_JP_DEFAULT_PARAMS,
    STAT_OF_JP_SERIES_BY_TICKER,
)


class StatOfJpDataObj(TypedDict, total=False):
    """Wrapper around a single VALUE object (``@time`` / ``$`` keys)."""

    # Open-key map of already-typed attribute / value strings from the API.
    VALUE: dict[str, str]


class StatOfJpDataInf(TypedDict, total=False):
    """DATA_INF block."""

    DATA_OBJ: list[StatOfJpDataObj]


class StatOfJpStatisticalData(TypedDict, total=False):
    """STATISTICAL_DATA block."""

    DATA_INF: StatOfJpDataInf


class StatOfJpGetStats(TypedDict, total=False):
    """GET_STATS block."""

    STATISTICAL_DATA: StatOfJpStatisticalData


class StatOfJpPayload(TypedDict, total=False):
    """e-Stat Dashboard getData JSON root (fields we read)."""

    GET_STATS: StatOfJpGetStats


_STAT_OF_JP_PAYLOAD_ADAPTER = TypeAdapter(StatOfJpPayload)


def _parse_stat_of_jp_time_label(time_label: str) -> date | None:
    """Parse e-Stat Dashboard time codes (``YYYYMM00`` / ``YYYY nQ00``)."""
    monthly_match = re.fullmatch(r"(\d{4})(\d{2})00", time_label)
    if monthly_match:
        year = int(monthly_match.group(1))
        month = int(monthly_match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
        return None
    quarterly_match = re.fullmatch(r"(\d{4})(\d)Q00", time_label)
    if quarterly_match:
        year = int(quarterly_match.group(1))
        quarter = int(quarterly_match.group(2))
        if 1 <= quarter <= 4:
            return date(year, (quarter - 1) * 3 + 1, 1)
    return None


def _parse_stat_of_jp_values(payload: StatOfJpPayload) -> list[ScrapingResult]:
    """Parse e-Stat Dashboard ``DATA_OBJ`` values into scraping results."""
    data_objects = (
        payload.get("GET_STATS", {})
        .get("STATISTICAL_DATA", {})
        .get("DATA_INF", {})
        .get("DATA_OBJ", [])
    )
    economic_data: list[ScrapingResult] = []
    for data_object in data_objects:
        value_block = data_object.get("VALUE", {})
        time_label = value_block.get("@time")
        raw_value = value_block.get("$")
        if not time_label or raw_value is None or raw_value == "":
            continue
        period = _parse_stat_of_jp_time_label(time_label)
        if period is None:
            continue
        try:
            data_value = float(raw_value)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(key=lambda row: row["period"] or date.min, reverse=True)
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_stat_of_jp(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get Japan series from the e-Stat Statistics Dashboard API.

    ``ticker`` is our configured series ID. The e-Stat ``IndicatorCode`` and
    filters come from ``STAT_OF_JP_SERIES_BY_TICKER``.

    Source: https://dashboard.e-stat.go.jp/en/static/api
    """
    series_config = STAT_OF_JP_SERIES_BY_TICKER.get(ticker)
    if series_config is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported STAT_OF_JP ticker: {ticker}",
            )
        ]

    series_params = series_config["params"]
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    stat_of_jp_request_params: dict[str, str] = {
        "Lang": STAT_OF_JP_DEFAULT_PARAMS["Lang"],
        "RegionCode": STAT_OF_JP_DEFAULT_PARAMS["RegionCode"],
        "TimeFrom": STAT_OF_JP_DEFAULT_PARAMS["TimeFrom"],
        "Cycle": series_params["Cycle"],
        "IsSeasonalAdjustment": series_params["IsSeasonalAdjustment"],
        "IndicatorCode": series_config["indicator_code"],
        "TimeTo": f"{date.today().year}1200",
    }
    response = requests.get(
        STAT_OF_JP_DATA_URL,
        params=stat_of_jp_request_params,
        timeout=60,
        headers={"User-Agent": "market-watch/1.0"},
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping JP e-Stat data: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        payload = _STAT_OF_JP_PAYLOAD_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Invalid JP e-Stat JSON: {exc}",
            )
        ]

    economic_data = _parse_stat_of_jp_values(payload)
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No JP e-Stat values found."
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_stat_of_jp(name: str) -> list[datetime]:
    """Get publication dates from Statistics of Japan (not yet wired)."""
    logger.warning(
        "Statistics of Japan publication schedule is not implemented "
        f"(technical_name={name})."
    )
    return []
