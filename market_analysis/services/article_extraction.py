"""Source registry and in-memory article extraction.

Each news source has a dedicated 'scrap_*' function under
'market_analysis.services.scrapers', mapped in 'SOURCE_SCRAP_MAP' and cached
with 'ttl_cache'. Treat all scraped text as untrusted data, never as agent
instructions. A source may yield zero or more region-tagged wraps.
"""

import json
from collections.abc import Callable
from datetime import date
from typing import TypedDict

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import NotFound, ValidationError

from core.services import logger
from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.config import NEWS_SOURCES_JSON
from market_analysis.services.scrapers.boursier import scrap_boursier_cloture_paris
from market_analysis.services.scrapers.boursorama import scrap_boursorama
from market_analysis.services.scrapers.cnbc_stock_market_daily_recap import (
    scrap_cnbc_stock_market_daily_recap,
)
from market_analysis.services.scrapers.common import (
    ScrapingResult,
    TaggedScrapingResult,
    tag_scraping_result,
)
from market_analysis.services.scrapers.newsquawk import scrap_newsquawk_us_market_wrap
from market_analysis.services.scrapers.swissinfo import scrap_swissinfo_market_wrap
from market_analysis.services.scrapers.tbs_bloomberg import (
    scrap_tbs_japan_markets,
    scrap_tbs_us_markets,
)
from market_analysis.services.scrapers.the_edge import scrap_the_edge_global_markets
from market_analysis.services.scrapers.tokyo_closing_bell import (
    scrap_tokyo_closing_bell,
)
from market_analysis.services.scrapers.zonebourse import scrap_zonebourse

# Single-article scrapers return ScrapingResult; multi-wrap scrapers return a
# tagged list. Extraction normalizes both using the catalog 'regions' list.
SOURCE_SCRAP_MAP: dict[
    NewsSourceChoices, Callable[..., ScrapingResult | list[TaggedScrapingResult]]
] = {
    NewsSourceChoices.BOURSIER_CLOTURE_PARIS: scrap_boursier_cloture_paris,
    NewsSourceChoices.SWISSINFO_MARKET_WRAP: scrap_swissinfo_market_wrap,
    NewsSourceChoices.TOKYO_CLOSING_BELL: scrap_tokyo_closing_bell,
    NewsSourceChoices.TBS_JAPAN_MARKETS: scrap_tbs_japan_markets,
    NewsSourceChoices.TBS_US_MARKETS: scrap_tbs_us_markets,
    NewsSourceChoices.BOURSORAMA: scrap_boursorama,
    NewsSourceChoices.ZONEBOURSE: scrap_zonebourse,
    NewsSourceChoices.NEWSQUAWK_US_MARKET_WRAP: scrap_newsquawk_us_market_wrap,
    NewsSourceChoices.THE_EDGE_GLOBAL_MARKETS: scrap_the_edge_global_markets,
    NewsSourceChoices.CNBC_STOCK_MARKET_DAILY_RECAP: (
        scrap_cnbc_stock_market_daily_recap
    ),
}

# Multi-wrap scrapers that accept an optional 'region' keyword to scrape one
# catalog region instead of every region for that source.
_MULTI_REGION_SCRAP_SOURCES: frozenset[NewsSourceChoices] = frozenset(
    {
        NewsSourceChoices.BOURSORAMA,
        NewsSourceChoices.ZONEBOURSE,
    }
)


class _NewsSourceEntry(TypedDict):
    """Catalog entry for one news source used by article extraction."""

    source: NewsSourceChoices
    name: str
    base_url: str
    regions: list[ArticleRegionChoices]


class ArticleData(TypedDict):
    """Scraped article payload plus source metadata for one wrap."""

    source_key: NewsSourceChoices
    source_name: str
    regions: list[ArticleRegionChoices]
    url: str
    title: str
    content: str


