"""Tests for Bundesbank scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from market_overview.services.scrapers.bundesbank import get_bund_yield_from_bundesbank
from market_overview.services.scrapers.common import ScrapingResult


class TestBundesbankScraping(TestCase):
    """Test cases for get_bund_yield_from_bundesbank."""

    MOCK_BUNDESBANK_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/bundesbank/success.xml"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_bund_yield_from_bundesbank.cache_clear()

    @patch("market_overview.services.scrapers.bundesbank.requests.get")
    def test_bundesbank_success(self, mock_get):
        """
        GIVEN a successful Bundesbank XML response with yield data
        WHEN scraping the yield for a specific date
        THEN the yield should be returned successfully
        """
        target_date = date(2020, 5, 27)
        ticker = "D.REN.EUR.A607.000000WT7070.A"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BUNDESBANK_SUCCESS, text="Success"
        )

        result = get_bund_yield_from_bundesbank(target_date, ticker)

        assert result == ScrapingResult(price=-0.56, comment="")

    @patch("market_overview.services.scrapers.bundesbank.requests.get")
    def test_bundesbank_not_found(self, mock_get):
        """
        GIVEN a Bundesbank XML response without data for the target date
        WHEN scraping the yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "D.REN.EUR.A607.000000WT7070.A"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BUNDESBANK_SUCCESS, text="Success"
        )

        result = get_bund_yield_from_bundesbank(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Bunds rate not found.")

    @patch("market_overview.services.scrapers.bundesbank.requests.get")
    def test_bundesbank_http_error(self, mock_get):
        """
        GIVEN a Bundesbank HTTP error response
        WHEN scraping the yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "D.REN.EUR.A607.000000WT7070.A"

        mock_get.return_value = MockResponse(
            status_code=500, content=b"", text="Internal Server Error"
        )

        result = get_bund_yield_from_bundesbank(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Internal Server Error")
