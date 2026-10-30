"""Scrape rates from Banque de France Webstat."""

from datetime import date
from io import StringIO

import pandas as pd
import requests
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.config import WEBSTAT_RATE_URL


def _parse_str_decimals_to_float(decimal_text: str) -> float | None:
    """Parse French and English string decimals to float."""
    return (
        float(str(decimal_text).replace(",", ".")) if pd.notna(decimal_text) else None
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_webstat_rates(target_date: date, ticker: str) -> ScrapingResult:
    """Get Webstat data.

    Source: https://webstat.banque-france.fr/en/
    """
    response = requests.get(f"{WEBSTAT_RATE_URL}/{ticker}")
    if response.status_code >= 400:
        logger.warning(f"Error scraping Webstat rates: {response.text}")
        return ScrapingResult(price=None, comment=response.text)

    csv_data = StringIO(response.text)
    prices = pd.read_csv(csv_data, sep=";")
    closing_price_series = prices[
        pd.to_datetime(prices["time_period"]).dt.date == target_date
    ].reset_index()
    if not closing_price_series.empty:
        closing_price_str = closing_price_series.loc[0, "obs_value"]
        try:
            return ScrapingResult(
                price=_parse_str_decimals_to_float(str(closing_price_str)), comment=""
            )
        except ValueError:
            return ScrapingResult(
                price=None,
                comment=f"Could not convert rate to float: {closing_price_str}",
            )
    return ScrapingResult(price=None, comment="Webstat rate not found.")
