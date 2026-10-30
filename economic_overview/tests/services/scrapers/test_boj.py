"""Tests for the Bank of Japan Tankan scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.scrapers.boj import (
    _parse_boj_tankan_zip,
    get_data_from_boj,
)
from economic_overview.services.scrapers.common import ScrapingResult


class TestBojTankanDataIngestion(TestCase):
    """Tests for BoJ Tankan summary ZIP scraping."""

    MOCK_TANKAN_ZIP = read_file_content(
        "economic_overview/tests/mock_web_data/boj/data/tka2609.zip"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_boj.cache_clear()

    def test_parse_boj_tankan_zip_all_series(self):
        """
        GIVEN a Tankan summary ZIP fixture with Manufacturing and Nonmanufacturing
        WHEN parsing each supported size × sector ticker
        THEN the matching current-survey actual DI is returned for September 2026
        """
        expected_by_ticker = {
            "business_conditions_large_mfg": 24.0,
            "business_conditions_medium_mfg": 23.0,
            "business_conditions_small_mfg": 14.0,
            "business_conditions_large_nonmfg": 35.0,
            "business_conditions_medium_nonmfg": 24.0,
            "business_conditions_small_nonmfg": 15.0,
        }
        for ticker, expected_value in expected_by_ticker.items():
            result = _parse_boj_tankan_zip(self.MOCK_TANKAN_ZIP, "tka2609.zip", ticker)
            assert result == [
                ScrapingResult(
                    period=date(2026, 9, 1),
                    data_value=expected_value,
                    comment="",
                )
            ], ticker

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_success(self, mock_get):
        """
        GIVEN the BoJ Tankan index page and summary ZIP
        WHEN getting the medium nonmanufacturing business-conditions DI
        THEN the latest survey observation is returned
        """
        index_html = '<a href="/en/statistics/tk/gaiyo/2026/tka2609.zip">[ZIP 97KB]</a>'
        mock_get.side_effect = [
            MockResponse(status_code=200, content=index_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_TANKAN_ZIP, text=""),
        ]

        result = get_data_from_boj(
            "business_conditions_medium_nonmfg",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=24.0, comment="")
        ]

    def test_get_data_from_boj_unknown_ticker(self):
        """
        GIVEN a ticker not in BOJ_TANKAN_SERIES_BY_TICKER
        WHEN getting BoJ Tankan data
        THEN an unsupported-ticker ScrapingResult is returned
        """
        result = get_data_from_boj("business_conditions_all_industries")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported BOJ ticker: business_conditions_all_industries",
            )
        ]
