"""Tests for Yahoo Finance scraper."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase

from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.yahoo import get_yahoo_finance_closing_prices


def _read_yfinance_mock(file_path: str) -> pd.DataFrame:
    """Read Yahoo Finance mock data from CSV file."""
    mock_df = pd.read_csv(file_path)
    mock_df["Date"] = pd.to_datetime(mock_df["Date"])
    return mock_df


class TestYahooFinanceScraping(TestCase):
    """Test cases for get_yahoo_finance_closing_prices."""

    MOCK_YAHOO_FINANCE_SUCCESS = _read_yfinance_mock(
        "market_overview/tests/mock_web_data/yfinance/success.csv"
    )
    MOCK_YAHOO_FINANCE_EMPTY = _read_yfinance_mock(
        "market_overview/tests/mock_web_data/yfinance/empty.csv"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_yahoo_finance_closing_prices.cache_clear()

    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    def test_yahoo_finance_success(self, mock_ticker):
        """
        GIVEN a successful yfinance API response
        WHEN getting the closing prices for a specific date
        THEN the closing prices of this date should be returned
        """
        target_date = date(2024, 1, 15)
        ticker = "^DJI"

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.MOCK_YAHOO_FINANCE_SUCCESS
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_closing_prices(target_date, ticker)

        assert result == ScrapingResult(price=110.0, comment="")

    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    def test_yahoo_finance_empty_dataframe(self, mock_ticker):
        """
        GIVEN a yfinance API with empty DataFrame
        WHEN getting the closing prices for a specific date
        THEN the closing prices should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "^DJI"

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.MOCK_YAHOO_FINANCE_EMPTY
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_closing_prices(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Yahoo Finance: No prices found."
        )

    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    def test_yahoo_finance_date_not_found(self, mock_ticker):
        """
        GIVEN a yfinance API with a DataFrame but no data for the target date
        WHEN getting the closing prices for a specific date
        THEN the closing prices should be None and commented accordingly
        """
        target_date = date(2024, 2, 20)
        ticker = "^DJI"

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.MOCK_YAHOO_FINANCE_SUCCESS
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_closing_prices(target_date, ticker)

        assert result == ScrapingResult(
            price=None, comment="Yahoo Finance: No prices found."
        )
