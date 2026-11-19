"""Scrape METI retail sales and operating-ratio index workbooks."""

import io
import logging
import re
from collections.abc import Callable
from datetime import date, datetime

import openpyxl
import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    METI_OPERATING_RATIO_MANUFACTURING_LABEL,
    METI_OPERATING_RATIO_SHEET,
    METI_OPERATING_RATIO_TICKER,
    METI_OPERATING_RATIO_XLSX_URL,
    METI_RETAIL_SALES_INDEX_COLUMN,
    METI_RETAIL_SALES_INDEX_SHEET,
    METI_RETAIL_SALES_INDEX_TICKER,
    METI_RETAIL_SALES_INDEX_XLSX_URL,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)
from economic_overview.services.scrapers.stat_of_jp import (
    get_publication_dates_from_estat_for_technical_name,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (retail sales and operating ratio)
# __________________________________________________________

_METI_SCRAPER_BY_TICKER: dict[
    str, tuple[str, Callable[[bytes], list[ScrapingResult]]]
] = {
    METI_RETAIL_SALES_INDEX_TICKER: (
        METI_RETAIL_SALES_INDEX_XLSX_URL,
        lambda workbook_bytes: _parse_meti_retail_sales_index_workbook(workbook_bytes),
    ),
    METI_OPERATING_RATIO_TICKER: (
        METI_OPERATING_RATIO_XLSX_URL,
        lambda workbook_bytes: _parse_meti_operating_ratio_workbook(workbook_bytes),
    ),
}


def _parse_meti_month_code(period_code: str | int | float) -> date | None:
    """Parse METI time-axis codes such as '2026000808' into month-start dates."""
    match = re.fullmatch(r"(\d{4})00(\d{2})\2", str(period_code))
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def _parse_meti_yyyymm_header(period_code: str | int | float) -> date | None:
    """Parse wide-table month headers such as '202601' into month-start dates."""
    match = re.fullmatch(r"(\d{4})(\d{2})", str(period_code))
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def _parse_meti_retail_sales_index_workbook(
    workbook_bytes: bytes,
) -> list[ScrapingResult]:
    """Parse METI seasonally adjusted monthly retail trade index (2020=100)."""
    workbook = openpyxl.load_workbook(
        io.BytesIO(workbook_bytes), data_only=True, read_only=True
    )
    if METI_RETAIL_SALES_INDEX_SHEET not in workbook.sheetnames:
        return []
    worksheet = workbook[METI_RETAIL_SALES_INDEX_SHEET]
    economic_data: list[ScrapingResult] = []
    for worksheet_cells in worksheet.iter_rows(
        min_row=9,
        max_col=METI_RETAIL_SALES_INDEX_COLUMN,
        values_only=True,
    ):
        # Column 1 is the time-axis code; column 21 is retail trade total.
        period_code = worksheet_cells[0]
        value_cell = worksheet_cells[METI_RETAIL_SALES_INDEX_COLUMN - 1]
        if isinstance(period_code, bool) or not isinstance(
            period_code, (str, int, float)
        ):
            continue
        period = _parse_meti_month_code(period_code)
        if period is None:
            continue
        if isinstance(value_cell, bool) or not isinstance(value_cell, (int, float)):
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=float(value_cell), comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min, reverse=True
    )
    return economic_data


def _parse_meti_operating_ratio_workbook(
    workbook_bytes: bytes,
) -> list[ScrapingResult]:
    """Parse METI monthly SA manufacturing operating-ratio index (2020=100).

    Wide layout: row 3 holds YYYYMM headers from column 4 onward; the
    manufacturing-total industry row supplies the index values.
    """
    workbook = openpyxl.load_workbook(
        io.BytesIO(workbook_bytes), data_only=True, read_only=True
    )
    if METI_OPERATING_RATIO_SHEET not in workbook.sheetnames:
        return []
    worksheet = workbook[METI_OPERATING_RATIO_SHEET]
    worksheet_rows = list(worksheet.iter_rows(values_only=True))
    if len(worksheet_rows) < 4:
        return []
    # Row 3 (1-based) holds YYYYMM month headers starting at column 4.
    header_row = worksheet_rows[2]
    month_periods: list[tuple[int, date]] = []
    for column_index, header_cell in enumerate(header_row):
        if column_index < 3:
            continue
        if isinstance(header_cell, bool) or not isinstance(
            header_cell, (str, int, float)
        ):
            continue
        period = _parse_meti_yyyymm_header(header_cell)
        if period is not None:
            month_periods.append((column_index, period))
    manufacturing_row = next(
        (
            worksheet_row
            for worksheet_row in worksheet_rows[3:]
            if len(worksheet_row) > 1
            and worksheet_row[1] == METI_OPERATING_RATIO_MANUFACTURING_LABEL
        ),
        None,
    )
    if manufacturing_row is None:
        return []
    economic_data: list[ScrapingResult] = []
    for column_index, period in month_periods:
        if column_index >= len(manufacturing_row):
            continue
        value_cell = manufacturing_row[column_index]
        if isinstance(value_cell, bool) or not isinstance(value_cell, (int, float)):
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=float(value_cell), comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min, reverse=True
    )
    return economic_data


def _download_meti_workbook(workbook_url: str) -> bytes | None:
    """Download one METI / e-Stat Excel workbook."""
    response = requests.get(
        workbook_url,
        timeout=120,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping METI workbook: {response.text[:500]}")
        return None
    return response.content


def _fetch_meti_workbook_scraping_results(
    ticker: str,
    workbook_url: str,
    parse_workbook: Callable[[bytes], list[ScrapingResult]],
) -> list[ScrapingResult]:
    """Download and parse one METI Excel workbook for a seed ticker."""
    workbook_bytes = _download_meti_workbook(workbook_url)
    if workbook_bytes is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Could not download METI workbook for ticker={ticker}.",
            )
        ]
    try:
        economic_data = parse_workbook(workbook_bytes)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing METI workbook for ticker={ticker}: {exc}",
            )
        ]
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No METI values found for ticker={ticker}.",
            )
        ]
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_meti(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get a METI monthly index series by seed ticker.

    Supported tickers:
    - 'retail_sales_index_sa' nationwide SA retail trade (2020=100)
    - 'operating_ratio_mfg_sa' manufacturing SA operating ratio (2020=100)

    Operating ratio stays on the Excel time-series workbook because the matching
    e-Stat getStatsData table currently lags the published file by several months.
    """
    scraper = _METI_SCRAPER_BY_TICKER.get(ticker)
    if scraper is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported METI ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for METI scrape: {frequency}",
            )
        ]

    workbook_url, parse_workbook = scraper
    economic_data = _fetch_meti_workbook_scraping_results(
        ticker, workbook_url, parse_workbook
    )
    # A failed scrape returns exactly one empty error result at index 0.
    if economic_data[0]["data_value"] is None:
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (e-Stat calendar)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_meti(name: str) -> list[datetime]:
    """Get upcoming METI dates from the e-Stat release calendar.

    Retail commerce uses 商業動態速報 slots; operating ratio follows the
    preliminary IIP release that updates the capacity workbook.
    """
    return get_publication_dates_from_estat_for_technical_name(name)
