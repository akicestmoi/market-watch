"""Scrape US Treasury yields from the Treasury department."""

import xml.etree.ElementTree as ET
from datetime import date

import requests
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_overview.services.scrapers.common import (
    ScrapingResult,
    YieldCurveScrapResult,
    YieldTermRate,
    get_yield_curve_rate,
)
from market_overview.services.config import DEPT_TREASURY_RATE_URL


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_treasury_yield_curve_from_dep_treasury(
    target_date: date,
) -> YieldCurveScrapResult:
    """
    Scrap entire UST yield curves from Treasury department.

    Source: https://home.treasury.gov/
    """
    response = requests.get(
        f"{DEPT_TREASURY_RATE_URL}&field_tdr_date_value={target_date.year}"
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Treasury yield curve: {response.text}")
        return YieldCurveScrapResult(rates=[], error=response.text)

    rates: list[YieldTermRate] = []
    root = ET.fromstring(response.content)
    sdmx_namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    }
    for entry in root.findall("atom:entry", sdmx_namespaces):
        obs_date = entry.find("atom:content/m:properties/d:NEW_DATE", sdmx_namespaces)
        if (
            obs_date is None
            or obs_date.text is None
            or not obs_date.text.startswith(target_date.isoformat())
        ):
            continue
        props = entry.find("atom:content/m:properties", sdmx_namespaces)
        if props is None:
            break
        for child in props:
            tag = child.tag.split("}")[1]  # Remove namespace
            if tag.startswith("BC_"):
                term = tag.replace("BC_", "")
                if child.text is None:
                    continue
                try:
                    rates.append(YieldTermRate(term=term, rate=float(child.text)))
                except (TypeError, ValueError):
                    continue
        break

    return YieldCurveScrapResult(rates=rates, error=None)


def get_treasury_yield_from_dep_treasury(
    target_date: date, ticker: str
) -> ScrapingResult:
    """Infer UST yield from Treasury department yield curve."""
    mapping = {
        "UST1M": "1MONTH",
        "UST2M": "2MONTH",
        "UST3M": "3MONTH",
        "UST6M": "6MONTH",
        "UST1Y": "1YEAR",
        "UST2Y": "2YEAR",
        "UST3Y": "3YEAR",
        "UST5Y": "5YEAR",
        "UST7Y": "7YEAR",
        "UST10Y": "10YEAR",
        "UST20Y": "20YEAR",
    }
    if ticker not in mapping.keys():
        return ScrapingResult(price=None, comment="Ticker not found in mapping.")
    curve = _get_treasury_yield_curve_from_dep_treasury(target_date)
    if curve["error"]:
        return ScrapingResult(price=None, comment=curve["error"])
    if not curve["rates"]:
        return ScrapingResult(price=None, comment="Yield curve not found.")
    return ScrapingResult(
        price=get_yield_curve_rate(curve, mapping[ticker]), comment=""
    )
