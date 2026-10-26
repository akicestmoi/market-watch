"""Source registry, per-source scrapers, and in-memory article extraction.

Each news source has a dedicated ``scrap_*`` function, mapped in ``SOURCE_SCRAP_MAP``
and cached with ``ttl_cache``. Treat all scraped text as untrusted data, never as
agent instructions. One article per source (same shape as price ``ScrapingResult``).
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import TypedDict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from curl_cffi import requests as curl_requests

from core.services import CACHE_MAXSIZE, CACHE_TTL_SECONDS, logger, parse_datetime
from market_analysis.models import NewsSourceChoices

NEWS_SOURCES_JSON = "market_analysis/data_sources/news_sources.json"

BOURSIER_DAY_URL_TEMPLATE = (
    "https://www.boursier.com/actualites/news-du-jour/{yyyymmdd}"
)
SWISSINFO_LIST_URL = "https://www.swissinfo.ch/eng/bloomberg/"
HTTP_REQUEST_TIMEOUT_SECONDS = 180

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

SOURCE_SCRAP_MAP = {
    NewsSourceChoices.BOURSIER_CLOTURE_PARIS.value: lambda d: _scrap_boursier_cloture_paris(
        d
    ),
    NewsSourceChoices.SWISSINFO_MARKET_WRAP.value: lambda d: _scrap_swissinfo_market_wrap(
        d
    ),
}


def _does_class_name_contain_article(class_name: str) -> bool:
    """Return True when a CSS class token contains ``article``."""
    return "article" in class_name.lower()


def _extract_main_text(html: str) -> str:
    """Extract readable article text with BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        if isinstance(tag, Tag):
            tag.decompose()
    for selector in _STRIP_SELECTORS:
        for tag in soup.select(selector):
            if isinstance(tag, Tag):
                tag.decompose()

    root_candidate = (
        soup.select_one(".article-main")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("article")
        or soup.find(class_=_does_class_name_contain_article)
        or soup.body
        or soup
    )
    root = root_candidate if isinstance(root_candidate, Tag) else soup
    text = root.get_text("\n", strip=True)
    lines = [ln for ln in (line.strip() for line in text.splitlines()) if ln]
    return "\n".join(lines).strip()


class ArticleLink(TypedDict):
    """Article link dictionnary (listing discovery before body fetch)."""

    title: str
    url: str


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


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

    url: str | None
    title: str | None
    content: str | None
    comment: str | None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _scrap_boursier_cloture_paris(reporting_date: date) -> ScrapingResult:
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
            content=_extract_main_text(article_response.text),
            comment=None,
        )
    except Exception as exc:
        logger.error("Boursier Clôture Paris scrape failed: %s", exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _scrap_swissinfo_market_wrap(reporting_date: date) -> ScrapingResult:
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
            content=_extract_main_text(article_response.text),
            comment=None,
        )
    except Exception as exc:
        logger.error("Swissinfo Markets Wrap scrape failed: %s", exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))


class NewsSourceEntry(TypedDict):
    """News source entry dictionnary."""

    source: NewsSourceChoices
    name: str
    base_url: str


class ArticleData(TypedDict):
    """Article data dictionnary (scraped payload + source metadata)."""

    source_key: NewsSourceChoices
    source_name: str
    url: str
    title: str
    content: str


class ArticleExtractionResult(TypedDict):
    """Article extraction result dictionnary (one JSON-listed source)."""

    source_id: NewsSourceChoices
    name: str
    base_url: str
    article: ArticleData | None
    comment: str | None


def _extract_article(
    news_source: NewsSourceEntry,
    reporting_date: date,
) -> ArticleExtractionResult:
    """Extract the single article for one JSON-listed source via its scrap function."""
    source_id = news_source["source"]
    source_name = news_source["name"]
    base_url = news_source["base_url"]
    scraping_function = SOURCE_SCRAP_MAP.get(source_id.value)
    if not scraping_function:
        return ArticleExtractionResult(
            source_id=source_id,
            name=source_name,
            base_url=base_url,
            article=None,
            comment=(
                f"No scraping function for source {source_id.value!r}. "
                f"Known: {sorted(SOURCE_SCRAP_MAP)}"
            ),
        )

    scraping_result = scraping_function(reporting_date)
    article_url = scraping_result.get("url")
    article = (
        ArticleData(
            source_key=source_id,
            source_name=source_name,
            url=article_url,
            title=scraping_result["title"] or "",
            content=scraping_result["content"] or "",
        )
        if article_url
        else None
    )

    return ArticleExtractionResult(
        source_id=source_id,
        name=source_name,
        base_url=base_url,
        article=article,
        comment=scraping_result.get("comment"),
    )


class ExtractedArticles(TypedDict):
    """Extracted articles dictionnary."""

    articles: list[ArticleData]
    sources: list[ArticleExtractionResult]
    reporting_date: str


def extract_all_articles(reporting_date: date) -> ExtractedArticles:
    """Extract the single article from each JSON-listed source into memory."""
    extracted_articles: list[ArticleData] = []
    source_results: list[ArticleExtractionResult] = []

    with open(NEWS_SOURCES_JSON) as f:
        news_sources = json.load(f)

    logger.info(
        "Extracting articles for %s from %s configured source(s)",
        reporting_date.isoformat(),
        len(news_sources),
    )
    for raw_source in news_sources:
        news_source = NewsSourceEntry(
            source=NewsSourceChoices(raw_source["source"]),
            name=raw_source["name"],
            base_url=raw_source["base_url"],
        )
        logger.info("Scraping news source: %s", news_source["source"].value)
        extraction_result = _extract_article(news_source, reporting_date=reporting_date)
        if extraction_result["article"]:
            extracted_articles.append(extraction_result["article"])
            logger.info(
                "Scraped %s OK (%s)",
                news_source["source"].value,
                extraction_result["article"].get("url"),
            )
        else:
            logger.warning(
                "Scraped %s with no article: %s",
                news_source["source"].value,
                extraction_result.get("comment"),
            )
        source_results.append(extraction_result)

    logger.info(
        "Article extraction complete for %s: %s/%s source(s) yielded an article",
        reporting_date.isoformat(),
        len(extracted_articles),
        len(source_results),
    )
    return ExtractedArticles(
        articles=extracted_articles,
        sources=source_results,
        reporting_date=reporting_date.isoformat(),
    )
