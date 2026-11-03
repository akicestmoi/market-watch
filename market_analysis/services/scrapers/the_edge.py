"""The Edge Malaysia Global+Markets flash scraper."""

import json
from datetime import date, datetime
from typing import TypedDict
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_analysis.services.config import (
    THE_EDGE_BASE_URL,
    THE_EDGE_GLOBAL_MARKETS_LIST_URL,
)
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    extract_main_text,
    scrap_article_from_listing,
)

# The Edge Malaysia publishes Global Markets flashes on Asia morning clocks; the
# dateline session day matches Asia/Kuala_Lumpur better than America/New_York.
_EDGE_PUBLISH_TIMEZONE = "Asia/Kuala_Lumpur"
_GLOBAL_WRAP_TITLE_CUES = [
    "stocks",
    "bonds",
    "bond ",
    "markets",
    "wall street",
    "global",
    "equities",
    "investors",
]


class _EdgeFlashArticle(TypedDict, total=False):
    """Subset of The Edge flash card fields used for selection."""

    nid: int
    title: str
    created: int
    flash: str
    alias: str


class _EdgePageProps(TypedDict, total=False):
    """'pageProps' from The Edge flash category '__NEXT_DATA__'."""

    corporateData: list[_EdgeFlashArticle]


class _EdgeProps(TypedDict, total=False):
    """'props' wrapper in '__NEXT_DATA__'."""

    pageProps: _EdgePageProps


class _EdgeNextData(TypedDict, total=False):
    """Root '__NEXT_DATA__' payload for the Global+Markets flash page."""

    props: _EdgeProps


_EDGE_NEXT_DATA_ADAPTER = TypeAdapter(_EdgeNextData)


class _EdgeArticleData(TypedDict, total=False):
    """Article payload nested under article-page 'pageProps.data'."""

    title: str
    content: str
    summary: str


class _EdgeArticlePageProps(TypedDict, total=False):
    """'pageProps' from an Edge article '__NEXT_DATA__'."""

    data: _EdgeArticleData


class _EdgeArticleProps(TypedDict, total=False):
    """'props' wrapper on an Edge article page."""

    pageProps: _EdgeArticlePageProps


class _EdgeArticleNextData(TypedDict, total=False):
    """Root '__NEXT_DATA__' payload for an Edge article page."""

    props: _EdgeArticleProps


_EDGE_ARTICLE_NEXT_DATA_ADAPTER = TypeAdapter(_EdgeArticleNextData)


def _convert_epoch_ms_to_timezone_date(epoch_ms: int, timezone_name: str) -> date:
    """Convert Unix epoch milliseconds to a calendar date in 'timezone_name'."""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=ZoneInfo(timezone_name)).date()


def _does_edge_title_look_like_global_wrap(title: str) -> bool:
    """Return True for Global Markets session-style flash titles."""
    normalized_title = " ".join(title.lower().split())
    if "haven from" in normalized_title or "hedge fund returns" in normalized_title:
        return False
    return any(cue in normalized_title for cue in _GLOBAL_WRAP_TITLE_CUES)


def _parse_the_edge_global_markets_card(
    html: str, reporting_date: date
) -> ArticleLink | None:
    """Pick a Global+Markets flash whose KL publish date matches 'reporting_date'."""
    soup = BeautifulSoup(html, "lxml")
    next_data_el = soup.find("script", id="__NEXT_DATA__")
    if not isinstance(next_data_el, Tag) or not next_data_el.string:
        return None
    try:
        raw_payload = json.loads(next_data_el.string)
        next_data = _EDGE_NEXT_DATA_ADAPTER.validate_python(raw_payload)
    except (json.JSONDecodeError, ValidationError):
        return None
    corporate_data = (
        next_data.get("props", {}).get("pageProps", {}).get("corporateData", [])
    )
    for flash_article in corporate_data:
        title = flash_article.get("title") or ""
        created_ms = flash_article.get("created")
        nid = flash_article.get("nid")
        if not title or created_ms is None or nid is None:
            continue
        if (
            _convert_epoch_ms_to_timezone_date(created_ms, _EDGE_PUBLISH_TIMEZONE)
            != reporting_date
        ):
            continue
        if not _does_edge_title_look_like_global_wrap(title):
            continue
        alias = flash_article.get("alias") or f"node/{nid}"
        return ArticleLink(
            title=title,
            url=urljoin(THE_EDGE_BASE_URL + "/", alias),
        )
    return None


def _extract_the_edge_article_text(html: str) -> str:
    """Extract article body from Edge '__NEXT_DATA__', falling back to HTML text."""
    soup = BeautifulSoup(html, "lxml")
    next_data_el = soup.find("script", id="__NEXT_DATA__")
    if isinstance(next_data_el, Tag) and next_data_el.string:
        try:
            raw_payload = json.loads(next_data_el.string)
            next_data = _EDGE_ARTICLE_NEXT_DATA_ADAPTER.validate_python(raw_payload)
            article_data = (
                next_data.get("props", {}).get("pageProps", {}).get("data", {})
            )
            content_html = article_data.get("content") or ""
            if content_html:
                return extract_main_text(content_html)
        except (json.JSONDecodeError, ValidationError):
            pass
    return extract_main_text(html)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_the_edge_global_markets(reporting_date: date) -> ScrapingResult:
    """Scrape The Edge Global+Markets → wrap for 'reporting_date'."""
    return scrap_article_from_listing(
        THE_EDGE_GLOBAL_MARKETS_LIST_URL,
        reporting_date,
        _parse_the_edge_global_markets_card,
        "The Edge Global Markets wrap",
        extract_article_text=_extract_the_edge_article_text,
    )
