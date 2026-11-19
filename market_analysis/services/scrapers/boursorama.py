"""Boursorama market-close scrapers (France / Europe)."""

import logging
from datetime import date
from typing import NamedTuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from curl_cffi import requests as curl_requests

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.config import (
    BOURSORAMA_ACTUALITES_LIST_URL,
    BOURSORAMA_BASE_URL,
    BOURSORAMA_MARCHES_LIST_URL,
    BOURSORAMA_PROVIDER_RANK,
    HTTP_REQUEST_TIMEOUT_SECONDS,
)
from market_analysis.services.scrapers.common import (
    ArticleLink,
    ScrapingResult,
    TaggedScrapingResult,
    does_title_look_like_market_wrap,
    get_article_matching_published_date,
    scrap_tagged_region_closes,
)

logger = logging.getLogger(__name__)


class _BoursoramaCandidate(NamedTuple):
    """Ranked listing candidate before published-date verification."""

    title: str
    url: str
    provider: str
    provider_rank: int


def _parse_boursorama_provider(block_text: str) -> str:
    """Extract wire/provider name from a Boursorama listing card."""
    lowered = block_text.lower()
    for provider in ("reuters", "afp", "zonebourse", "boursorama"):
        if provider in lowered:
            return provider
    return ""


def _append_boursorama_listing_candidate(
    link_el: Tag,
    block_text: str,
    close_cues: list[str],
    seen_urls: set[str],
    candidates: list[_BoursoramaCandidate],
    *,
    title: str | None = None,
) -> None:
    """Append one listing candidate when the title matches close/wrap cues."""
    link_title = title
    if link_title is None:
        link_title = " ".join(link_el.get_text(" ", strip=True).split())
    if not does_title_look_like_market_wrap(link_title, close_cues):
        return
    href_attr = link_el.get("href")
    if not isinstance(href_attr, str):
        return
    article_url = urljoin(BOURSORAMA_BASE_URL, href_attr)
    if article_url in seen_urls:
        return
    seen_urls.add(article_url)
    provider = _parse_boursorama_provider(block_text)
    candidates.append(
        _BoursoramaCandidate(
            title=link_title,
            url=article_url,
            provider=provider,
            provider_rank=BOURSORAMA_PROVIDER_RANK.get(provider, 99),
        )
    )


def _collect_boursorama_candidates_from_news_lines(
    soup: BeautifulSoup,
    close_cues: list[str],
    seen_urls: set[str],
    candidates: list[_BoursoramaCandidate],
) -> None:
    """Collect wrap candidates from Boursorama news-line listing cards."""
    for line in soup.select("li.c-list-news__line"):
        if not isinstance(line, Tag):
            continue
        link_el = line.select_one("a[href]")
        if not isinstance(link_el, Tag):
            continue
        _append_boursorama_listing_candidate(
            link_el,
            line.get_text(" ", strip=True),
            close_cues,
            seen_urls,
            candidates,
        )


def _collect_boursorama_candidates_from_events(
    soup: BeautifulSoup,
    close_cues: list[str],
    seen_urls: set[str],
    candidates: list[_BoursoramaCandidate],
) -> None:
    """Collect wrap candidates from Boursorama à-la-une event cards."""
    for event in soup.select("div.c-event"):
        if not isinstance(event, Tag):
            continue
        link_el = event.select_one("a[href]")
        if not isinstance(link_el, Tag):
            continue
        title = " ".join(link_el.get_text(" ", strip=True).split())
        # Strip leading "information fournie par … DD mon." noise when present.
        if "information fournie par" in title.lower():
            # Title often trails the provider/date prefix in à-la-une cards.
            for cue in close_cues:
                cue_index = title.lower().find(cue)
                if cue_index >= 0:
                    title = title[cue_index:].strip()
                    break
        _append_boursorama_listing_candidate(
            link_el,
            event.get_text(" ", strip=True),
            close_cues,
            seen_urls,
            candidates,
            title=title,
        )


def _collect_boursorama_candidates(
    html: str, close_cues: list[str]
) -> list[_BoursoramaCandidate]:
    """Collect close/wrap candidates from a Boursorama listing page."""
    soup = BeautifulSoup(html, "lxml")
    candidates: list[_BoursoramaCandidate] = []
    seen_urls: set[str] = set()
    _collect_boursorama_candidates_from_news_lines(
        soup, close_cues, seen_urls, candidates
    )
    _collect_boursorama_candidates_from_events(soup, close_cues, seen_urls, candidates)
    candidates.sort(key=lambda candidate: candidate.provider_rank)
    return candidates


def _scrap_boursorama_region_close(
    reporting_date: date, close_cues: list[str], region_label: str
) -> ScrapingResult:
    """Scan Boursorama marches + actualités feeds for a region close wrap."""
    try:
        candidates: list[_BoursoramaCandidate] = []
        for listing_url in (
            BOURSORAMA_MARCHES_LIST_URL,
            BOURSORAMA_ACTUALITES_LIST_URL,
        ):
            listing_response = curl_requests.get(
                listing_url,
                impersonate="chrome",
                timeout=HTTP_REQUEST_TIMEOUT_SECONDS,
            )
            listing_response.raise_for_status()
            candidates.extend(
                _collect_boursorama_candidates(listing_response.text, close_cues)
            )
        # Re-rank across both listings; keep first URL occurrence.
        # Usage of dict: keys are article URLs; values are the best-ranked candidate.
        deduped_by_url: dict[str, _BoursoramaCandidate] = {}
        for candidate in candidates:
            existing = deduped_by_url.get(candidate.url)
            if existing is None or candidate.provider_rank < existing.provider_rank:
                deduped_by_url[candidate.url] = candidate
        ranked_candidates = sorted(
            deduped_by_url.values(), key=lambda candidate: candidate.provider_rank
        )
        article_links = [
            ArticleLink(title=candidate.title, url=candidate.url)
            for candidate in ranked_candidates
        ]
        scraping_result = get_article_matching_published_date(
            article_links, reporting_date
        )
        if scraping_result is None:
            return ScrapingResult(
                url=None,
                title=None,
                content=None,
                comment=(
                    f"No Boursorama {region_label} close wrap found for "
                    f"{reporting_date.isoformat()}"
                ),
            )
        return scraping_result
    except Exception as exc:
        logger.error("Boursorama %s scrape failed: %s", region_label, exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_boursorama(
    reporting_date: date,
    region: ArticleRegionChoices | None = None,
) -> list[TaggedScrapingResult]:
    """Scrape Boursorama France / Europe close wraps for 'reporting_date'.

    When 'region' is set, only that region's close wrap is scraped.
    """
    return scrap_tagged_region_closes(
        NewsSourceChoices.BOURSORAMA,
        reporting_date,
        region,
        _scrap_boursorama_region_close,
    )
