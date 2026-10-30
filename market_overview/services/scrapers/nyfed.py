"""Scrape rates from the New York Fed XML feed."""

import xml.etree.ElementTree as ET
from datetime import date

import requests
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.config import NY_FED_RATE_URL


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_rate_from_nyfed_xml(target_date: date, ticker: str) -> ScrapingResult:
    """Scrap rate from NY Fed XML.

    Source: https://www.newyorkfed.org/markets/reference-rates/
    """
    response = requests.get(f"{NY_FED_RATE_URL}&eventCodes={ticker}")
    if response.status_code >= 400:
        logger.warning(f"Error scraping rates from NY Fed XML: {response.text}")
        return ScrapingResult(price=None, comment=response.text)

    root = ET.fromstring(response.content)
    for rate in root.findall(".//rate"):
        effective_date_el = rate.find("effectiveDate")
        if effective_date_el is None or effective_date_el.text is None:
            continue
        if effective_date_el.text == target_date.isoformat():
            percent_rate_el = rate.find("percentRate")
            if percent_rate_el is not None and percent_rate_el.text:
                return ScrapingResult(price=float(percent_rate_el.text), comment="")
    return ScrapingResult(price=None, comment="Rate not found.")
