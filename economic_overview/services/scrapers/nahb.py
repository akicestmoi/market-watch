"""Scrape NAHB/Wells Fargo Housing Market Index history workbooks."""

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

import requests
import xlrd
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    NAHB_HMI_EASTERN_RELEASE_HOUR,
    NAHB_HMI_EASTERN_RELEASE_MINUTE,
    NAHB_HMI_PAGE_URL,
    NAHB_HMI_RELEASE_DATES_URL,
    NAHB_HMI_TICKER,
    NAHB_SITE_ORIGIN,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (Housing Market Index)
# __________________________________________________________


def _get_nahb_hmi_history_xls_url() -> str | None:
    """Resolve the latest National HMI history Excel URL from the HMI page."""
    response = requests.get(
        NAHB_HMI_PAGE_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        return None
    match = re.search(
        r'href="([^"]*t2-national-hmi-history[^"]+\.xls[^"]*)"',
        response.text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return urljoin(NAHB_SITE_ORIGIN, match.group(1).replace("&amp;", "&"))


def _parse_nahb_hmi_history_workbook(workbook_bytes: bytes) -> list[ScrapingResult]:
    """Parse the National HMI year×month grid into monthly levels."""
    workbook = xlrd.open_workbook(file_contents=workbook_bytes)
    worksheet = workbook.sheet_by_index(0)
    economic_data: list[ScrapingResult] = []
    for row_index in range(worksheet.nrows):
        year_cell = worksheet.cell_value(row_index, 0)
        if isinstance(year_cell, bool) or not isinstance(year_cell, (int, float)):
            continue
        year = int(year_cell)
        if year < 1900:
            continue
        for month in range(1, 13):
            value_cell = worksheet.cell_value(row_index, month)
            if value_cell in ("", None):
                continue
            if isinstance(value_cell, bool) or not isinstance(value_cell, (int, float)):
                continue
            economic_data.append(
                ScrapingResult(
                    period=date(year, month, 1),
                    data_value=float(value_cell),
                    comment="",
                )
            )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _fetch_nahb_hmi_scraping_results() -> list[ScrapingResult]:
    """Download and parse the NAHB national HMI history workbook."""
    workbook_url = _get_nahb_hmi_history_xls_url()
    if workbook_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Could not resolve NAHB HMI history workbook URL.",
            )
        ]
    response = requests.get(
        workbook_url,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping NAHB HMI workbook: {response.text[:200]}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        economic_data = _parse_nahb_hmi_history_workbook(response.content)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing NAHB HMI workbook: {exc}",
            )
        ]
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No NAHB HMI values found.",
            )
        ]
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_nahb(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get the NAHB/Wells Fargo National Housing Market Index.

    Supported ticker: 'nahb_hmi'. Source workbook is Table 2 on the HMI page.
    """
    if ticker != NAHB_HMI_TICKER:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported NAHB ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for NAHB scrape: {frequency}",
            )
        ]

    economic_data = _fetch_nahb_hmi_scraping_results()
    # A failed scrape returns exactly one empty error result at index 0.
    if economic_data[0]["data_value"] is None:
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (HMI releases)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_nahb(_: str) -> list[datetime]:
    """Get upcoming NAHB/Wells Fargo HMI dates from the official release table.

    Clock is 10:00 America/New_York per NAHB's HMI release-dates page.
    """
    response = requests.get(
        NAHB_HMI_RELEASE_DATES_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping NAHB HMI release dates: {response.text}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    publication_datetimes: list[datetime] = []
    for table_row in soup.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True) for cell in table_row.find_all(["td", "th"])
        ]
        if len(cells) < 2 or cells[0].lower().startswith("reporting"):
            continue
        release_label = cells[1].replace(".", "")
        try:
            release_date = datetime.strptime(release_label, "%b %d, %Y").date()
        except ValueError:
            continue
        publication_datetimes.append(
            convert_local_wall_time_to_utc(
                release_date.year,
                release_date.month,
                release_date.day,
                NAHB_HMI_EASTERN_RELEASE_HOUR,
                NAHB_HMI_EASTERN_RELEASE_MINUTE,
                source_timezone="America/New_York",
            )
        )
    publication_datetimes.sort()
    return filter_upcoming_publication_dates(publication_datetimes)
