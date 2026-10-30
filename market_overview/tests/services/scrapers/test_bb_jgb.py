"""Tests for BB JGB scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from market_overview.services.scrapers.bb_jgb import (
    _scrap_jgb_yield_curve_from_bb,
    get_jgb_yield_from_bb,
)
from market_overview.services.scrapers.common import ScrapingResult


class TestBBScraping(TestCase):
    """Test cases for get_jgb_yield_from_bb."""

    MOCK_BB_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/bb/success.html"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _scrap_jgb_yield_curve_from_bb.cache_clear()

    @patch("core.services.requests.get")
    def test_bb_success(self, mock_get):
        """
        GIVEN a successful BB HTML response with JGB yield data
        WHEN scraping the JGB yield for a specific date
        THEN the JGB yield should be returned successfully
        """
        target_date = date(2025, 11, 26)
        ticker = "JGB10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BB_SUCCESS
        )

        result = get_jgb_yield_from_bb(target_date, ticker)

        assert result == ScrapingResult(price=1.8, comment="")

    @patch("core.services.requests.get")
    def test_bb_not_found(self, mock_get):
        """
        GIVEN a BB HTML response without data for the target date
        WHEN scraping the JGB yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "JGB10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BB_SUCCESS, text="Success"
        )

        result = get_jgb_yield_from_bb(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Yield curve not found.")

    @patch("core.services.requests.get")
    def test_bb_invalid_ticker(self, mock_get):
        """
        GIVEN a BB HTML response with a valid date but an invalid ticker
        WHEN scraping the JGB yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "INVALID"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BB_SUCCESS
        )

        result = get_jgb_yield_from_bb(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Ticker not found in mapping."
        )
