"""Scrape S&P 500 constituent weights from the iShares IVV holdings CSV."""

import csv
import io
import logging

import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_overview.services.config import IVV_HOLDINGS_CSV_URL

logger = logging.getLogger(__name__)


def _normalize_ivv_ticker(raw_ticker: str) -> str:
    """Turn an IVV holdings ticker into the Yahoo-style catalog ticker."""
    return raw_ticker.strip().replace(" ", "-")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_spx_weights_from_ivv() -> dict[str, float]:
    """
    Return IVV equity market weights keyed by Yahoo ticker.

    Values are percent of the fund (for example 8.14 means 8.14%).
    """
    # Usage of dict: keys are Yahoo tickers; values are weight percents.
    response = requests.get(IVV_HOLDINGS_CSV_URL, timeout=60)
    response.raise_for_status()
    lines = response.text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.startswith("Ticker,")),
        None,
    )
    if header_index is None:
        raise ValueError("IVV holdings CSV has no Ticker header row.")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    weights: dict[str, float] = {}
    for row in reader:
        if row.get("Asset Class") != "Equity":
            continue
        raw_ticker = (row.get("Ticker") or "").strip()
        if not raw_ticker or raw_ticker == "-":
            continue
        weight_raw = (row.get("Market Weight") or "").strip()
        if not weight_raw or weight_raw == "-":
            continue
        weights[_normalize_ivv_ticker(raw_ticker)] = float(weight_raw)
    if not weights:
        raise ValueError("IVV holdings CSV returned no equity weights.")
    logger.info("Loaded %s SPX weights from IVV.", len(weights))
    return weights
