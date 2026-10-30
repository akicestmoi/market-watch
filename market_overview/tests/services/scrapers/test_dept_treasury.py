"""Tests for Treasury department scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.dept_treasury import (
    _get_treasury_yield_curve_from_dep_treasury,
    get_treasury_yield_from_dep_treasury,
)


class TestTreasuryDeptScraping(TestCase):
    """Test cases for get_treasury_yield_from_dep_treasury."""

    MOCK_TREASURY_DEPT_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/treasury_dept/success.xml"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_treasury_yield_curve_from_dep_treasury.cache_clear()

    @patch("market_overview.services.scrapers.dept_treasury.requests.get")
    def test_treasury_yield_success(self, mock_get):
        """
        GIVEN a Treasury department XML with a success response
        WHEN scraping the yield for a specific date
        THEN the yield should be scraped successfully
        """
        target_date = date(2025, 1, 6)
        ticker = "UST10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_TREASURY_DEPT_SUCCESS, text="Success"
        )

        result = get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrapingResult(price=4.62, comment="")

    @patch("market_overview.services.scrapers.dept_treasury.requests.get")
    def test_treasury_yield_not_found(self, mock_get):
        """
        GIVEN a Treasury department XML with a success response
        WHEN scraping the yield for a specific date not included in the XML
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "UST10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_TREASURY_DEPT_SUCCESS, text="Success"
        )

        result = get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Yield curve not found.")

    @patch("market_overview.services.scrapers.dept_treasury.requests.get")
    def test_treasury_yield_invalid_ticker(self, mock_get):
        """
        GIVEN a Treasury department XML with a success response
        WHEN scraping the yield for a specific date with an invalid ticker
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "INVALID"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_TREASURY_DEPT_SUCCESS, text="Success"
        )

        result = get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Ticker not found in mapping."
        )

    @patch("market_overview.services.scrapers.dept_treasury.requests.get")
    def test_treasury_yield_http_error(self, mock_get):
        """
        GIVEN a Treasury department XML with an HTTP error response
        WHEN scraping the yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "UST10Y"

        mock_get.return_value = MockResponse(
            status_code=500,
            content=self.MOCK_TREASURY_DEPT_SUCCESS,
            text="Internal Server Error",
        )

        result = get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Internal Server Error")
