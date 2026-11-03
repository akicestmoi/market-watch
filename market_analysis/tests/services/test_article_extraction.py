"""Tests for article_extraction orchestration."""

from datetime import date
from unittest.mock import Mock, patch

from rest_framework.exceptions import NotFound, ValidationError

from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.article_extraction import (
    SOURCE_SCRAP_MAP,
    ArticleData,
    ArticleExtractionResult,
    ExtractedArticles,
    _extract_article,
    _NewsSourceEntry,
    extract_all_articles,
    extract_articles_for_source,
)
from market_analysis.services.scrapers.common import (
    ScrapingResult,
    TaggedScrapingResult,
)

REPORTING_DATE = date(2026, 10, 23)


def _build_news_source() -> _NewsSourceEntry:
    """Return a Boursier news source entry for tests."""
    return _NewsSourceEntry(
        source=NewsSourceChoices.BOURSIER_CLOTURE_PARIS,
        name="Boursier",
        base_url="https://www.boursier.com",
        regions=[ArticleRegionChoices.FR],
    )


@patch.dict(SOURCE_SCRAP_MAP, clear=True)
def test_extract_article_without_scrap_function():
    """
    GIVEN a news source with no registered scrap function
    WHEN _extract_article is called
    THEN no articles are returned and the comment lists the known sources
    """
    news_source = _build_news_source()
    extraction_result = _extract_article(news_source, REPORTING_DATE)

    assert extraction_result == ArticleExtractionResult(
        source_id=NewsSourceChoices.BOURSIER_CLOTURE_PARIS,
        name="Boursier",
        base_url="https://www.boursier.com",
        regions=[ArticleRegionChoices.FR],
        articles=[],
        comment=(
            "No scraping function for source "
            f"{NewsSourceChoices.BOURSIER_CLOTURE_PARIS.value!r}. "
            "Known: []"
        ),
    )


@patch.dict(SOURCE_SCRAP_MAP)
def test_extract_article_from_scrap_function():
    """
    GIVEN a scrap function returning an article for the reporting date
    WHEN _extract_article is called
    THEN the article carries the catalog regions and scraped payload
    """
    scrap_function = Mock()
    scrap_function.return_value = ScrapingResult(
        url="https://www.boursier.com/article-1.html",
        title="Clôture Paris",
        content="CAC 40 en baisse.",
        comment=None,
    )
    SOURCE_SCRAP_MAP[NewsSourceChoices.BOURSIER_CLOTURE_PARIS] = scrap_function

    extraction_result = _extract_article(_build_news_source(), REPORTING_DATE)

    scrap_function.assert_called_once_with(REPORTING_DATE)
    assert extraction_result == ArticleExtractionResult(
        source_id=NewsSourceChoices.BOURSIER_CLOTURE_PARIS,
        name="Boursier",
        base_url="https://www.boursier.com",
        regions=[ArticleRegionChoices.FR],
        articles=[
            ArticleData(
                source_key=NewsSourceChoices.BOURSIER_CLOTURE_PARIS,
                source_name="Boursier",
                regions=[ArticleRegionChoices.FR],
                url="https://www.boursier.com/article-1.html",
                title="Clôture Paris",
                content="CAC 40 en baisse.",
            )
        ],
        comment=None,
    )


@patch.dict(SOURCE_SCRAP_MAP)
def test_extract_article_filters_multi_region_by_region():
    """
    GIVEN a multi-region scrap function and region=FR
    WHEN _extract_article is called
    THEN only the FR wrap is scraped and returned
    """
    scrap_function = Mock()
    scrap_function.return_value = [
        TaggedScrapingResult(
            regions=[ArticleRegionChoices.FR],
            url="https://www.boursorama.com/fr",
            title="Paris clôture",
            content="CAC.",
            comment=None,
        )
    ]
    SOURCE_SCRAP_MAP[NewsSourceChoices.BOURSORAMA] = scrap_function
    news_source = _NewsSourceEntry(
        source=NewsSourceChoices.BOURSORAMA,
        name="Boursorama",
        base_url="https://www.boursorama.com",
        regions=[
            ArticleRegionChoices.EU,
            ArticleRegionChoices.FR,
        ],
    )

    extraction_result = _extract_article(
        news_source, REPORTING_DATE, region=ArticleRegionChoices.FR
    )

    scrap_function.assert_called_once_with(
        REPORTING_DATE, region=ArticleRegionChoices.FR
    )
    assert extraction_result == ArticleExtractionResult(
        source_id=NewsSourceChoices.BOURSORAMA,
        name="Boursorama",
        base_url="https://www.boursorama.com",
        regions=[
            ArticleRegionChoices.EU,
            ArticleRegionChoices.FR,
        ],
        articles=[
            ArticleData(
                source_key=NewsSourceChoices.BOURSORAMA,
                source_name="Boursorama",
                regions=[ArticleRegionChoices.FR],
                url="https://www.boursorama.com/fr",
                title="Paris clôture",
                content="CAC.",
            )
        ],
        comment=None,
    )


