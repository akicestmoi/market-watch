"""Tests for the World Inequality Database wealth scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    WID_TOP10_WEALTH_SHARE_TICKER,
    WID_WEALTH_GINI_TICKER,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.wid import get_data_from_wid


class TestWidDataIngestion(TestCase):
    """Tests for WID net personal wealth Gini and top-10 share scraping."""

    MOCK_WID_US_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/wid/data/us_wealth_success.csv"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_wid.cache_clear()

    @patch("economic_overview.services.scrapers.wid.requests.get")
    def test_get_data_from_wid_wealth_gini(self, mock_get):
        """
        GIVEN a successful WID US bulk CSV
        WHEN getting wealth Gini
        THEN annual points are returned newest-first on a 0–100 scale
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_WID_US_CSV.encode(),
            text=self.MOCK_WID_US_CSV,
        )

        result = get_data_from_wid(
            WID_WEALTH_GINI_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="US",
        )
        assert result == [
            ScrapingResult(period=date(2023, 1, 1), data_value=85.5, comment=""),
            ScrapingResult(period=date(2022, 1, 1), data_value=85.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.wid.requests.get")
    def test_get_data_from_wid_top10_wealth_share(self, mock_get):
        """
        GIVEN a successful WID US bulk CSV
        WHEN getting top-10 wealth share
        THEN annual percent points are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_WID_US_CSV.encode(),
            text=self.MOCK_WID_US_CSV,
        )

        result = get_data_from_wid(
            WID_TOP10_WEALTH_SHARE_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="US",
        )
        assert result == [
            ScrapingResult(period=date(2023, 1, 1), data_value=71.0, comment=""),
            ScrapingResult(period=date(2022, 1, 1), data_value=70.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.wid.requests.get")
    def test_get_data_from_wid_unsupported_ticker(self, mock_get):
        """
        GIVEN an unknown WID ticker
        WHEN getting data
        THEN an unsupported-ticker error result is returned
        """
        result = get_data_from_wid("not_a_series")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported WID ticker: not_a_series",
            )
        ]
        mock_get.assert_not_called()
