"""Scrape CAC 40 constituent weights from the whichindex proxy page."""

import logging
import re

import requests
from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_overview.services.config import (
    CAC40_WEIGHTS_PAGE_URL,
    CAC_YAHOO_TICKER_BY_INDEX_SYMBOL,
)

logger = logging.getLogger(__name__)


def _get_yahoo_ticker_for_cac_symbol(index_symbol: str) -> str:
    """Map a whichindex / Euronext symbol onto our Yahoo CAC ticker."""
    mapped = CAC_YAHOO_TICKER_BY_INDEX_SYMBOL.get(index_symbol)
    if mapped is not None:
        return mapped
    return f"{index_symbol}.PA"


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_cac_weights_from_whichindex() -> dict[str, float]:
    """
    Return CAC 40 ETF-proxy weights keyed by Yahoo ticker.

    Values are percent of the index proxy (for example 9.05 means 9.05%).
    """
    # Usage of dict: keys are Yahoo tickers; values are weight percents.
    response = requests.get(
        CAC40_WEIGHTS_PAGE_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=60,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):
        raise ValueError("whichindex CAC 40 page has no constituents table.")
    weights: dict[str, float] = {}
    # The first table row is the header, so the remaining rows are constituents.
    for row in table.find_all("tr")[1:]:
        if not isinstance(row, Tag):
            continue
        cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        index_symbol = cells[2]
        weight_raw = cells[3]
        if not index_symbol or not re.fullmatch(r"-?\d+(\.\d+)?", weight_raw):
            continue
        yahoo_ticker = _get_yahoo_ticker_for_cac_symbol(index_symbol)
        weights[yahoo_ticker] = float(weight_raw)
    if not weights:
        raise ValueError("whichindex CAC 40 page returned no constituent weights.")
    logger.info("Loaded %s CAC weights from whichindex.", len(weights))
    return weights