def test_extract_article_rejects_region_not_in_catalog():
    """
    GIVEN a source whose catalog regions do not include US
    WHEN _extract_article is called with region=US
    THEN ValidationError is raised
    """
    try:
        _extract_article(
            _build_news_source(), REPORTING_DATE, region=ArticleRegionChoices.US
        )
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "not available" in str(exc.detail)


@patch(
    "market_analysis.services.article_extraction._get_news_source_entry",
    return_value=None,
)
def test_extract_articles_for_source_not_configured(mock_get_entry):
    """
    GIVEN a NewsSourceChoices value absent from the catalog
    WHEN extract_articles_for_source is called
    THEN NotFound is raised
    """
    try:
        extract_articles_for_source(
            REPORTING_DATE, NewsSourceChoices.SWISSINFO_MARKET_WRAP
        )
        raise AssertionError("expected NotFound")
    except NotFound as exc:
        assert "not configured" in str(exc.detail)
    mock_get_entry.assert_called_once()


@patch(
    "market_analysis.services.article_extraction._load_news_source_entries",
)
@patch.dict(SOURCE_SCRAP_MAP)
def test_extract_all_articles_region_only_skips_sources_without_region(
    mock_load_entries,
):
    """
    GIVEN catalog sources where only one lists US
    WHEN extract_all_articles is called with region=US and no source
    THEN only the US-capable source is scraped
    """
    us_source = _NewsSourceEntry(
        source=NewsSourceChoices.NEWSQUAWK_US_MARKET_WRAP,
        name="Newsquawk",
        base_url="https://www.newsquawk.com",
        regions=[ArticleRegionChoices.US],
    )
    fr_source = _build_news_source()
    mock_load_entries.return_value = [us_source, fr_source]
    scrap_function = Mock()
    scrap_function.return_value = ScrapingResult(
        url="https://www.newsquawk.com/wrap",
        title="US wrap",
        content="Stocks fell.",
        comment=None,
    )
    SOURCE_SCRAP_MAP[NewsSourceChoices.NEWSQUAWK_US_MARKET_WRAP] = scrap_function

    extracted_articles = extract_all_articles(
        REPORTING_DATE, region=ArticleRegionChoices.US
    )

    scrap_function.assert_called_once_with(REPORTING_DATE)
    assert extracted_articles == ExtractedArticles(
        reporting_date=REPORTING_DATE,
        source=None,
        region=ArticleRegionChoices.US,
        articles=[
            ArticleData(
                source_key=NewsSourceChoices.NEWSQUAWK_US_MARKET_WRAP,
                source_name="Newsquawk",
                regions=[ArticleRegionChoices.US],
                url="https://www.newsquawk.com/wrap",
                title="US wrap",
                content="Stocks fell.",
            )
        ],
        sources=[
            ArticleExtractionResult(
                source_id=NewsSourceChoices.NEWSQUAWK_US_MARKET_WRAP,
                name="Newsquawk",
                base_url="https://www.newsquawk.com",
                regions=[ArticleRegionChoices.US],
                articles=[
                    ArticleData(
                        source_key=NewsSourceChoices.NEWSQUAWK_US_MARKET_WRAP,
                        source_name="Newsquawk",
                        regions=[ArticleRegionChoices.US],
                        url="https://www.newsquawk.com/wrap",
                        title="US wrap",
                        content="Stocks fell.",
                    )
                ],
                comment=None,
            )
        ],
    )
