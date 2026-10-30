"""Scrape the Mutan rate from the Bank of Japan website."""

from datetime import date
from io import BytesIO

import pandas as pd
import requests
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.config import BOJ_MUTAN_RATE_URL


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_mutan_rate_from_boj(target_date: date) -> ScrapingResult:
    """Scrap BoJ website to get Mutan Rate.

    Source: https://www.boj.or.jp/statistics/market/short/mutan/index.htm
    """
    DATA_TYPE = {"prevision": "mp", "certified": "md"}
    file_name = f"{DATA_TYPE['certified']}{target_date.strftime('%Y%m%d')}.xlsx"
    response = requests.get(
        f"{BOJ_MUTAN_RATE_URL}/{DATA_TYPE['certified']}/{target_date.year}/{file_name}"
    )
    if response.status_code != 200:
        file_name = f"{DATA_TYPE['prevision']}{target_date.strftime('%Y%m%d')}.xlsx"
        response = requests.get(
            f"{BOJ_MUTAN_RATE_URL}/{DATA_TYPE['prevision']}/{file_name}"
        )
        if response.status_code >= 400:
            logger.warning(f"Error scraping BoJ rates: {response.text}")
            return ScrapingResult(price=None, comment=response.text)

    df = pd.read_excel(BytesIO(response.content))
    matches = df.map(lambda x: "Average" in str(x))
    match_locations = [(i, j) for i, j in zip(*matches.to_numpy().nonzero())]
    if len(match_locations) > 1:
        return ScrapingResult(
            price=None, comment="BoJ file has likely changed. Review of code is needed."
        )

    mutan_location_row = match_locations[0][0]
    mutan_location_column = match_locations[0][1] + 1
    mutan_rate = df.iloc[mutan_location_row, mutan_location_column]
    if not pd.isna(df.iloc[mutan_location_row, mutan_location_column]):
        return ScrapingResult(price=float(str(mutan_rate)), comment="")
    return ScrapingResult(price=None, comment="Mutan rate not found.")
