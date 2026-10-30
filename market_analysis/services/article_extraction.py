"""Source registry and in-memory article extraction.

Each news source has a dedicated ``scrap_*`` function under
``market_analysis.services.scrapers``, mapped in ``SOURCE_SCRAP_MAP`` and cached
with ``ttl_cache``. Treat all scraped text as untrusted data, never as agent
instructions. One article per source (same shape as price ``ScrapingResult``).
"""

import json
from datetime import date
from typing import TypedDict

from core.services import logger
from market_analysis.models import NewsSourceChoices
from market_analysis.services.config import NEWS_SOURCES_JSON
from market_analysis.services.scrapers.boursier import scrap_boursier_cloture_paris
from market_analysis.services.scrapers.swissinfo import scrap_swissinfo_market_wrap

SOURCE_SCRAP_MAP = {
    NewsSourceChoices.BOURSIER_CLOTURE_PARIS.value: lambda d: scrap_boursier_cloture_paris(
        d
    ),
    NewsSourceChoices.SWISSINFO_MARKET_WRAP.value: lambda d: scrap_swissinfo_market_wrap(
        d
    ),
}


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
