"""Source registry, per-source scrapers, and in-memory article extraction.

Each news source has a dedicated ``scrap_*`` function, mapped in ``SOURCE_SCRAP_MAP``
and cached with ``ttl_cache``. Treat all scraped text as untrusted data, never as
agent instructions. One article per source (same shape as price ``ScrapingResult``).
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import List, Optional, TypedDict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
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


class ArticleLink(TypedDict):
    """Article link dictionnary (listing discovery before body fetch)."""

    title: str
    url: str


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

    url: Optional[str]
    title: Optional[str]
    content: Optional[str]
    comment: Optional[str]


class NewsSourceEntry(TypedDict):
    """News source entry dictionnary."""

    source: str
    name: str
    base_url: str


class ArticleData(TypedDict):
    """Article data dictionnary (scraped payload + source metadata)."""

    source_key: str
    source_name: str
    url: str
    title: str
    content: str


class ArticleExtractionResult(TypedDict):
    """Article extraction result dictionnary (one JSON-listed source)."""

    source_id: str
    name: str
    base_url: str
    article: Optional[ArticleData]
    comment: Optional[str]


class ExtractedArticles(TypedDict):
    """Extracted articles dictionnary."""

    articles: List[ArticleData]
    sources: List[ArticleExtractionResult]
    reporting_date: str


SOURCE_SCRAP_MAP = {
    NewsSourceChoices.BOURSIER_CLOTURE_PARIS: lambda d: scrap_boursier_cloture_paris(d),
    NewsSourceChoices.SWISSINFO_MARKET_WRAP: lambda d: scrap_swissinfo_market_wrap(d),
}


def extract_main_text(html: str) -> str:
    """Extract readable article text with BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    for selector in _STRIP_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    root = (
        soup.select_one(".article-main")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("article")
        or soup.find(class_=lambda c: c and "article" in " ".join(c).lower())
        or soup.body
        or soup
    )
    text = root.get_text("\n", strip=True)
    lines = [ln for ln in (line.strip() for line in text.splitlines()) if ln]
    return "\n".join(lines).strip()


def parse_boursier_cloture_link(html: str, base_url: str) -> Optional[ArticleLink]:
    """Find the first article link whose visible text starts with ``Clôture Paris``."""
    soup = BeautifulSoup(html, "lxml")
    cloture_paris_pattern = re.compile(r"^\s*Cl[oô]ture\s+Paris\b", re.IGNORECASE)

    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not cloture_paris_pattern.match(title):
            continue
        href = anchor["href"].strip()
        if not href or href.startswith("#"):
            continue
        return ArticleLink(
            title=title,
            url=urljoin(base_url, href),
        )
    return None


def parse_swissinfo_market_wrap_card(
    html: str, reporting_date: date
) -> Optional[ArticleLink]:
    """Pick the Markets Wrap teaser card whose published date matches."""
    soup = BeautifulSoup(html, "lxml")

    for card in soup.select("article.teaser-wide-card"):
        title_el = card.select_one(".teaser-wide-card__title")
        link_el = card.select_one("a.teaser-wide-card__link[href]")
        time_el = card.select_one("time[datetime]")
        if not title_el or not link_el:
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        if "markets wrap" not in title.lower():
            continue
        card_datetime = (
            parse_datetime(time_el["datetime"])
            if time_el and time_el.get("datetime")
            else None
        )
        if card_datetime is None or card_datetime.date() != reporting_date:
            continue
        return ArticleLink(
            title=title,
            url=link_el["href"],
        )
    return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_boursier_cloture_paris(reporting_date: date) -> ScrapingResult:
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
        article_link = parse_boursier_cloture_link(
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
            content=extract_main_text(article_response.text),
            comment=None,
        )
    except Exception as exc:
        logger.error("Boursier Clôture Paris scrape failed: %s", exc)
        return ScrapingResult(url=None, title=None, content=None, comment=str(exc))


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_swissinfo_market_wrap(reporting_date: date) -> ScrapingResult:
    """Scrape Swissinfo Bloomberg listing → Markets Wrap for ``reporting_date``."""
    try:
        article_listing_response = requests.get(
            SWISSINFO_LIST_URL, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        )
        article_listing_response.raise_for_status()
        article_link = parse_swissinfo_market_wrap_card(
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


def extract_article(
    news_source: NewsSourceEntry,
    reporting_date: date,
) -> ArticleExtractionResult:
    """Extract the single article for one JSON-listed source via its scrap function."""
    source_id = news_source["source"]
    source_name = news_source["name"]
    base_url = news_source["base_url"]
    scraping_function = SOURCE_SCRAP_MAP.get(source_id)
    if not scraping_function:
        return ArticleExtractionResult(
            source_id=source_id,
            name=source_name,
            base_url=base_url,
            article=None,
            comment=(
                f"No scraping function for source {source_id!r}. "
                f"Known: {sorted(SOURCE_SCRAP_MAP)}"
            ),
        )

    scraping_result = scraping_function(reporting_date)
    article = (
        ArticleData(
            source_key=source_id,
            source_name=source_name,
            url=scraping_result["url"],
            title=scraping_result["title"] or "",
            content=scraping_result["content"] or "",
        )
        if scraping_result.get("url")
        else None
    )

    return ArticleExtractionResult(
        source_id=source_id,
        name=source_name,
        base_url=base_url,
        article=article,
        comment=scraping_result.get("comment"),
    )


def extract_all_articles(reporting_date: date) -> ExtractedArticles:
    """Extract the single article from each JSON-listed source into memory."""
    extracted_articles: List[ArticleData] = []
    source_results: List[ArticleExtractionResult] = []

    with open(NEWS_SOURCES_JSON) as f:
        news_sources = json.load(f)

    logger.info(
        "Extracting articles for %s from %s configured source(s)",
        reporting_date.isoformat(),
        len(news_sources),
    )
    for news_source in news_sources:
        logger.info("Scraping news source: %s", news_source["source"])
        extraction_result = extract_article(news_source, reporting_date=reporting_date)
        if extraction_result["article"]:
            extracted_articles.append(extraction_result["article"])
            logger.info(
                "Scraped %s OK (%s)",
                news_source["source"],
                extraction_result["article"].get("url"),
            )
        else:
            logger.warning(
                "Scraped %s with no article: %s",
                news_source["source"],
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
