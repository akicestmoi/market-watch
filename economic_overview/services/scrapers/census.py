"""Scrape US Census Bureau ACS Gini and ACS PUMS Palma series."""

import csv
import io
import logging
import re
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    CENSUS_ACS_API_URL_TEMPLATE,
    CENSUS_ACS_EASTERN_RELEASE_HOUR,
    CENSUS_ACS_EASTERN_RELEASE_MINUTE,
    CENSUS_ACS_GINI_FIRST_YEAR,
    CENSUS_ACS_RELEASE_SCHEDULE_URL,
    CENSUS_GINI_TICKER,
    CENSUS_PALMA_TICKER,
    CENSUS_PUMS_HOUSING_ZIP_URL_TEMPLATE,
    CENSUS_PUMS_PALMA_YEARS,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (ACS Gini and Palma)
# __________________________________________________________

_CENSUS_ACS_SCHEDULE_DATE_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),\s+(20\d{2})",
    flags=re.IGNORECASE,
)
_CENSUS_MONTH_NUMBER_BY_NAME: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# ACS household Gini is published on a 0–1 scale; Front stores 0–100 like Eurostat.
_ACS_GINI_TO_FRONT_SCALE = 100.0
# ACS PUMS codes missing / N/A household income as negative sentinels.
_PUMS_MISSING_HOUSEHOLD_INCOME_THRESHOLD = 0.0

_CENSUS_ACS_API_ADAPTER = TypeAdapter(list[list[str]])


def _get_census_api_key() -> str:
    """Return the configured Census API key, or an empty string when unset."""
    return (getattr(settings, "CENSUS_API_KEY", None) or "").strip()


def _parse_acs_gini_estimate(raw_estimate: str) -> float | None:
    """Parse one ACS B19083 estimate and scale it to 0–100."""
    try:
        gini_zero_to_one = float(raw_estimate)
    except ValueError:
        return None
    return gini_zero_to_one * _ACS_GINI_TO_FRONT_SCALE


def _fetch_acs_gini_for_year(year: int, api_key: str) -> ScrapingResult | None:
    """Fetch the national ACS 1-year B19083 Gini for one vintage year."""
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    request_params: dict[str, str] = {
        "get": "NAME,B19083_001E",
        "for": "us:1",
        "key": api_key,
    }
    response = requests.get(
        CENSUS_ACS_API_URL_TEMPLATE.format(year=year),
        params=request_params,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(
            f"Census ACS Gini HTTP {response.status_code} for year={year}: "
            f"{response.text[:200]}"
        )
        return None
    try:
        payload_rows = _CENSUS_ACS_API_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        logger.warning(f"Invalid Census ACS JSON for year={year}: {exc}")
        return None
    if len(payload_rows) < 2:
        return None
    # Header is row 0; national estimate is the only data row for for=us:1.
    data_row = payload_rows[1]
    if len(data_row) < 2:
        return None
    gini_value = _parse_acs_gini_estimate(data_row[1])
    if gini_value is None:
        return None
    return ScrapingResult(
        period=date(year, 1, 1),
        data_value=gini_value,
        comment="",
    )


def _list_acs_gini_series(api_key: str) -> list[ScrapingResult]:
    """Walk ACS 1-year vintages from the configured start year through today."""
    economic_data: list[ScrapingResult] = []
    latest_year = date.today().year
    for year in range(CENSUS_ACS_GINI_FIRST_YEAR, latest_year + 1):
        scraping_result = _fetch_acs_gini_for_year(year, api_key)
        if scraping_result is not None:
            economic_data.append(scraping_result)
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _calculate_weighted_palma_from_household_incomes(
    household_incomes: list[float],
    household_weights: list[float],
) -> float | None:
    """Compute Palma from weighted household money income (top 10% / bottom 40%)."""
    if not household_incomes or len(household_incomes) != len(household_weights):
        return None
    ordered_households = sorted(
        zip(household_incomes, household_weights, strict=True),
        key=lambda household: household[0],
    )
    total_weight = sum(weight for _income, weight in ordered_households)
    total_income = sum(
        income * weight for income, weight in ordered_households if income > 0
    )
    if total_weight <= 0 or total_income <= 0:
        return None

    cumulative_weight = 0.0
    bottom_forty_income = 0.0
    top_ten_income = 0.0
    bottom_forty_weight_cut = 0.4 * total_weight
    top_ten_weight_cut = 0.9 * total_weight
    for income, weight in ordered_households:
        previous_cumulative_weight = cumulative_weight
        cumulative_weight += weight
        positive_income = max(income, 0.0)
        if cumulative_weight <= bottom_forty_weight_cut:
            bottom_forty_income += positive_income * weight
        elif previous_cumulative_weight < bottom_forty_weight_cut:
            share_in_bottom = (
                bottom_forty_weight_cut - previous_cumulative_weight
            ) / weight
            bottom_forty_income += positive_income * weight * share_in_bottom
        if previous_cumulative_weight >= top_ten_weight_cut:
            top_ten_income += positive_income * weight
        elif cumulative_weight > top_ten_weight_cut:
            share_in_top = (cumulative_weight - top_ten_weight_cut) / weight
            top_ten_income += positive_income * weight * share_in_top
    if bottom_forty_income <= 0:
        return None
    return top_ten_income / bottom_forty_income


def _calculate_pums_palma_from_housing_zip_path(zip_path: Path) -> float | None:
    """Parse ACS PUMS housing CSVs inside a zip and return one Palma value.

    Only the derived Palma point is kept; the zip itself is never stored in the DB.
    """
    household_incomes: list[float] = []
    household_weights: list[float] = []
    with zipfile.ZipFile(zip_path) as zip_archive:
        for zip_member_name in zip_archive.namelist():
            if not zip_member_name.lower().endswith(".csv"):
                continue
            with zip_archive.open(zip_member_name) as csv_file:
                text_stream = io.TextIOWrapper(csv_file, encoding="utf-8", newline="")
                csv_reader = csv.DictReader(text_stream)
                for household_row in csv_reader:
                    raw_income = household_row.get("HINCP")
                    raw_weight = household_row.get("WGTP")
                    if raw_income is None or raw_weight is None:
                        continue
                    try:
                        household_income = float(raw_income)
                        household_weight = float(raw_weight)
                    except ValueError:
                        continue
                    if household_income < _PUMS_MISSING_HOUSEHOLD_INCOME_THRESHOLD:
                        continue
                    if household_weight <= 0:
                        continue
                    household_incomes.append(household_income)
                    household_weights.append(household_weight)
    return _calculate_weighted_palma_from_household_incomes(
        household_incomes, household_weights
    )


def _fetch_pums_palma_for_year(year: int) -> ScrapingResult | None:
    """Stream one ACS PUMS housing zip to a temp file, derive Palma, then delete it."""
    zip_url = CENSUS_PUMS_HOUSING_ZIP_URL_TEMPLATE.format(year=year)
    response = requests.get(zip_url, timeout=600, stream=True)
    if response.status_code >= 400:
        logger.warning(
            f"Census PUMS zip HTTP {response.status_code} for year={year}: "
            f"{zip_url}"
        )
        return None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".zip",
            prefix=f"acs_pums_{year}_",
            delete=True,
        ) as temporary_zip_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    temporary_zip_file.write(chunk)
            temporary_zip_file.flush()
            palma_value = _calculate_pums_palma_from_housing_zip_path(
                Path(temporary_zip_file.name)
            )
    except (KeyError, ValueError, zipfile.BadZipFile, OSError) as exc:
        logger.warning(f"Failed to parse Census PUMS zip for year={year}: {exc}")
        return None
    finally:
        response.close()
    if palma_value is None:
        return None
    return ScrapingResult(
        period=date(year, 1, 1),
        data_value=palma_value,
        comment="",
    )


