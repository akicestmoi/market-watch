"""Swissinfo news scraper (Bloomberg Markets Wrap)."""

from datetime import date
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import parse_datetime
from market_analysis.services.config import SWISSINFO_LIST_URL
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    scrap_article_from_listing,
)

# Markets Wrap covers the US cash session; overnight Europe publishes land on
# the prior New York calendar date (e.g. Sat 01:32 Paris → Friday session).
_SWISSINFO_SESSION_TIMEZONE = ZoneInfo("America/New_York")


def _parse_swissinfo_market_wrap_card(
    html: str, reporting_date: date
) -> ArticleLink | None:
    """Pick the Markets Wrap teaser card whose US session date matches."""
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
        if card_datetime is None:
            continue
        card_session_date = card_datetime.astimezone(_SWISSINFO_SESSION_TIMEZONE).date()
        if card_session_date != reporting_date:
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
    """Scrape Swissinfo Bloomberg listing → Markets Wrap for 'reporting_date'."""
    return scrap_article_from_listing(
        SWISSINFO_LIST_URL,
        reporting_date,
        _parse_swissinfo_market_wrap_card,
        "Swissinfo Markets Wrap",
    )
