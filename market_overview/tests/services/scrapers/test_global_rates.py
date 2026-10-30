"""Tests for GlobalRates scraper."""

from datetime import date
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import TestCase

from core.testing import MockResponse, read_file_content
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.global_rates import scrap_from_global_rates


class TestGlobalRatesScraping(TestCase):
    """Test cases for scrap_from_global_rates."""

    MOCK_GLOBAL_RATES_EURIBOR_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/euribor_success.html"
    )
    MOCK_GLOBAL_RATES_EURIBOR_INVALID_DATE = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/euribor_invalid_date.html"
    )
    MOCK_GLOBAL_RATES_EURIBOR_INVALID_RATE = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/euribor_invalid_rate.html"
    )
    MOCK_GLOBAL_RATES_CENTRAL_BANK_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/central_bank_success.html"
    )
    MOCK_GLOBAL_RATES_CENTRAL_BANK_EMPTY_RATE = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/central_bank_empty_rate.html"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        scrap_from_global_rates.cache_clear()

    @patch("core.services.requests.get")
    def test_global_rates_euribor_success(self, mock_get):
        """
        GIVEN a successful Global Rates HTML response with EURIBOR data
        WHEN scraping the EURIBOR rate for a specific date
        THEN the EURIBOR rate should be returned successfully
        """
        target_date = date(2025, 11, 25)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_SUCCESS,
        )

        result = scrap_from_global_rates(target_date, ticker)
        assert result == ScrapingResult(price=1.926, comment="")

    @patch("core.services.requests.get")
    def test_global_rates_euribor_not_found(self, mock_get):
        """
        GIVEN a Global Rates HTML response without data for the target date
        WHEN scraping the EURIBOR rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_SUCCESS,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Euribor rate not found.")

    @patch("core.services.requests.get")
    def test_global_rates_euribor_invalid_date(self, mock_get):
        """
        GIVEN a Global Rates HTML response with invalid date format
        WHEN scraping the EURIBOR rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_INVALID_DATE,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Euribor rate not found.")

    @patch("core.services.requests.get")
    def test_global_rates_euribor_invalid_rate(self, mock_get):
        """
        GIVEN a Global Rates HTML response with invalid rate format
        WHEN scraping the EURIBOR rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_INVALID_RATE,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Could not parse Euribor rate: invalid-rate"
        )

    @patch("core.services.requests.get")
    def test_global_rates_central_bank_success(self, mock_get):
        """
        GIVEN a successful Global Rates HTML response with central bank data
        WHEN scraping the central bank rate
        THEN the central bank rate should be returned successfully
        """
        ticker = "central-banks/9/japanese-boj-overnight-call-rate/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_CENTRAL_BANK_SUCCESS,
        )

        result = scrap_from_global_rates(None, ticker)

        assert result == ScrapingResult(price=0.5, comment="")

    @patch("core.services.requests.get")
    def test_global_rates_central_bank_empty_rate(self, mock_get):
        """
        GIVEN a Global Rates HTML response with an empty rate cell
        WHEN scraping the central bank rate
        THEN the rate should be None and commented accordingly
        """
        target_date = None
        ticker = "central-banks/ecb/ecb-interest-rate"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_CENTRAL_BANK_EMPTY_RATE,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(price=None, comment="Rate cell is empty")

    @patch("market_overview.services.scrapers.global_rates.fetch_html")
    def test_global_rates_fetch_failed(self, mock_fetch_html):
        """
        GIVEN a failed HTML fetch (fetch_html returns None)
        WHEN scraping rates from Global Rates
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_fetch_html.return_value = None

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(
            price=None,
            comment="Failed to fetch HTML from https://www.global-rates.com/en/interest-rates",
        )

    @patch("market_overview.services.scrapers.global_rates.fetch_html")
    def test_global_rates_no_table(self, mock_fetch_html):
        """
        GIVEN a Global Rates HTML response with no table
        WHEN scraping rates from Global Rates
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        mock_fetch_html.return_value = soup

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Could not find interest rates table on page"
        )

    @patch("market_overview.services.scrapers.global_rates.fetch_html")
    def test_global_rates_unsupported_rate_type(self, mock_fetch_html):
        """
        GIVEN a Global Rates HTML response with an unsupported rate type
        WHEN scraping rates from Global Rates
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "unknown/rate-type"

        soup = BeautifulSoup("<html><body><table></table></body></html>", "html.parser")
        mock_fetch_html.return_value = soup

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Unsupported rate type: unknown"
        )
