"""Swissinfo news scraper (Bloomberg Markets Wrap)."""

from datetime import date

import requests
from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger, parse_datetime
from market_analysis.services.scrapers.common import ArticleLink, ScrapingResult
from market_analysis.services.scrapers.html_text import extract_main_text
from market_analysis.services.config import (
    HTTP_REQUEST_TIMEOUT_SECONDS,
    SWISSINFO_LIST_URL,
)


def _parse_swissinfo_market_wrap_card(
    html: str, reporting_date: date
) -> ArticleLink | None:
    """Pick the Markets Wrap teaser card whose published date matches."""
    soup = BeautifulSoup(html, "lxml")

    for card in soup.select("article.teaser-wide-card"):
        if not isinstance(card, Tag):
            continue
        title_el = card.select_one(".teaser-wide-card__title")
        link_el = card.select_one("a.teaser-wide-card__link[href]")
        time_el = card.select_one("time[datetime]")
        if not isinstance(title_el, Tag) or not isinstance(link_el, Tag):
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        if "markets wrap" not in title.lower():
            continue
        datetime_attr = time_el.get("datetime") if isinstance(time_el, Tag) else None
        card_datetime = (
            parse_datetime(datetime_attr) if isinstance(datetime_attr, str) else None
        )
        if card_datetime is None or card_datetime.date() != reporting_date:
            continue
        href_attr = link_el.get("href")
        if not isinstance(href_attr, str):
            continue
        return ArticleLink(
            title=title,
            url=href_attr,
        )
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_swissinfo_market_wrap(reporting_date: date) -> ScrapingResult:
    """Scrape Swissinfo Bloomberg listing → Markets Wrap for ``reporting_date``."""
    try:
        article_listing_response = requests.get(
            SWISSINFO_LIST_URL, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        )
        article_listing_response.raise_for_status()
        article_link = _parse_swissinfo_market_wrap_card(
            article_listing_response.text, reporting_date
        )
        if not article_link:
            return ScrapingResult(
                url=None,
                title=None,
                content=None,
                comment=(
                    f"No Swissinfo Markets Wrap found for "
                    f"{reporting_date.isoformat()} on {SWISSINFO_LIST_URL}"
                ),
            )
        article_response = requests.get(
            article_link["url"], timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        )
        article_response.raise_for_status()
        return ScrapingResult(
            url=article_link["url"],
            title=(article_link.get("title") or "")[:500],
            content=extract_main_text(article_response.text),
            comment=None,
        )
    except Exception as exc:
        logger.error("Swissinfo Markets Wrap scrape failed: %s", exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))
