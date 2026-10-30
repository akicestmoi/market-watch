"""Tests for analysis_cache_views."""

from unittest.mock import patch

from django.test import Client, TestCase

from market_analysis.llm.config import PROMPT_VERSION


class GetArticleAnalysisCacheViewTests(TestCase):
    """Tests for the article analysis cache GET API."""

    @patch("market_analysis.views.analysis_cache.list_cached_analyses")
    def test_get_article_cache_endpoint(self, mock_list):
        """
        GIVEN list_cached_analyses returns an empty cache payload
        WHEN GET /analysis/article-cache is called with a reporting_date
        THEN a 200 response with that reporting_date is returned
        """
        mock_list.return_value = {
            "reporting_date": "2025-12-12",
            "prompt_version": PROMPT_VERSION,
            "ttl_seconds": 86400,
            "count": 0,
            "items": [],
        }
        response = Client().get(
            "/analysis/article-cache", {"reporting_date": "2025-12-12"}
        )
        assert response.status_code == 200
        assert response.json()["reporting_date"] == "2025-12-12"
        mock_list.assert_called_once()
