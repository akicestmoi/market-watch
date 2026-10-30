"""Tests for NY Fed scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.nyfed import scrap_rate_from_nyfed_xml


class TestNYFedScraping(TestCase):
    """Test cases for scrap_rate_from_nyfed_xml."""

    MOCK_NYFED_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/nyfed/success.xml"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        scrap_rate_from_nyfed_xml.cache_clear()

    @patch("market_overview.services.scrapers.nyfed.requests.get")
    def test_nyfed_success(self, mock_get):
        """
        GIVEN a NY Fed XML with a success response
        WHEN scraping the rate for a specific date
        THEN the rate should be scraped successfully
        """
        target_date = date(2025, 11, 24)
        ticker = "SOFR"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_NYFED_SUCCESS, text="Success"
        )

        result = scrap_rate_from_nyfed_xml(target_date, ticker)

        assert result == ScrapingResult(price=3.96, comment="")

    @patch("market_overview.services.scrapers.nyfed.requests.get")
    def test_nyfed_not_found(self, mock_get):
        """
        GIVEN a NY Fed XML with a success response
        WHEN scraping the rate for a specific date not included in the XML
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "SOFR"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_NYFED_SUCCESS, text="Success"
        )

        result = scrap_rate_from_nyfed_xml(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Rate not found.")

    @patch("market_overview.services.scrapers.nyfed.requests.get")
    def test_nyfed_http_error(self, mock_get):
        """
        GIVEN a NY Fed XML with a HTTP error response
        WHEN scraping the rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "SOFR"

        mock_get.return_value = MockResponse(
            status_code=404, content=self.MOCK_NYFED_SUCCESS, text="Not Found"
        )

        result = scrap_rate_from_nyfed_xml(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Not Found")
