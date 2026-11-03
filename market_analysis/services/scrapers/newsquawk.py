"""Newsquawk headlines scraper (US Market Wrap)."""

from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import parse_datetime
from market_analysis.services.config import NEWSQUAWK_HEADLINES_LIST_URL
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    scrap_article_from_listing,
)


def _parse_newsquawk_us_market_wrap_card(
    html: str, reporting_date: date
) -> ArticleLink | None:
    """Pick the US Market Wrap headline whose published date matches."""
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("article.group"):
        if not isinstance(card, Tag):
            continue
        title_el = card.select_one("h2")
        link_el = card.select_one("a[href]")
        time_el = card.select_one("time[datetime]")
        if not isinstance(title_el, Tag) or not isinstance(link_el, Tag):
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        if "us market wrap" not in title.lower():
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
            url=urljoin(NEWSQUAWK_HEADLINES_LIST_URL, href_attr),
        )
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_newsquawk_us_market_wrap(reporting_date: date) -> ScrapingResult:
    """Scrape Newsquawk headlines → US Market Wrap for 'reporting_date'."""
    return scrap_article_from_listing(
        NEWSQUAWK_HEADLINES_LIST_URL,
        reporting_date,
        _parse_newsquawk_us_market_wrap_card,
        "Newsquawk US Market Wrap",
    )
