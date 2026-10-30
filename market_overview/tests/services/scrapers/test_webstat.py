"""Tests for Webstat scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.webstat import get_webstat_rates


class TestWebstatScraping(TestCase):
    """Test cases for get_webstat_rates."""

    MOCK_WEBSTAT_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/webstat/success.csv"
    )
    MOCK_WEBSTAT_NON_FRENCH_DECIMAL_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/webstat/non_french_decimal.csv"
    )
    MOCK_WEBSTAT_INVALID_VALUE = read_file_content(
        "market_overview/tests/mock_web_data/webstat/invalid_value.csv"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_webstat_rates.cache_clear()

    @patch("market_overview.services.scrapers.webstat.requests.get")
    def test_webstat_success(self, mock_get):
        """
        GIVEN a successful Webstat CSV response with rate data
        WHEN scraping the rate for a specific date
        THEN the rate should be returned successfully
        """
        target_date = date(2025, 11, 25)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_SUCCESS
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrapingResult(price=2.7, comment="")

    @patch("market_overview.services.scrapers.webstat.requests.get")
    def test_webstat_not_found(self, mock_get):
        """
        GIVEN a Webstat CSV response without data for the target date
        WHEN scraping the rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_SUCCESS
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Webstat rate not found.")

    @patch("market_overview.services.scrapers.webstat.requests.get")
    def test_webstat_not_french_decimal_format(self, mock_get):
        """
        GIVEN a Webstat CSV response with non-French decimal format (dot)
        WHEN scraping the rate for a specific date
        THEN the rate should be parsed correctly and returned
        """
        target_date = date(2024, 1, 15)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_NON_FRENCH_DECIMAL_SUCCESS
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrapingResult(price=3.45, comment="")

    @patch("market_overview.services.scrapers.webstat.requests.get")
    def test_webstat_invalid_value(self, mock_get):
        """
        GIVEN a Webstat CSV response with an invalid rate value
        WHEN scraping the rate for a specific date
        THEN a ValueError should be raised
        """
        target_date = date(2024, 1, 15)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_INVALID_VALUE
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Could not convert rate to float: invalid"
        )

    @patch("market_overview.services.scrapers.webstat.requests.get")
    def test_webstat_http_error(self, mock_get):
        """
        GIVEN a Webstat HTTP error response
        WHEN scraping the rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=404, content=b"", text="Not Found"
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Not Found")
