"""Scrape Nikkei 225 constituent weights from the official Nikkei CSV."""

import csv
import io
import logging

import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_overview.services.config import NIKKEI_WEIGHT_CSV_URL

logger = logging.getLogger(__name__)


def _parse_weight_percent(raw_weight: str) -> float:
    """Parse a Nikkei weight cell such as '1.5067%' into a float percent."""
    cleaned = raw_weight.strip().removesuffix("%").strip()
    return float(cleaned)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_nikkei_weights_from_official_csv() -> dict[str, float]:
    """
    Return official Nikkei 225 weights keyed by Yahoo ticker (CODE.T).

    Values are percent of the index (for example 1.5 means 1.5%).
    """
    # Usage of dict: keys are Yahoo tickers; values are weight percents.
    response = requests.get(NIKKEI_WEIGHT_CSV_URL, timeout=60)
    response.raise_for_status()
    text = response.content.decode("cp932")
    reader = csv.DictReader(io.StringIO(text))
    weights: dict[str, float] = {}
    for row in reader:
        code = (row.get("Code") or "").strip()
        raw_weight = (row.get("Weight") or "").strip()
        if not code or not raw_weight:
            continue
        weights[f"{code}.T"] = _parse_weight_percent(raw_weight)
    if not weights:
        raise ValueError("Nikkei weight CSV returned no constituent weights.")
    logger.info("Loaded %s Nikkei weights from official CSV.", len(weights))
    return weights
