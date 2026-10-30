"""Boursier.com news scraper (Clôture Paris daily wrap)."""

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from curl_cffi import requests as curl_requests

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_analysis.services.config import (
    BOURSIER_DAY_URL_TEMPLATE,
    HTTP_REQUEST_TIMEOUT_SECONDS,
)
from market_analysis.services.scrapers.common import ArticleLink, ScrapingResult
from market_analysis.services.scrapers.html_text import extract_main_text


def _parse_boursier_cloture_link(html: str, base_url: str) -> ArticleLink | None:
    """Find the first article link whose visible text starts with ``Clôture Paris``."""
    soup = BeautifulSoup(html, "lxml")
    cloture_paris_pattern = re.compile(r"^\s*Cl[oô]ture\s+Paris\b", re.IGNORECASE)

    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not cloture_paris_pattern.match(title):
            continue
        href_attr = anchor.get("href")
        if not isinstance(href_attr, str):
            continue
        href = href_attr.strip()
        if not href or href.startswith("#"):
            continue
        return ArticleLink(
            title=title,
            url=urljoin(base_url, href),
        )
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_boursier_cloture_paris(reporting_date: date) -> ScrapingResult:
    """Scrape Boursier day index → Clôture Paris article for ``reporting_date``."""
    listing_url = BOURSIER_DAY_URL_TEMPLATE.format(
        yyyymmdd=reporting_date.strftime("%Y%m%d")
    )
    try:
        article_listing_response = curl_requests.get(
            listing_url,
            impersonate="chrome",
            timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        article_listing_response.raise_for_status()
        article_link = _parse_boursier_cloture_link(
            article_listing_response.text, base_url=listing_url
        )
        if not article_link:
            return ScrapingResult(
                url=None,
                title=None,
                content=None,
                comment=f"No 'Clôture Paris' article found on {listing_url}",
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
        logger.error("Boursier Clôture Paris scrape failed: %s", exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))
