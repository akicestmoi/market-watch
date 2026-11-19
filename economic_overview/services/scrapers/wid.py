"""Scrape World Inequality Database bulk country CSVs for wealth series."""

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
    WID_BULK_CSV_URL_TEMPLATE,
    WID_SERIES_BY_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (net personal wealth Gini and top-10 share)
# __________________________________________________________


def _parse_wid_bulk_csv(
    csv_text: str,
    *,
    variable: str,
    percentile: str,
    value_scale: float,
) -> list[ScrapingResult]:
    """Parse one WID bulk country CSV into scaled annual scraping results."""
    reader = csv.reader(io.StringIO(csv_text), delimiter=";")
    economic_data: list[ScrapingResult] = []
    for fields in reader:
        if len(fields) < 5:
            continue
        row_variable = fields[1].strip()
        row_percentile = fields[2].strip()
        if row_variable != variable or row_percentile != percentile:
            continue
        year_label = fields[3].strip()
        raw_value = fields[4].strip()
        if not year_label or not raw_value:
            continue
        try:
            year = int(year_label)
            data_value = float(raw_value) * value_scale
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(
                period=date(year, 1, 1),
                data_value=data_value,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _download_wid_country_csv(country_code: str) -> str | None:
    """Download one WID bulk country CSV, or None when the request fails."""
    url = WID_BULK_CSV_URL_TEMPLATE.format(country_code=country_code)
    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        logger.warning(
            f"Error scraping WID data for {country_code}: {response.text[:500]}"
        )
        return None
    return response.text


def _signal_unsupported_wid_scrape_error(
    ticker: str,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult] | None:
    """Return an error result when frequency or ticker is unsupported."""
    if frequency != EconomicPublicationFrequencyChoices.ANNUAL:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for WID scrape: {frequency}",
            )
        ]
    if ticker not in WID_SERIES_BY_TICKER:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported WID ticker: {ticker}",
            )
        ]
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_wid(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.ANNUAL,
    location: str = "US",
) -> list[ScrapingResult]:
    """Get WID net personal wealth series for one location.

    Source: https://wid.world/bulk_download/WID_data_{country}.csv
    Gini and top-10 share are stored ×100 to match ECB DWA 0–100 scales.
    """
    unsupported_error = _signal_unsupported_wid_scrape_error(ticker, frequency)
    if unsupported_error is not None:
        return unsupported_error
    series_config = WID_SERIES_BY_TICKER[ticker]
    csv_text = _download_wid_country_csv(location)
    if csv_text is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"WID request failed for location {location}.",
            )
        ]
    economic_data = _parse_wid_bulk_csv(
        csv_text,
        variable=series_config.variable,
        percentile=series_config.percentile,
        value_scale=series_config.value_scale,
    )
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No WID series values found."
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (MONTHLY_UPDATE — no calendar scrape)
# __________________________________________________________


def get_publication_dates_from_wid(_: str) -> list[datetime]:
    """Seeds use MONTHLY_UPDATE, so no release calendar is scraped."""
    return []