def _list_pums_palma_series() -> list[ScrapingResult]:
    """Derive Palma for each configured ACS PUMS vintage year."""
    economic_data: list[ScrapingResult] = []
    for year in CENSUS_PUMS_PALMA_YEARS:
        scraping_result = _fetch_pums_palma_for_year(year)
        if scraping_result is not None:
            economic_data.append(scraping_result)
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_census(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.ANNUAL,
) -> list[ScrapingResult]:
    """Get US Census inequality series (ACS Gini or ACS PUMS Palma).

    ACS B19083 is scaled ×100 to match the Eurostat 0–100 Gini convention.
    Palma uses weighted household money income from ACS 1-year housing PUMS.
    """
    if frequency != EconomicPublicationFrequencyChoices.ANNUAL:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for Census scrape: {frequency}",
            )
        ]
    if ticker == CENSUS_GINI_TICKER:
        api_key = _get_census_api_key()
        if not api_key:
            return [
                ScrapingResult(
                    period=None,
                    data_value=None,
                    comment="CENSUS_API_KEY is not configured.",
                )
            ]
        economic_data = _list_acs_gini_series(api_key)
        if not economic_data:
            return [
                ScrapingResult(
                    period=None,
                    data_value=None,
                    comment="No Census ACS Gini values found.",
                )
            ]
        return filter_scraping_results_by_target_period(
            economic_data, target_period, frequency
        )
    if ticker == CENSUS_PALMA_TICKER:
        economic_data = _list_pums_palma_series()
        if not economic_data:
            return [
                ScrapingResult(
                    period=None,
                    data_value=None,
                    comment="No Census PUMS Palma values found.",
                )
            ]
        return filter_scraping_results_by_target_period(
            economic_data, target_period, frequency
        )
    return [
        ScrapingResult(
            period=None,
            data_value=None,
            comment=f"Unsupported CENSUS ticker: {ticker}",
        )
    ]


# __________________________________________________________
# Publication dates (ACS release schedule)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_census(name: str) -> list[datetime]:
    """Get upcoming ACS 1-year dates from the Census release-schedule page.

    Gini uses the ACS 1-year detailed-tables civil date at noon Eastern when
    Census stamps one. PUMS Palma often stays TBD on that page and then shares
    any dated ACS 1-year slot found (same annual ACS wave).
    """
    response = requests.get(
        CENSUS_ACS_RELEASE_SCHEDULE_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Census ACS release schedule: {response.text}")
        return []

    page_text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    publication_datetimes: list[datetime] = []
    for match in _CENSUS_ACS_SCHEDULE_DATE_PATTERN.finditer(page_text):
        month = _CENSUS_MONTH_NUMBER_BY_NAME[match.group(1).lower()]
        day = int(match.group(2))
        year = int(match.group(3))
        publication_datetimes.append(
            convert_local_wall_time_to_utc(
                year,
                month,
                day,
                CENSUS_ACS_EASTERN_RELEASE_HOUR,
                CENSUS_ACS_EASTERN_RELEASE_MINUTE,
                source_timezone="America/New_York",
            )
        )
    publication_datetimes = sorted(set(publication_datetimes))
    upcoming_publication_dates = filter_upcoming_publication_dates(
        publication_datetimes
    )
    if not upcoming_publication_dates:
        logger.warning(
            "Census ACS release schedule has no upcoming dated slot "
            f"(technical_name={name})."
        )
    return upcoming_publication_dates
