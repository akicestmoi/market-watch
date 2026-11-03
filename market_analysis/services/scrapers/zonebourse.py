"""Zonebourse market-close scrapers (US / Europe / France)."""

from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from curl_cffi import requests as curl_requests

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.config import (
    HTTP_REQUEST_TIMEOUT_SECONDS,
    ZONEBOURSE_ACTUALITES_LIST_URL,
    ZONEBOURSE_BASE_URL,
    ZONEBOURSE_CAC40_NEWS_LIST_URL,
    ZONEBOURSE_INDICES_LIST_URL,
)
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    TaggedScrapingResult,
    does_title_look_like_market_wrap,
    pick_article_matching_published_date,
    scrap_tagged_region_closes,
)


def _collect_zonebourse_candidates(
    html: str, close_cues: list[str]
) -> list[ArticleLink]:
    """Collect close/wrap article links from a Zonebourse listing page."""
    soup = BeautifulSoup(html, "lxml")
    candidates: list[ArticleLink] = []
    seen_urls: set[str] = set()
    for link_el in soup.find_all("a", href=True):
        if not isinstance(link_el, Tag):
            continue
        href_attr = link_el.get("href")
        if not isinstance(href_attr, str) or "/actualite-bourse/" not in href_attr:
            continue
        title = " ".join(link_el.get_text(" ", strip=True).split())
        if len(title) < 20:
            continue
        if not does_title_look_like_market_wrap(title, close_cues):
            continue
        article_url = urljoin(ZONEBOURSE_BASE_URL, href_attr)
        if article_url in seen_urls:
            continue
        seen_urls.add(article_url)
        candidates.append(ArticleLink(title=title, url=article_url))
    return candidates


def _scrap_zonebourse_region_close(
    reporting_date: date, close_cues: list[str], region_label: str
) -> ScrapingResult:
    """Scan Zonebourse actualités + indices feeds for a region close wrap."""
    try:
        candidates: list[ArticleLink] = []
        seen_urls: set[str] = set()
        for listing_url in (
            ZONEBOURSE_CAC40_NEWS_LIST_URL,
            ZONEBOURSE_INDICES_LIST_URL,
            ZONEBOURSE_ACTUALITES_LIST_URL,
        ):
            listing_response = curl_requests.get(
                listing_url,
                impersonate="chrome",
                timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
            )
            listing_response.raise_for_status()
            for candidate in _collect_zonebourse_candidates(
                listing_response.text, close_cues
            ):
                if candidate["url"] in seen_urls:
                    continue
                seen_urls.add(candidate["url"])
                candidates.append(candidate)
        scraping_result = pick_article_matching_published_date(
            candidates, reporting_date
        )
        if scraping_result is None:
            return ScrapingResult(
                url=None,
                title=None,
                content=None,
                comment=(
                    f"No Zonebourse {region_label} close wrap found for "
                    f"{reporting_date.isoformat()}"
                ),
            )
        return scraping_result
    except Exception as exc:
        logger.error("Zonebourse %s scrape failed: %s", region_label, exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_zonebourse(
    reporting_date: date,
    region: ArticleRegionChoices | None = None,
) -> list[TaggedScrapingResult]:
    """Scrape Zonebourse US / Europe / France close wraps for 'reporting_date'.

    When 'region' is set, only that region's close wrap is scraped.
    """
    return scrap_tagged_region_closes(
        NewsSourceChoices.ZONEBOURSE,
        reporting_date,
        region,
        _scrap_zonebourse_region_close,
    )
