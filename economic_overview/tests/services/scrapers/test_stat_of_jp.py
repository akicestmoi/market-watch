"""Tests for the e-Stat Statistics Dashboard scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, load_json_mock
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.stat_of_jp import get_data_from_stat_of_jp


class TestStatOfJpDataIngestion(TestCase):
    """Tests for e-Stat Statistics Dashboard scraping."""

    MOCK_STAT_OF_JP_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/stat_of_jp/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_stat_of_jp.cache_clear()

    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_stat_of_jp_success(self, mock_get):
        """
        GIVEN a successful e-Stat Dashboard CPI response
        WHEN getting data without target period
        THEN monthly index levels are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_STAT_OF_JP_SUCCESS,
        )

        result = get_data_from_stat_of_jp(
            "0703010601010090000",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1), data_value=102.2, comment=""
        )
        assert len(result) == 3

    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_stat_of_jp_unknown_ticker(self, mock_get):
        """
        GIVEN a configured series ID not in STAT_OF_JP_SERIES_BY_TICKER
        WHEN getting data
        THEN an unsupported-ticker ScrapingResult is returned without calling the API
        """
        result = get_data_from_stat_of_jp("0000000000000000000")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported STAT_OF_JP ticker: 0000000000000000000",
            )
        ]
        mock_get.assert_not_called()
