"""Scrape University of Michigan Surveys of Consumers tables."""

import csv
import io
import logging
from datetime import date, datetime

import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    MICHIGAN_SCA_DATA_ARCHIVE_URL,
    MICHIGAN_SCA_FRED_TECHNICAL_NAME,
    MICHIGAN_SCA_TABLE_BY_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)
from economic_overview.services.scrapers.fred import get_publication_dates_from_fred

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (Surveys of Consumers)
# __________________________________________________________


def _parse_univ_michigan_sca_table_csv(csv_text: str) -> list[ScrapingResult]:
    """Parse a Michigan SCA table CSV into monthly Relative index scores."""
    reader = csv.reader(io.StringIO(csv_text))
    header_row: list[str] | None = None
    economic_data: list[ScrapingResult] = []
    for row in reader:
        if not row:
            continue
        # Skip the title line; the next non-empty row is the column header.
        if header_row is None:
            if row[0].strip().lower().startswith("month"):
                header_row = [cell.strip() for cell in row]
            continue
        if len(row) < 7:
            continue
        try:
            month = int(row[0])
            year = int(row[1])
            relative_score = float(row[6])
        except (TypeError, ValueError):
            continue
        if month < 1 or month > 12:
            continue
        economic_data.append(
            ScrapingResult(
                period=date(year, month, 1),
                data_value=relative_score,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _fetch_univ_michigan_sca_table_scraping_results(
    table_number: int,
) -> list[ScrapingResult]:
    """POST one Michigan SCA table export and parse monthly relative scores."""
    response = requests.post(
        MICHIGAN_SCA_DATA_ARCHIVE_URL,
        data={
            "table": str(table_number),
            "year": "",
            "format": "Comma-Separated (CSV)",
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Michigan SCA table: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        economic_data = _parse_univ_michigan_sca_table_csv(response.text)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing Michigan SCA CSV: {exc}",
            )
        ]
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Michigan SCA values found.",
            )
        ]
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_univ_michigan(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get a Surveys of Consumers table index from the Michigan data archive.

    Supported tickers map to SCA table numbers (e.g. 'sca_table_30' → Table 30
    Expected Change in Unemployment During the Next Year Relative score).

    Source: https://data.sca.isr.umich.edu/data-archive/mine.php
    """
    table_number = MICHIGAN_SCA_TABLE_BY_TICKER.get(ticker)
    if table_number is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Michigan ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for Michigan scrape: {frequency}",
            )
        ]

    economic_data = _fetch_univ_michigan_sca_table_scraping_results(table_number)
    # A failed scrape returns exactly one empty error result at index 0.
    if economic_data[0]["data_value"] is None:
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (Michigan / FRED calendar)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_univ_michigan(_: str) -> list[datetime]:
    """Get University of Michigan release dates via the FRED SCA calendar.

    FRED release 91 mirrors the SCA publication dates; local clock is 10:00 ET.
    """
    return get_publication_dates_from_fred(MICHIGAN_SCA_FRED_TECHNICAL_NAME)