class ArticleExtractionResult(TypedDict):
    """Extraction outcome for one JSON-listed news source."""

    source_id: NewsSourceChoices
    name: str
    base_url: str
    regions: list[ArticleRegionChoices]
    articles: list[ArticleData]
    comment: str | None


def _normalize_tagged_scraping_results(
    scraping_output: ScrapingResult | list[TaggedScrapingResult],
    catalog_regions: list[ArticleRegionChoices],
) -> list[TaggedScrapingResult]:
    """Normalize single- or multi-wrap scraper output to tagged results."""
    if isinstance(scraping_output, list):
        return scraping_output
    return [tag_scraping_result(scraping_output, catalog_regions)]


def _extract_article(
    news_source: _NewsSourceEntry,
    reporting_date: date,
    region: ArticleRegionChoices | None = None,
) -> ArticleExtractionResult:
    """Extract zero or more wraps for one JSON-listed source via its scrap function."""
    source_id = news_source["source"]
    source_name = news_source["name"]
    base_url = news_source["base_url"]
    catalog_regions = news_source["regions"]
    if region is not None and region not in catalog_regions:
        raise ValidationError(
            {
                "region": (
                    f"Region {region.value!r} is not available for source "
                    f"{source_id.value!r}. "
                    f"Available: {[item.value for item in catalog_regions]}"
                )
            }
        )
    scraping_function = SOURCE_SCRAP_MAP.get(source_id)
    if not scraping_function:
        return ArticleExtractionResult(
            source_id=source_id,
            name=source_name,
            base_url=base_url,
            regions=catalog_regions,
            articles=[],
            comment=(
                f"No scraping function for source {source_id.value!r}. "
                f"Known: {sorted(choice.value for choice in SOURCE_SCRAP_MAP)}"
            ),
        )

    if source_id in _MULTI_REGION_SCRAP_SOURCES:
        scraping_output = scraping_function(reporting_date, region=region)
    else:
        scraping_output = scraping_function(reporting_date)
    tagged_results = _normalize_tagged_scraping_results(
        scraping_output,
        catalog_regions,
    )
    articles: list[ArticleData] = []
    miss_comments: list[str] = []
    for tagged_result in tagged_results:
        article_regions = list(tagged_result.get("regions") or catalog_regions)
        if region is not None and region not in article_regions:
            continue
        article_url = tagged_result.get("url")
        if article_url:
            articles.append(
                ArticleData(
                    source_key=source_id,
                    source_name=source_name,
                    regions=article_regions,
                    url=article_url,
                    title=tagged_result.get("title") or "",
                    content=tagged_result.get("content") or "",
                )
            )
        elif tagged_result.get("comment"):
            miss_comments.append(str(tagged_result["comment"]))

    return ArticleExtractionResult(
        source_id=source_id,
        name=source_name,
        base_url=base_url,
        regions=catalog_regions,
        articles=articles,
        comment=" | ".join(miss_comments) if miss_comments else None,
    )


class ExtractedArticles(TypedDict):
    """Extracted wraps for a reporting date, with optional source/region filters."""

    reporting_date: date
    source: NewsSourceChoices | None
    region: ArticleRegionChoices | None
    articles: list[ArticleData]
    sources: list[ArticleExtractionResult]


class _NewsSourceJsonEntry(TypedDict):
    """One news-source catalog entry from 'news_sources.json' (string enums)."""

    source: str
    name: str
    base_url: str
    regions: list[str]


_NEWS_SOURCE_JSON_ADAPTER = TypeAdapter(list[_NewsSourceJsonEntry])


