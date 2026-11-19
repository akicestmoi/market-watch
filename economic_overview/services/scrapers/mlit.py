"""Scrape Japan MLIT residential property price index (RPPI)."""

import io
import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

import openpyxl
import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    MLIT_RPPI_INDEX_COLUMN_BY_TICKER,
    MLIT_RPPI_PAGE_URL,
    MLIT_RPPI_SHEET,
    MLIT_SITE_ORIGIN,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (residential property price index)
# __________________________________________________________


def _get_mlit_rppi_xlsx_url() -> str | None:
    """Resolve the nationwide Residential Property Price Index Excel URL."""
    response = requests.get(
        MLIT_RPPI_PAGE_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        return None
    # requests may default text/html without charset to Latin-1; page is UTF-8.
    page_html = response.content.decode("utf-8")
    # First "不動産価格指数（住宅）" Excel under 最新データ.
    match = re.search(
        r"不動産価格指数（住宅）</td>\s*<td[^>]*>\s*"
        r'<a href="(/totikensangyo/content/[^"]+\.xlsx)"',
        page_html,
    )
    if not match:
        return None
    return urljoin(MLIT_SITE_ORIGIN, match.group(1))


def _parse_mlit_rppi_workbook(
    workbook_bytes: bytes, index_column: int
) -> list[ScrapingResult]:
    """Parse one nationwide SA RPPI index column from the MLIT workbook."""
    workbook = openpyxl.load_workbook(
        io.BytesIO(workbook_bytes), data_only=True, read_only=True
    )
    if MLIT_RPPI_SHEET not in workbook.sheetnames:
        return []
    worksheet = workbook[MLIT_RPPI_SHEET]
    economic_data: list[ScrapingResult] = []
    for worksheet_cells in worksheet.iter_rows(
        min_row=10, max_col=index_column, values_only=True
    ):
        # Period is always column A; the series index is at 'index_column'.
        period_cell = worksheet_cells[0]
        value_cell = worksheet_cells[index_column - 1]
        if period_cell is None or value_cell is None:
            continue
        if isinstance(period_cell, datetime):
            period = period_cell.date().replace(day=1)
        elif isinstance(period_cell, date):
            period = period_cell.replace(day=1)
        else:
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


def _fetch_mlit_rppi_scraping_results(
    index_column: int,
) -> list[ScrapingResult]:
    """Download and parse the nationwide MLIT RPPI workbook."""
    xlsx_url = _get_mlit_rppi_xlsx_url()
    if xlsx_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Could not resolve MLIT RPPI Excel URL.",
            )
        ]

    response = requests.get(
        xlsx_url,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping MLIT RPPI: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        economic_data = _parse_mlit_rppi_workbook(response.content, index_column)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing MLIT RPPI workbook: {exc}",
            )
        ]
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No MLIT RPPI values found."
            )
        ]
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_mlit(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get Japan Residential Property Price Index from MLIT Excel releases.

    Supported tickers are nationwide SA Detached House ('detached_house_sa') and
    Condominiums ('condominiums_sa') index columns.

    Source: https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html
    """
    index_column = MLIT_RPPI_INDEX_COLUMN_BY_TICKER.get(ticker)
    if index_column is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported MLIT ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for MLIT scrape: {frequency}",
            )
        ]

    economic_data = _fetch_mlit_rppi_scraping_results(index_column)
    # A failed scrape returns exactly one empty error result at index 0.
    if economic_data[0]["data_value"] is None:
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (MONTHLY_UPDATE — no calendar scrape)
# __________________________________________________________


def get_publication_dates_from_mlit(_: str) -> list[datetime]:
    """Seeds use MONTHLY_UPDATE, so no release calendar is scraped."""
    return []
