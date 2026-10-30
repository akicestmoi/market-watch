"""Tests for Fed Funds futures scraper."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase
from freezegun import freeze_time

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.scrapers.fedfunds_futures import (
    YFinanceTickerInfo,
    _get_fedfunds_futures_price,
    _get_ticker_info_from_maturity_month,
    get_fedfunds_futures_prices,
)
from central_banks_overview.services.scrapers.common import StirFutures
from market_overview.services.scrapers.yahoo import get_yahoo_finance_closing_prices


class TestGetTickerInfoFromMaturityMonth(TestCase):
    """Test cases for _get_ticker_info_from_maturity_month function."""

    @freeze_time("2025-12-14 12:00:00")
    @patch(
        "central_banks_overview.services.scrapers.fedfunds_futures.get_central_bank_next_meeting_date"
    )
    def test_get_ticker_info_future_meeting_date(self, mock_next_meeting):
        """
        GIVEN next meeting date is in the future
        WHEN getting ticker info for maturity months
        THEN month_offset equals maturity_month (no adjustment)
        """
        mock_next_meeting.return_value = datetime(
            2026, 1, 15, 13, 0, tzinfo=timezone.utc
        )

        # maturity_month 0: now (2025-12-14) + 0 months = 2025-12-14
        result = _get_ticker_info_from_maturity_month(0)
        assert result == YFinanceTickerInfo(
            ticker="ZQZ25.CBT",
            date=datetime(2025, 12, 14, 12, 0, tzinfo=timezone.utc),
        )

        # maturity_month 1: now (2025-12-14) + 1 month = 2026-01-14
        result = _get_ticker_info_from_maturity_month(1)
        assert result == YFinanceTickerInfo(
            ticker="ZQF26.CBT",
            date=datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc),
        )

        # maturity_month 14: now (2025-12-14) + 14 months = 2027-02-14
        result = _get_ticker_info_from_maturity_month(14)
        assert result == YFinanceTickerInfo(
            ticker="ZQG27.CBT",
            date=datetime(2027, 2, 14, 12, 0, tzinfo=timezone.utc),
        )

    @freeze_time("2025-12-14 12:00:00")
    @patch(
        "central_banks_overview.services.scrapers.fedfunds_futures.get_central_bank_next_meeting_date"
    )
    def test_get_ticker_info_past_meeting_date(self, mock_next_meeting):
        """
        GIVEN next meeting date is in the past
        WHEN getting ticker info for maturity months
        THEN month_offset equals maturity_month + 1 (adjusted)
        """
        mock_next_meeting.return_value = datetime(
            2025, 12, 10, 13, 0, tzinfo=timezone.utc
        )

        # maturity_month 0: now (2025-12-14) + (0 + 1) months = 2026-01-14
        result = _get_ticker_info_from_maturity_month(0)
        assert result == YFinanceTickerInfo(
            ticker="ZQF26.CBT",
            date=datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc),
        )

        # maturity_month 1: now (2025-12-14) + (1 + 1) months = 2026-02-14
        result = _get_ticker_info_from_maturity_month(1)
        assert result == YFinanceTickerInfo(
            ticker="ZQG26.CBT",
            date=datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc),
        )

        # maturity_month 14: now (2025-12-14) + (14 + 1) months = 2027-03-14
        result = _get_ticker_info_from_maturity_month(14)
        assert result == YFinanceTickerInfo(
            ticker="ZQH27.CBT",
            date=datetime(2027, 3, 14, 12, 0, tzinfo=timezone.utc),
        )

    @freeze_time("2025-12-14 12:00:00")
    @patch(
        "central_banks_overview.services.scrapers.fedfunds_futures.get_central_bank_next_meeting_date"
    )
    def test_get_ticker_info_no_meeting_date(self, mock_next_meeting):
        """
        GIVEN no next meeting date is available
        WHEN getting ticker info for maturity months
        THEN month_offset equals maturity_month (no adjustment)
        """
        mock_next_meeting.return_value = None

        # maturity_month 0: now (2025-12-14) + 0 months = 2025-12-14
        result = _get_ticker_info_from_maturity_month(0)
        assert result == YFinanceTickerInfo(
            ticker="ZQZ25.CBT",
            date=datetime(2025, 12, 14, 12, 0, tzinfo=timezone.utc),
        )


class TestFedFundFuturesPricesIngestion(TestCase):
    """Test cases for ingestion functions related to fedfund futures."""

    MOCK_FF_STIR_FUTURES_SUCCESS_PATH = (
        "central_banks_overview/tests/mock_web_data/ff_stir_futures"
    )

    def setUp(self):
        """Set up test fixtures."""
        self.target_date = date(2025, 12, 10)
        self.mock_dataframes = {}
        csv_files = [
            "ZQZ25.CBT.csv",
            "ZQF26.CBT.csv",
            "ZQG26.CBT.csv",
            "ZQH26.CBT.csv",
            "ZQJ26.CBT.csv",
            "ZQK26.CBT.csv",
            "ZQM26.CBT.csv",
            "ZQN26.CBT.csv",
            "ZQQ26.CBT.csv",
            "ZQU26.CBT.csv",
            "ZQV26.CBT.csv",
            "ZQX26.CBT.csv",
            "ZQZ26.CBT.csv",
            "ZQF27.CBT.csv",
            "ZQG27.CBT.csv",
            "ZQH27.CBT.csv",
            "ZQJ27.CBT.csv",
        ]
        for csv_file in csv_files:
            csv_path = f"{self.MOCK_FF_STIR_FUTURES_SUCCESS_PATH}/{csv_file}"
            df = pd.read_csv(csv_path)
            # Convert Date column to datetime
            df["Date"] = pd.to_datetime(df["Date"])
            ticker_key = csv_file.replace(".csv", "")
            self.mock_dataframes[ticker_key] = df

    def _create_mock_ticker(self, ticker_symbol: str) -> MagicMock:
        """Create a mock ticker instance that returns the appropriate DataFrame."""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.mock_dataframes[ticker_symbol]
        )
        return mock_ticker_instance

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_fedfunds_futures_price.cache_clear()
        get_yahoo_finance_closing_prices.cache_clear()

    @freeze_time("2025-12-14 12:00:00")
    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    @patch(
        "central_banks_overview.services.scrapers.fedfunds_futures.get_central_bank_next_meeting_date"
    )
    def test_get_fedfunds_futures_prices_success(self, mock_next_meeting, mock_ticker):
        """
        GIVEN Yahoo Finance returns prices for Fed Funds futures
        WHEN getting Fed Funds futures prices
        THEN list of StirFutures for all maturities is returned
        """
        mock_next_meeting.return_value = datetime(
            2026, 1, 15, 13, 0, tzinfo=timezone.utc
        )

        def ticker_side_effect(ticker_symbol):
            """Return a mock Yahoo ticker for the given symbol."""
            return self._create_mock_ticker(ticker_symbol)

        mock_ticker.side_effect = ticker_side_effect

        result = get_fedfunds_futures_prices(self.target_date)
        assert len(result) == 15
        assert result[0] == StirFutures(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="25.12",
            first_accrual_date=date(2025, 12, 1),
            last_accrual_date=date(2025, 12, 31),
            date=self.target_date,
            price=96.27749633789062,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        # maturity_month 14: now (2025-12-14) + 14 months = 2027-02-14
        # ticker = ZQG27.CBT, maturity = 27.02
        assert result[-1] == StirFutures(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="27.02",
            first_accrual_date=date(2027, 2, 1),
            last_accrual_date=date(2027, 2, 28),
            date=self.target_date,
            price=96.87999725341795,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

    @freeze_time("2025-12-14 12:00:00")
    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    @patch(
        "central_banks_overview.services.scrapers.fedfunds_futures.get_central_bank_next_meeting_date"
    )
    def test_get_fedfunds_futures_prices_none_price(
        self, mock_next_meeting, mock_ticker
    ):
        """
        GIVEN Yahoo Finance returns None price
        WHEN getting Fed Funds futures prices
        THEN StirFutures with None price and comment is returned
        """
        mock_next_meeting.return_value = datetime(
            2026, 1, 15, 13, 0, tzinfo=timezone.utc
        )

        # Mock ticker to return empty DataFrame (no data) for all ticker calls
        def ticker_side_effect(ticker_symbol):
            """Return a mock ticker whose history is an empty DataFrame."""
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history.return_value.reset_index.return_value = (
                pd.DataFrame()
            )
            return mock_ticker_instance

        mock_ticker.side_effect = ticker_side_effect

        result = get_fedfunds_futures_prices(self.target_date)
        assert len(result) == 15
        assert all(item["price"] is None for item in result)
        assert all(
            item["comment"] and "Yahoo Finance: No prices found." in item["comment"]
            for item in result
        )

    @freeze_time("2025-12-14 12:00:00")
    @patch("market_overview.services.scrapers.yahoo.yf.Ticker")
    @patch(
        "central_banks_overview.services.scrapers.fedfunds_futures.get_central_bank_next_meeting_date"
    )
    def test_get_fedfunds_futures_prices_after_meeting(
        self, mock_next_meeting, mock_ticker
    ):
        """
        GIVEN next meeting date is in the past
        WHEN getting Fed Funds futures prices
        THEN month_offset is adjusted correctly
        """
        # Meeting date is in the past (before current date)
        mock_next_meeting.return_value = datetime(
            2025, 12, 10, 13, 0, tzinfo=timezone.utc
        )

        def ticker_side_effect(ticker_symbol):
            """Return a mock Yahoo ticker for the given symbol."""
            return self._create_mock_ticker(ticker_symbol)

        mock_ticker.side_effect = ticker_side_effect

        result = get_fedfunds_futures_prices(self.target_date)

        # Verify we get 15 items and assert first item structure
        # When meeting is in past, month_offset adds 1
        # maturity_month 0: now (2025-12-14) + (0 + 1) months = 2026-01-14
        # ticker = ZQF26.CBT, maturity = 26.01
        assert len(result) == 15
        assert result[0] == StirFutures(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.target_date,
            price=96.36000061035156,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        # maturity_month 14: now (2025-12-14) + (14 + 1) months = 2027-03-14
        # ticker = ZQH27.CBT, maturity = 27.03
        assert result[-1] == StirFutures(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="27.03",
            first_accrual_date=date(2027, 3, 1),
            last_accrual_date=date(2027, 3, 31),
            date=self.target_date,
            price=96.87999725341795,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
