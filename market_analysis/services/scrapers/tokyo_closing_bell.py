"""Tokyo Closing Bell scraper (daily English Nikkei session wrap)."""

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import parse_datetime
from market_analysis.services.config import TOKYO_CLOSING_BELL_LIST_URL
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    scrap_article_from_listing,
)

_SESSION_DATE_IN_URL_PATTERN = re.compile(r"(?:^|/|-)(\d{4})-(\d{2})-(\d{2})(?:/|$)")


def _parse_session_date_from_url(url: str) -> date | None:
    """Extract 'YYYY-MM-DD' session date from a Tokyo Closing Bell URL slug."""
    match = _SESSION_DATE_IN_URL_PATTERN.search(url)
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day)


def _parse_tokyo_closing_bell_card(
    html: str, reporting_date: date
) -> ArticleLink | None:
    """Pick the homepage post whose session date matches 'reporting_date'."""
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("article"):
        if not isinstance(card, Tag):
            continue
        title_el = card.select_one("h2 a, h2, .entry-title a, .entry-title")
        link_el = card.select_one("h2 a, .entry-title a, a[rel=bookmark]")
        time_el = card.select_one("time[datetime]")
        if not isinstance(title_el, Tag) or not isinstance(link_el, Tag):
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        if "nikkei" not in title.lower():
            continue
        href_attr = link_el.get("href")
        if not isinstance(href_attr, str):
            continue
        article_url = urljoin(TOKYO_CLOSING_BELL_LIST_URL, href_attr)
        session_date = _parse_session_date_from_url(article_url)
        if session_date is None:
            datetime_attr = (
                time_el.get("datetime") if isinstance(time_el, Tag) else None
            )
            card_datetime = (
                parse_datetime(datetime_attr)
                if isinstance(datetime_attr, str)
                else None
            )
            session_date = card_datetime.date() if card_datetime is not None else None
        if session_date != reporting_date:
            continue
        return ArticleLink(title=title, url=article_url)
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_tokyo_closing_bell(reporting_date: date) -> ScrapingResult:
    """Scrape Tokyo Closing Bell homepage → Nikkei wrap for 'reporting_date'."""
    return scrap_article_from_listing(
        TOKYO_CLOSING_BELL_LIST_URL,
        reporting_date,
        _parse_tokyo_closing_bell_card,
        "Tokyo Closing Bell wrap",
    )
