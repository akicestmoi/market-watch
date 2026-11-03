"""Shared TypedDicts and helpers for news article scrapers."""

from collections.abc import Callable
from datetime import date
from typing import TypedDict

import requests
from bs4 import BeautifulSoup, Tag
from curl_cffi import requests as curl_requests

from core.services import logger, parse_datetime
from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.config import (
    HTTP_REQUEST_TIMEOUT_SECONDS,
    MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION,
    MARKET_WRAP_TITLE_EXCLUDE_CUES,
)

_STRIP_TAGS = ("script", "style", "noscript", "svg", "iframe")
_STRIP_SELECTORS = (
    "nav",
    "header",
    "footer",
    "aside",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
)

# Prefer explicit article-body containers before a generic '<article>' (TBS and
# similar pages put related-story cards in '<article>' ahead of the main body).
_MAIN_TEXT_SELECTORS = (
    ".article-body",
    ".article-main",
    "[itemprop='articleBody']",
    "main",
    "[role='main']",
    "article",
)


class ArticleLink(TypedDict):
    """Title and URL discovered on a listing page before body fetch."""

    title: str
    url: str


class ScrapingResult(TypedDict):
    """Scraped article fields or a miss comment from one news source."""

    url: str | None
    title: str | None
    content: str | None
    comment: str | None


class TaggedScrapingResult(TypedDict):
    """Scraping result tagged with one or more UI catalog regions."""

    regions: list[ArticleRegionChoices]
    url: str | None
    title: str | None
    content: str | None
    comment: str | None


def tag_scraping_result(
    scraping_result: ScrapingResult,
    regions: list[ArticleRegionChoices],
) -> TaggedScrapingResult:
    """Attach catalog regions to a plain 'ScrapingResult'."""
    return TaggedScrapingResult(
        regions=list(regions),
        url=scraping_result.get("url"),
        title=scraping_result.get("title"),
        content=scraping_result.get("content"),
        comment=scraping_result.get("comment"),
    )


def _does_title_match_any_cue(title: str, cues: list[str]) -> bool:
    """Return True when normalized 'title' contains any cue substring."""
    # Collapse whitespace and lowercase a title for cue matching.
    normalized_title = " ".join(title.lower().split())
    return any(cue in normalized_title for cue in cues)


def does_title_look_like_market_wrap(title: str, close_cues: list[str]) -> bool:
    """Return True when title matches close cues and is not an open/preview."""
    if _does_title_match_any_cue(title, MARKET_WRAP_TITLE_EXCLUDE_CUES):
        return False
    return _does_title_match_any_cue(title, close_cues)


def parse_article_published_date(html: str) -> date | None:
    """Parse 'article:published_time' (or 'time[datetime]') from article HTML."""
    soup = BeautifulSoup(html, "lxml")
    for meta in soup.select(
        'meta[property="article:published_time"], '
        'meta[property="og:article:published_time"], '
        'meta[name="date"], '
        'meta[name="pubdate"]'
    ):
        if not isinstance(meta, Tag):
            continue
        content = meta.get("content")
        if not isinstance(content, str):
            continue
        published_datetime = parse_datetime(content)
        if published_datetime is not None:
            return published_datetime.date()
    for time_el in soup.select("time[datetime]"):
        if not isinstance(time_el, Tag):
            continue
        datetime_attr = time_el.get("datetime")
        if not isinstance(datetime_attr, str):
            continue
        published_datetime = parse_datetime(datetime_attr)
        if published_datetime is not None:
            return published_datetime.date()
    return None


def _does_class_name_contain_article(
    class_name: str | list[str] | None,
) -> bool:
    """Return True when a CSS class token contains 'article'."""
    if class_name is None:
        return False
    if isinstance(class_name, list):
        return any(
            isinstance(token, str) and "article" in token.lower()
            for token in class_name
        )
    return "article" in class_name.lower()


def extract_main_text(html: str) -> str:
    """Extract readable article text with BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        if isinstance(tag, Tag):
            tag.decompose()
    for selector in _STRIP_SELECTORS:
        for tag in soup.select(selector):
            if isinstance(tag, Tag):
                tag.decompose()

    root_candidate: Tag | None = None
    for selector in _MAIN_TEXT_SELECTORS:
        found = soup.select_one(selector)
        if isinstance(found, Tag):
            root_candidate = found
            break
    if root_candidate is None:
        found_by_class = soup.find(class_=_does_class_name_contain_article)
        if isinstance(found_by_class, Tag):
            root_candidate = found_by_class
        elif isinstance(soup.body, Tag):
            root_candidate = soup.body
        else:
            root_candidate = soup

    text = root_candidate.get_text("\n", strip=True)
    lines = [ln for ln in (line.strip() for line in text.splitlines()) if ln]
    return "\n".join(lines).strip()


def pick_article_matching_published_date(
    candidates: list[ArticleLink],
    reporting_date: date,
) -> ScrapingResult | None:
    """Fetch candidate pages (curl/chrome) until published date matches."""
    for candidate in candidates:
        try:
            article_response = curl_requests.get(
                candidate["url"],
                impersonate="chrome",
                timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
            )
            article_response.raise_for_status()
        except Exception:
            continue
        published_date = parse_article_published_date(article_response.text)
        if published_date != reporting_date:
            continue
        return ScrapingResult(
            url=candidate["url"],
            title=(candidate.get("title") or "")[:500],
            content=extract_main_text(article_response.text),
            comment=None,
        )
    return None


def scrap_tagged_region_closes(
    source: NewsSourceChoices,
    reporting_date: date,
    region: ArticleRegionChoices | None,
    scrap_region_close: Callable[[date, list[str], str], ScrapingResult],
) -> list[TaggedScrapingResult]:
    """Scrape close wraps for 'source' regions and tag each result.

    When 'region' is set, only that region's close wrap is scraped.
    """
    targets = [
        (article_region, close_cues)
        for (cue_source, article_region), close_cues in (
            MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION.items()
        )
        if cue_source == source and (region is None or article_region == region)
    ]
    tagged_results: list[TaggedScrapingResult] = []
    for article_region, close_cues in targets:
        scraping_result = scrap_region_close(
            reporting_date,
            close_cues,
            article_region.value,
        )
        tagged_results.append(
            tag_scraping_result(scraping_result, regions=[article_region])
        )
    return tagged_results


def scrap_article_from_listing(
    listing_url: str,
    reporting_date: date,
    parse_listing_card: Callable[[str, date], ArticleLink | None],
    source_label: str,
    *,
    extract_article_text: Callable[[str], str] | None = None,
) -> ScrapingResult:
    """Scrape one article discovered from a listing page for 'reporting_date'.

    Uses 'requests' (not curl_cffi). Pass 'extract_article_text' when the source
    needs a custom body extractor; defaults to 'extract_main_text'.
    """
    extract_body = (
        extract_article_text if extract_article_text is not None else extract_main_text
    )
    try:
        article_listing_response = requests.get(
            listing_url, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        )
        article_listing_response.raise_for_status()
        article_link = parse_listing_card(article_listing_response.text, reporting_date)
        if article_link is None:
            return ScrapingResult(
                url=None,
                title=None,
                content=None,
                comment=(
                    f"No {source_label} found for "
                    f"{reporting_date.isoformat()} on {listing_url}"
                ),
            )
        article_response = requests.get(
            article_link["url"], timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        )
        article_response.raise_for_status()
        return ScrapingResult(
            url=article_link["url"],
            title=(article_link.get("title") or "")[:500],
            content=extract_body(article_response.text),
            comment=None,
        )
    except Exception as exc:
        logger.error("%s scrape failed: %s", source_label, exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))
