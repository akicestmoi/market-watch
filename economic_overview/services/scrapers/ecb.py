"""Scrape ECB Data Portal SDMX series (QSA sector accounts and DWA wealth)."""

import csv
import io
import logging
import re
import time
from datetime import date, datetime

import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    ECB_HTTP_MAX_ATTEMPTS,
    ECB_QSA_HOUSEHOLD_RELEASE_TITLE_FRAGMENT,
    ECB_QSA_RELEASE_CALENDAR_URL,
    ECB_REF_AREA_FOR_EU_LOCATION,
    ECB_SDMX_DATA_URL_TEMPLATE,
    ECB_SERIES_BY_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (QSA sector accounts and DWA wealth)
# __________________________________________________________


def _get_ecb_ref_area(location: str) -> str:
    """Map our indicator location code to an ECB REF_AREA code."""
    if location == EconomicDataLocationChoices.EU:
        return ECB_REF_AREA_FOR_EU_LOCATION
    return location


def _parse_ecb_period_label(period_label: str) -> date | None:
    """Parse ECB SDMX time labels ('YYYY-Qn')."""
    quarterly_match = re.fullmatch(r"(\d{4})-Q([1-4])", period_label.strip())
    if quarterly_match is None:
        return None
    year = int(quarterly_match.group(1))
    quarter = int(quarterly_match.group(2))
    return date(year, (quarter - 1) * 3 + 1, 1)


def _parse_ecb_csvdata(csv_text: str) -> list[ScrapingResult]:
    """Parse ECB 'format=csvdata' observations into scraping results."""
    reader = csv.DictReader(io.StringIO(csv_text))
    economic_data: list[ScrapingResult] = []
    for observation in reader:
        period_label = (observation.get("TIME_PERIOD") or "").strip()
        raw_value = (observation.get("OBS_VALUE") or "").strip()
        if not period_label or not raw_value:
            continue
        period = _parse_ecb_period_label(period_label)
        if period is None:
            continue
        try:
            data_value = float(raw_value)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _keep_ecb_q4_as_annual(
    economic_data: list[ScrapingResult],
) -> list[ScrapingResult]:
    """Keep Q4 observations only and store them as calendar-year annual points."""
    annual_data: list[ScrapingResult] = []
    for scraping_result in economic_data:
        period = scraping_result["period"]
        # Q4 labels parse to month 10 ((4 - 1) * 3 + 1).
        if period is None or period.month != 10:
            continue
        annual_data.append(
            ScrapingResult(
                period=date(period.year, 1, 1),
                data_value=scraping_result["data_value"],
                comment=scraping_result["comment"],
            )
        )
    return annual_data


def _download_ecb_series(dataflow: str, series_key: str) -> list[ScrapingResult]:
    """Download one ECB SDMX series as CSV, retrying transient gateway errors."""
    url = ECB_SDMX_DATA_URL_TEMPLATE.format(dataflow=dataflow, series_key=series_key)
    last_error_comment = "ECB request failed."
    for attempt in range(ECB_HTTP_MAX_ATTEMPTS):
        response = requests.get(
            url,
            params={"format": "csvdata"},
            timeout=90,
            headers={"Accept": "text/csv"},
        )
        if response.status_code == 200:
            try:
                return _parse_ecb_csvdata(response.text)
            except Exception as exc:
                return [
                    ScrapingResult(
                        period=None,
                        data_value=None,
                        comment=f"Error parsing ECB CSV: {exc}",
                    )
                ]
        last_error_comment = response.text
        # ECB occasionally returns 504; brief backoff before retrying.
        if (
            response.status_code in {502, 503, 504}
            and attempt + 1 < ECB_HTTP_MAX_ATTEMPTS
        ):
            time.sleep(1.5 * (attempt + 1))
            continue
        logger.warning(f"Error scraping ECB data: {response.text[:500]}")
        return [
            ScrapingResult(
                period=None, data_value=None, comment=last_error_comment[:500]
            )
        ]
    return [
        ScrapingResult(period=None, data_value=None, comment=last_error_comment[:500])
    ]


def _signal_unsupported_ecb_scrape_error(
    ticker: str,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult] | None:
    """Return an error result when ticker or frequency is unsupported."""
    series_config = ECB_SERIES_BY_TICKER.get(ticker)
    if series_config is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported ECB ticker: {ticker}",
            )
        ]
    expected_frequency = (
        EconomicPublicationFrequencyChoices.ANNUAL
        if series_config.keep_q4_as_annual
        else EconomicPublicationFrequencyChoices.QUARTERLY
    )
    if frequency != expected_frequency:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for ECB scrape: {frequency}",
            )
        ]
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_ecb(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.QUARTERLY,
    location: str = EconomicDataLocationChoices.EU,
) -> list[ScrapingResult]:
    """Get ECB QSA or DWA series values for one location.

    Source: https://data-api.ecb.europa.eu/service/data/
    DWA wealth series keep Q4 only and store them as annual points.
    """
    unsupported_error = _signal_unsupported_ecb_scrape_error(ticker, frequency)
    if unsupported_error is not None:
        return unsupported_error
    series_config = ECB_SERIES_BY_TICKER[ticker]
    series_key = series_config.series_key_template.format(
        ref_area=_get_ecb_ref_area(location)
    )
    parsed = _download_ecb_series(series_config.dataflow, series_key)
    # A failed scrape returns exactly one empty error result at index 0.
    if (
        len(parsed) == 1
        and parsed[0]["period"] is None
        and parsed[0]["data_value"] is None
    ):
        return parsed
    if series_config.keep_q4_as_annual:
        parsed = _keep_ecb_q4_as_annual(parsed)
    if not parsed:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No ECB series values found."
            )
        ]
    return filter_scraping_results_by_target_period(parsed, target_period, frequency)


# __________________________________________________________
# Publication dates (QSA release calendar)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_ecb(_: str) -> list[datetime]:
    """Get upcoming QSA household dates from the ECB sector-accounts calendar.

    Clock is Europe/Berlin (Frankfurt) as stamped on the calendar page.
    """
    response = requests.get(
        ECB_QSA_RELEASE_CALENDAR_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping ECB QSA release calendar: {response.text}")
        return []

    publication_datetimes: list[datetime] = []
    for match in re.finditer(
        r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})\s*</dt>\s*<dd>\s*"
        + re.escape(ECB_QSA_HOUSEHOLD_RELEASE_TITLE_FRAGMENT),
        response.text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        publication_datetimes.append(
            convert_local_wall_time_to_utc(
                year,
                month,
                day,
                hour,
                minute,
                source_timezone="Europe/Berlin",
            )
        )
    publication_datetimes.sort()
    return filter_upcoming_publication_dates(publication_datetimes)
