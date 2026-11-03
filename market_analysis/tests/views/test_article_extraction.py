"""Tests for the extract-article API view."""

from datetime import date
from unittest.mock import patch

from django.test import Client, TestCase
from rest_framework.exceptions import NotFound

from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.services.article_extraction import (
    ArticleData,
    ArticleExtractionResult,
    ExtractedArticles,
)


class ExtractArticleViewTests(TestCase):
    """Tests for GET /analysis/article."""

    @patch("market_analysis.views.article_extraction.extract_all_articles")
    def test_extract_article_endpoint_with_source(self, mock_extract):
        """
        GIVEN extract_all_articles returns one scraped wrap for a source filter
        WHEN GET /analysis/article is called with reporting_date and source
        THEN articles are listed once and sources carry status only
        """
        mock_extract.return_value = ExtractedArticles(
            reporting_date=date(2026, 10, 30),
            source=NewsSourceChoices.SWISSINFO_MARKET_WRAP,
            region=None,
            articles=[
                ArticleData(
                    source_key=NewsSourceChoices.SWISSINFO_MARKET_WRAP,
                    source_name="Swissinfo — Bloomberg Markets Wrap",
                    regions=[ArticleRegionChoices.GLOBAL],
                    url="https://www.swissinfo.ch/eng/wrap/1",
                    title="Markets Wrap",
                    content="Stocks fell.",
                )
            ],
            sources=[
                ArticleExtractionResult(
                    source_id=NewsSourceChoices.SWISSINFO_MARKET_WRAP,
                    name="Swissinfo — Bloomberg Markets Wrap",
                    base_url="https://www.swissinfo.ch",
                    regions=[ArticleRegionChoices.GLOBAL],
                    articles=[
                        ArticleData(
                            source_key=NewsSourceChoices.SWISSINFO_MARKET_WRAP,
                            source_name="Swissinfo — Bloomberg Markets Wrap",
                            regions=[ArticleRegionChoices.GLOBAL],
                            url="https://www.swissinfo.ch/eng/wrap/1",
                            title="Markets Wrap",
                            content="Stocks fell.",
                        )
                    ],
                    comment=None,
                )
            ],
        )
        response = Client().get(
            "/analysis/article",
            {
                "reporting_date": "2026-10-30",
                "source": NewsSourceChoices.SWISSINFO_MARKET_WRAP.value,
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "reporting_date": "2026-10-30",
            "source": "SWISSINFO_MARKET_WRAP",
            "region": None,
            "articles": [
                {
                    "source_key": "SWISSINFO_MARKET_WRAP",
                    "source_name": "Swissinfo — Bloomberg Markets Wrap",
                    "regions": ["GLOBAL"],
                    "url": "https://www.swissinfo.ch/eng/wrap/1",
                    "title": "Markets Wrap",
                    "content": "Stocks fell.",
                }
            ],
            "sources": [
                {
                    "source_id": "SWISSINFO_MARKET_WRAP",
                    "name": "Swissinfo — Bloomberg Markets Wrap",
                    "base_url": "https://www.swissinfo.ch",
                    "regions": ["GLOBAL"],
                    "comment": None,
                }
            ],
        }
        mock_extract.assert_called_once_with(
            reporting_date=date(2026, 10, 30),
            source=NewsSourceChoices.SWISSINFO_MARKET_WRAP,
            region=None,
        )

    @patch("market_analysis.views.article_extraction.extract_all_articles")
    def test_extract_article_endpoint_region_only(self, mock_extract):
        """
        GIVEN extract_all_articles returns US wraps across sources
        WHEN GET /analysis/article is called with region only
        THEN the response includes that region filter without nested articles
        """
        mock_extract.return_value = ExtractedArticles(
            reporting_date=date(2026, 10, 30),
            source=None,
            region=ArticleRegionChoices.US,
            articles=[
                ArticleData(
                    source_key=NewsSourceChoices.CNBC_STOCK_MARKET_DAILY_RECAP,
                    source_name="CNBC — Stock Market Daily Recap",
                    regions=[ArticleRegionChoices.US],
                    url="https://www.cnbc.com/wrap",
                    title="US close",
                    content="Nasdaq fell.",
                )
            ],
            sources=[
                ArticleExtractionResult(
                    source_id=NewsSourceChoices.CNBC_STOCK_MARKET_DAILY_RECAP,
                    name="CNBC — Stock Market Daily Recap",
                    base_url="https://www.cnbc.com",
                    regions=[ArticleRegionChoices.US],
                    articles=[
                        ArticleData(
                            source_key=NewsSourceChoices.CNBC_STOCK_MARKET_DAILY_RECAP,
                            source_name="CNBC — Stock Market Daily Recap",
                            regions=[ArticleRegionChoices.US],
                            url="https://www.cnbc.com/wrap",
                            title="US close",
                            content="Nasdaq fell.",
                        )
                    ],
                    comment=None,
                )
            ],
        )
        response = Client().get(
            "/analysis/article",
            {
                "reporting_date": "2026-10-30",
                "region": ArticleRegionChoices.US.value,
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "reporting_date": "2026-10-30",
            "source": None,
            "region": "US",
            "articles": [
                {
                    "source_key": "CNBC_STOCK_MARKET_DAILY_RECAP",
                    "source_name": "CNBC — Stock Market Daily Recap",
                    "regions": ["US"],
                    "url": "https://www.cnbc.com/wrap",
                    "title": "US close",
                    "content": "Nasdaq fell.",
                }
            ],
            "sources": [
                {
                    "source_id": "CNBC_STOCK_MARKET_DAILY_RECAP",
                    "name": "CNBC — Stock Market Daily Recap",
                    "base_url": "https://www.cnbc.com",
                    "regions": ["US"],
                    "comment": None,
                }
            ],
        }
        mock_extract.assert_called_once_with(
            reporting_date=date(2026, 10, 30),
            source=None,
            region=ArticleRegionChoices.US,
        )

    @patch("market_analysis.views.article_extraction.extract_all_articles")
    def test_extract_article_endpoint_date_only(self, mock_extract):
        """
        GIVEN extract_all_articles returns an empty multi-source run
        WHEN GET /analysis/article is called with reporting_date only
        THEN extract_all_articles is called with no source/region filters
        """
        mock_extract.return_value = ExtractedArticles(
            reporting_date=date(2026, 10, 30),
            source=None,
            region=None,
            articles=[],
            sources=[],
        )
        response = Client().get(
            "/analysis/article",
            {"reporting_date": "2026-10-30"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "reporting_date": "2026-10-30",
            "source": None,
            "region": None,
            "articles": [],
            "sources": [],
        }
        mock_extract.assert_called_once_with(
            reporting_date=date(2026, 10, 30),
            source=None,
            region=None,
        )

    @patch("market_analysis.views.article_extraction.extract_all_articles")
    def test_extract_article_endpoint_not_found(self, mock_extract):
        """
        GIVEN extract_all_articles raises NotFound for an unconfigured source
        WHEN GET /analysis/article is called
        THEN a 404 response is returned
        """
        mock_extract.side_effect = NotFound(
            detail="News source 'SWISSINFO_MARKET_WRAP' is not configured."
        )
        response = Client().get(
            "/analysis/article",
            {
                "reporting_date": "2026-10-30",
                "source": NewsSourceChoices.SWISSINFO_MARKET_WRAP.value,
            },
        )
        assert response.status_code == 404
