"""CNBC Stock Market Daily Recap scraper (US session live wrap)."""

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from curl_cffi import requests as curl_requests

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_analysis.services.config import (
    CNBC_STOCK_MARKET_DAILY_RECAP_LIST_URL,
    HTTP_REQUEST_TIMEOUT_SECONDS,
)
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    extract_main_text,
)

_URL_DATE_PATTERN = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
_LIVE_UPDATE_PATH_MARKER = "stock-market-today-live-update"


def _parse_cnbc_stock_market_daily_recap_card(
    html: str, reporting_date: date
) -> ArticleLink | None:
    """Pick the daily-recap live update whose URL date matches 'reporting_date'."""
    soup = BeautifulSoup(html, "lxml")
    for link_el in soup.find_all("a", href=True):
        if not isinstance(link_el, Tag):
            continue
        href_attr = link_el.get("href")
        if not isinstance(href_attr, str):
            continue
        if _LIVE_UPDATE_PATH_MARKER not in href_attr.lower():
            continue
        title = " ".join(link_el.get_text(" ", strip=True).split())
        if len(title) < 20:
            continue
        article_url = urljoin(CNBC_STOCK_MARKET_DAILY_RECAP_LIST_URL, href_attr)
        match = _URL_DATE_PATTERN.search(article_url)
        if match is None:
            continue
        year, month, day = (int(part) for part in match.groups())
        if date(year, month, day) != reporting_date:
            continue
        return ArticleLink(title=title, url=article_url)
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_cnbc_stock_market_daily_recap(reporting_date: date) -> ScrapingResult:
    """Scrape CNBC Stock Market Daily Recap → live wrap for 'reporting_date'."""
    try:
        article_listing_response = curl_requests.get(
            CNBC_STOCK_MARKET_DAILY_RECAP_LIST_URL,
            impersonate="chrome",
            timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        article_listing_response.raise_for_status()
        article_link = _parse_cnbc_stock_market_daily_recap_card(
            article_listing_response.text, reporting_date
        )
        if not article_link:
            return ScrapingResult(
                url=None,
                title=None,
                content=None,
                comment=(
                    f"No CNBC Stock Market Daily Recap found for "
                    f"{reporting_date.isoformat()} on "
                    f"{CNBC_STOCK_MARKET_DAILY_RECAP_LIST_URL}"
                ),
            )
        article_response = curl_requests.get(
            article_link["url"],
            impersonate="chrome",
            timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        article_response.raise_for_status()
        return ScrapingResult(
            url=article_link["url"],
            title=(article_link.get("title") or "")[:500],
            content=extract_main_text(article_response.text),
            comment=None,
        )
    except Exception as exc:
        logger.error("CNBC Stock Market Daily Recap scrape failed: %s", exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))