def _load_news_source_entries() -> list[_NewsSourceEntry]:
    """Load catalog entries from 'news_sources.json' into typed entries."""
    with open(NEWS_SOURCES_JSON) as f:
        news_sources = json.load(f)
    try:
        news_source_json_entries = _NEWS_SOURCE_JSON_ADAPTER.validate_python(
            news_sources
        )
    except PydanticValidationError as exc:
        raise ValueError(f"Invalid news_sources.json: {exc}") from exc
    return [
        _NewsSourceEntry(
            source=NewsSourceChoices(news_source_json_entry["source"]),
            name=news_source_json_entry["name"],
            base_url=news_source_json_entry["base_url"],
            regions=[
                ArticleRegionChoices(region_value)
                for region_value in news_source_json_entry["regions"]
            ],
        )
        for news_source_json_entry in news_source_json_entries
    ]


def _get_news_source_entry(source: NewsSourceChoices) -> _NewsSourceEntry | None:
    """Return the catalog entry for 'source', or None when unconfigured."""
    for news_source in _load_news_source_entries():
        if news_source["source"] == source:
            return news_source
    return None


def _select_news_sources_for_extraction(
    source: NewsSourceChoices | None,
    region: ArticleRegionChoices | None,
) -> list[_NewsSourceEntry]:
    """List catalog entries to scrape based on optional source/region filters."""
    if source is not None:
        news_source = _get_news_source_entry(source)
        if news_source is None:
            raise NotFound(detail=f"News source {source.value!r} is not configured.")
        return [news_source]
    news_sources = _load_news_source_entries()
    if region is None:
        return news_sources
    return [
        news_source for news_source in news_sources if region in news_source["regions"]
    ]


def extract_all_articles(
    reporting_date: date,
    source: NewsSourceChoices | None = None,
    region: ArticleRegionChoices | None = None,
) -> ExtractedArticles:
    """Extract wraps for 'reporting_date' with optional source/region filters.

    - 'source' + 'region': that source's wraps for the region
    - 'source' only: all regions for that source
    - 'region' only: every catalog source that lists the region
    - neither: every catalog source and region

    Raises 'NotFound' when 'source' is not configured, and 'ValidationError'
    when both filters are set and the region is not in that source's catalog.
    """
    news_sources = _select_news_sources_for_extraction(source=source, region=region)
    logger.info(
        "Extracting articles for %s (source=%s, region=%s, catalog_sources=%s)",
        reporting_date.isoformat(),
        source.value if source is not None else "all",
        region.value if region is not None else "all",
        len(news_sources),
    )
    extracted_articles: list[ArticleData] = []
    source_results: list[ArticleExtractionResult] = []
    for news_source in news_sources:
        logger.info("Scraping news source: %s", news_source["source"].value)
        extraction_result = _extract_article(
            news_source, reporting_date=reporting_date, region=region
        )
        if extraction_result["articles"]:
            extracted_articles.extend(extraction_result["articles"])
            logger.info(
                "Scraped %s OK (%s article(s))",
                news_source["source"].value,
                len(extraction_result["articles"]),
            )
        else:
            logger.warning(
                "Scraped %s with no article: %s",
                news_source["source"].value,
                extraction_result.get("comment"),
            )
        source_results.append(extraction_result)

    logger.info(
        "Article extraction complete for %s: %s article(s) from %s source(s)",
        reporting_date.isoformat(),
        len(extracted_articles),
        len(source_results),
    )
    return ExtractedArticles(
        reporting_date=reporting_date,
        source=source,
        region=region,
        articles=extracted_articles,
        sources=source_results,
    )


def extract_articles_for_source(
    reporting_date: date,
    source: NewsSourceChoices,
    region: ArticleRegionChoices | None = None,
) -> ArticleExtractionResult:
    """Extract wraps for one catalog source on 'reporting_date'.

    Convenience wrapper around 'extract_all_articles' that returns the single
    source result. Raises 'NotFound' when 'source' is not configured.
    """
    extracted_articles = extract_all_articles(
        reporting_date=reporting_date, source=source, region=region
    )
    if not extracted_articles["sources"]:
        raise NotFound(detail=f"News source {source.value!r} is not configured.")
    # 'extract_all_articles' used one source, so 'sources' has that single result.
    return extracted_articles["sources"][0]
