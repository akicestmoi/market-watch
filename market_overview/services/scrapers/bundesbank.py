"""Scrape Bund yields from the Bundesbank database."""

import xml.etree.ElementTree as ET
from datetime import date

import requests
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.config import BUNDESBANK_RATE_URL


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_bund_yield_from_bundesbank(target_date: date, ticker: str) -> ScrapingResult:
    """Extract Bunds yield from Bundesbank database.

    Source: https://www.bundesbank.de/en/statistics/time-series-databases/
    """
    response = requests.get(f"{BUNDESBANK_RATE_URL}/{ticker}?format=sdmx&lang=en")
    if response.status_code >= 400:
        logger.warning(f"Error scraping Bundesbank rates: {response.text}")
        return ScrapingResult(price=None, comment=response.text)
    root = ET.fromstring(response.content)

    sdmx_namespaces = {
        "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic"
    }
    for obs in root.findall(".//generic:Obs", sdmx_namespaces):
        obs_date = obs.find("generic:ObsDimension", sdmx_namespaces)
        obs_value = obs.find("generic:ObsValue", sdmx_namespaces)
        if (
            obs_date is not None
            and obs_date.attrib.get("value") == target_date.isoformat()
        ):
            if obs_value is not None:
                return ScrapingResult(
                    price=float(obs_value.attrib["value"]), comment=""
                )
    return ScrapingResult(price=None, comment="Bunds rate not found.")
