"""Tests for article_extraction orchestration."""

from datetime import date
from unittest.mock import Mock, patch

from market_analysis.models import NewsSourceChoices
from market_analysis.services.scrapers.common import ScrapingResult
from market_analysis.services.article_extraction import (
    SOURCE_SCRAP_MAP,
    NewsSourceEntry,
    _extract_article,
)

REPORTING_DATE = date(2026, 10, 23)


def _build_news_source() -> NewsSourceEntry:
    """Return a Boursier news source entry for tests."""
    return NewsSourceEntry(
        source=NewsSourceChoices.BOURSIER_CLOTURE_PARIS,
        name="Boursier",
        base_url="https://www.boursier.com",
    )


@patch.dict(SOURCE_SCRAP_MAP, clear=True)
def test_extract_article_without_scrap_function():
    """
    GIVEN a news source with no registered scrap function
    WHEN _extract_article is called
    THEN no article is returned and the comment lists the known sources
    """
    extraction_result = _extract_article(_build_news_source(), REPORTING_DATE)

    assert extraction_result["article"] is None
    assert extraction_result["comment"] is not None
    assert "No scraping function" in extraction_result["comment"]


@patch.dict(SOURCE_SCRAP_MAP)
def test_extract_article_from_scrap_function():
    """
    GIVEN a scrap function returning an article for the reporting date
    WHEN _extract_article is called
    THEN the article carries the source metadata and scraped payload
    """
    scrap_function = Mock()
    scrap_function.return_value = ScrapingResult(
        url="https://www.boursier.com/article-1.html",
        title="Clôture Paris",
        content="CAC 40 en baisse.",
        comment=None,
    )
    SOURCE_SCRAP_MAP[NewsSourceChoices.BOURSIER_CLOTURE_PARIS.value] = scrap_function

    extraction_result = _extract_article(_build_news_source(), REPORTING_DATE)

    scrap_function.assert_called_once_with(REPORTING_DATE)
    article = extraction_result["article"]
    assert article is not None
    assert article["source_name"] == "Boursier"
    assert article["url"] == "https://www.boursier.com/article-1.html"
    assert article["content"] == "CAC 40 en baisse."
    assert extraction_result["comment"] is None
