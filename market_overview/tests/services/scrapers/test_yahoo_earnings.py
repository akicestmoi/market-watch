"""Tests for Yahoo Finance earnings snapshot scraping."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase

from market_overview.services.scrapers.yahoo import (
    YahooEarningsInformation,
    YahooEarningsSnapshot,
    get_yahoo_finance_earnings_snapshot,
)


class TestGetYahooFinanceEarningsSnapshot(TestCase):
    """Test cases for 'get_yahoo_finance_earnings_snapshot'."""

    def setUp(self):
        """Clear the Yahoo earnings TTL cache so each test hits the mock."""
        get_yahoo_finance_earnings_snapshot.cache_clear()

    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    def test_get_yahoo_finance_earnings_snapshot(self, mock_ticker):
        """
        GIVEN Yahoo history, calendar, estimates, and a quarterly income statement
        WHEN get_yahoo_finance_earnings_snapshot is called
        THEN upcoming is the next schedule and current/previous are reported results
        """
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.earnings_history = pd.DataFrame(
            {
                "epsActual": [1.57, 2.10],
                "epsEstimate": [1.43, 1.98],
            },
            index=pd.to_datetime(["2026-06-30", "2026-09-30"]),
        )
        mock_ticker_instance.quarterly_income_stmt = pd.DataFrame(
            {
                pd.Timestamp("2026-06-30"): [
                    94_000_000_000.0,
                    28_000_000_000.0,
                    44_000_000_000.0,
                    32_000_000_000.0,
                ],
                pd.Timestamp("2026-09-30"): [
                    114_000_000_000.0,
                    35_000_000_000.0,
                    54_000_000_000.0,
                    39_000_000_000.0,
                ],
            },
            index=[
                "Total Revenue",
                "Operating Income",
                "Gross Profit",
                "EBITDA",
            ],
        )
        mock_ticker_instance.earnings_estimate = pd.DataFrame(
            {"avg": [2.91]},
            index=["0q"],
        )
        mock_ticker_instance.calendar = {
            "Earnings Date": [date(2027, 1, 28)],
            "Earnings Average": 2.91,
            "Revenue Average": 156_000_000_000.0,
        }
        mock_ticker_instance.get_earnings_dates.side_effect = ImportError("no lxml")
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_earnings_snapshot("AAPL")

        assert result == YahooEarningsSnapshot(
            upcoming=YahooEarningsInformation(
                announcement_datetime=datetime(2027, 1, 28, 21, 0, tzinfo=timezone.utc),
                reporting_period_end=None,
                is_reported=False,
                eps_actual=None,
                eps_expected=2.91,
                revenue_expected=156_000_000_000.0,
                revenue=None,
                operating_income=None,
                gross_profit=None,
                ebitda=None,
            ),
            current=YahooEarningsInformation(
                # No earnings_dates available → leave call datetime empty rather
                # than faking it with the fiscal period end.
                announcement_datetime=None,
                reporting_period_end=date(2026, 9, 30),
                is_reported=True,
                eps_actual=2.10,
                eps_expected=1.98,
                revenue_expected=None,
                revenue=114_000_000_000.0,
                operating_income=35_000_000_000.0,
                gross_profit=54_000_000_000.0,
                ebitda=39_000_000_000.0,
            ),
            previous=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 6, 30),
                is_reported=True,
                eps_actual=1.57,
                eps_expected=1.43,
                revenue_expected=None,
                revenue=94_000_000_000.0,
                operating_income=28_000_000_000.0,
                gross_profit=44_000_000_000.0,
                ebitda=32_000_000_000.0,
            ),
        )

    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    def test_get_yahoo_finance_earnings_snapshot_matches_call_without_period_end(
        self,
        mock_ticker,
    ):
        """
        GIVEN earnings_dates without a Period End column (current yfinance shape)
        WHEN get_yahoo_finance_earnings_snapshot is called
        THEN the reported call date is matched after the fiscal period end
        """
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.earnings_history = pd.DataFrame(
            {
                "epsActual": [2.02, 2.10],
                "epsEstimate": [1.89, 1.98],
            },
            index=pd.to_datetime(["2026-06-30", "2026-09-30"]),
        )
        mock_ticker_instance.quarterly_income_stmt = pd.DataFrame()
        mock_ticker_instance.earnings_estimate = pd.DataFrame(
            {"avg": [2.91]},
            index=["0q"],
        )
        mock_ticker_instance.calendar = {
            "Earnings Date": [date(2027, 1, 28)],
            "Earnings Average": 2.91,
            "Revenue Average": 156_000_000_000.0,
        }
        mock_ticker_instance.get_earnings_dates.return_value = pd.DataFrame(
            {
                "EPS Estimate": [2.91, 1.98, 1.89],
                "Reported EPS": [None, 2.10, 2.02],
                "Surprise(%)": [None, 5.8, 6.7],
            },
            index=pd.to_datetime(
                [
                    "2027-01-28 16:00:00-05:00",
                    "2026-11-02 16:00:00-05:00",
                    "2026-07-30 16:00:00-04:00",
                ]
            ),
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_earnings_snapshot("AAPL")

        assert result.current is not None
        assert result.current.reporting_period_end == date(2026, 9, 30)
        assert result.current.announcement_datetime == datetime(
            2026, 11, 2, 21, 0, tzinfo=timezone.utc
        )
        assert result.upcoming is not None
        assert result.upcoming.announcement_datetime == datetime(
            2027, 1, 28, 21, 0, tzinfo=timezone.utc
        )
        assert result.previous is not None
        assert result.previous.reporting_period_end == date(2026, 6, 30)
