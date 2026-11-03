"""TBS CROSS DIG with Bloomberg 市況 wrap scrapers (Japan / US)."""

import re
from datetime import date
from functools import partial
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import parse_datetime
from market_analysis.services.config import (
    TBS_BASE_URL,
    TBS_JAPAN_MARKETS_LIST_URL,
    TBS_US_MARKETS_LIST_URL,
)
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    scrap_article_from_listing,
)

_TBS_LISTING_DATE_PATTERN = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})$")


def _parse_tbs_listing_date(raw_date: str) -> date | None:
    """Parse TBS listing dates shaped like '2026.10.30'."""
    match = _TBS_LISTING_DATE_PATTERN.match(raw_date.strip())
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day)


def _parse_tbs_markets_card(
    html: str,
    reporting_date: date,
    title_marker: str,
) -> ArticleLink | None:
    """Pick the newest 市況 card for 'reporting_date' (listing is newest-first)."""
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("article.m-article"):
        if not isinstance(card, Tag):
            continue
        link_el = card.select_one("a.m-article__link[href], a[href]")
        title_el = card.select_one(".m-article__ttl")
        time_el = card.select_one("time.m-article__date, time[datetime]")
        if not isinstance(link_el, Tag):
            continue
        title = (
            " ".join(title_el.get_text(" ", strip=True).split())
            if isinstance(title_el, Tag)
            else " ".join(link_el.get_text(" ", strip=True).split())
        )
        if title_marker not in title:
            continue
        card_date: date | None = None
        if isinstance(time_el, Tag):
            datetime_attr = time_el.get("datetime")
            if isinstance(datetime_attr, str):
                card_datetime = parse_datetime(datetime_attr)
                if card_datetime is not None:
                    card_date = card_datetime.date()
            if card_date is None:
                card_date = _parse_tbs_listing_date(time_el.get_text(" ", strip=True))
        if card_date is None:
            for part in card.stripped_strings:
                card_date = _parse_tbs_listing_date(part)
                if card_date is not None:
                    break
        if card_date != reporting_date:
            continue
        href_attr = link_el.get("href")
        if not isinstance(href_attr, str):
            continue
        return ArticleLink(
            title=title,
            url=urljoin(TBS_BASE_URL, href_attr),
        )
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_tbs_japan_markets(reporting_date: date) -> ScrapingResult:
    """Scrape TBS Bloomberg 日本市況 search → newest wrap for 'reporting_date'."""
    return scrap_article_from_listing(
        TBS_JAPAN_MARKETS_LIST_URL,
        reporting_date,
        partial(_parse_tbs_markets_card, title_marker="【日本市況】"),
        "TBS Japan markets wrap",
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_tbs_us_markets(reporting_date: date) -> ScrapingResult:
    """Scrape TBS Bloomberg 米国市況 search → newest wrap for 'reporting_date'."""
    return scrap_article_from_listing(
        TBS_US_MARKETS_LIST_URL,
        reporting_date,
        partial(_parse_tbs_markets_card, title_marker="【米国市況】"),
        "TBS US markets wrap",
    )
