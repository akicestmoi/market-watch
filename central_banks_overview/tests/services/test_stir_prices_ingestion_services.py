from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest  # type: ignore[reportMissingImports]
from django.test import TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesPriceUpdateLogModel,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.stir_prices_ingestion_services import (
    BulkUpdateFuturesPricesItem,
    StirFutures,
    YFinanceTickerInfo,
    _get_fedfunds_futures_price,
    _get_fedfunds_futures_prices,
    _get_mutan_futures_accrual_dates,
    _get_mutan_futures_prices,
    _get_mutan_futures_prices_from_tfx,
    _get_third_wednesday_of_month,
    _get_ticker_info_from_maturity_month,
    bulk_update_futures_prices,
    bulk_update_futures_prices_from_csv,
    calculate_estr_reference_dates,
    delete_stir_futures_price_update_logs_before_date,
    delete_stir_futures_prices_before_date,
    extract_all_stir_futures_prices,
    extract_estr_prices_from_pdf,
    get_futures_prices,
    ingest_stir_futures_prices,
)
from core.tests import MockResponse, parse_query_for_testing, read_file_content
from market_overview.services import price_ingestion_services


class TestGetTickerInfoFromMaturityMonth(TestCase):
    """Test cases for _get_ticker_info_from_maturity_month function."""

    @freeze_time("2025-12-14 12:00:00")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
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
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
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
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
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
        price_ingestion_services.get_yahoo_finance_closing_prices.cache_clear()

    @freeze_time("2025-12-14 12:00:00")
    @patch("market_overview.services.price_ingestion_services.yf.Ticker")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
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
            return self._create_mock_ticker(ticker_symbol)

        mock_ticker.side_effect = ticker_side_effect

        result = _get_fedfunds_futures_prices(self.target_date)
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
    @patch("market_overview.services.price_ingestion_services.yf.Ticker")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
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
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history.return_value.reset_index.return_value = (
                pd.DataFrame()
            )
            return mock_ticker_instance

        mock_ticker.side_effect = ticker_side_effect

        result = _get_fedfunds_futures_prices(self.target_date)
        assert len(result) == 15
        assert all(item["price"] is None for item in result)
        assert all(
            item["comment"] and "Yahoo Finance: No prices found." in item["comment"]
            for item in result
        )

    @freeze_time("2025-12-14 12:00:00")
    @patch("market_overview.services.price_ingestion_services.yf.Ticker")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
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
            return self._create_mock_ticker(ticker_symbol)

        mock_ticker.side_effect = ticker_side_effect

        result = _get_fedfunds_futures_prices(self.target_date)

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


class TestEstrFuturesPricesIngestion(TestCase):
    """Test cases for ingestion functions related to estr futures."""

    MOCK_ESTR_PDF_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/estr_stir_futures/success.pdf"
    )

    def test_get_third_wednesday_of_month(self):
        """
        GIVEN a specific month and year
        WHEN getting the third Wednesday
        THEN the correct date is returned
        """
        result = _get_third_wednesday_of_month(2024, 1)
        assert result == date(2024, 1, 17)

    def test_get_third_wednesday_of_month_when_first_day_is_wednesday(self):
        """
        GIVEN a month where the first day is a Wednesday
        WHEN getting the third Wednesday
        THEN the correct date is returned (21st day)
        """
        result = _get_third_wednesday_of_month(2024, 5)  # May 1, 2024 is Wednesday
        assert result == date(2024, 5, 15)

    def test_calculate_estr_reference_dates_valid_maturity(self):
        """
        GIVEN a valid maturity string "24.03"
        WHEN calculating ESTR reference dates
        THEN correct first and last accrual dates are returned
        """
        first_date, last_date = calculate_estr_reference_dates("24.03")
        assert first_date == date(2024, 3, 20)  # Third Wednesday of March 2024
        # Last accrual date: business day prior to third Wednesday of June 2024 (June 19)
        assert last_date == date(
            2024, 6, 18
        )  # June 18, 2024 is a Tuesday (BDay(1) before June 19)

    def test_calculate_estr_reference_dates_invalid_format(self):
        """
        GIVEN an invalid maturity format
        WHEN calculating ESTR reference dates
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError, match="Invalid maturity format"):
            calculate_estr_reference_dates("invalid")

    def test_calculate_estr_reference_dates_invalid_month(self):
        """
        GIVEN a maturity with invalid month
        WHEN calculating ESTR reference dates
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError, match="Invalid month"):
            calculate_estr_reference_dates("24.13")

    def test_calculate_estr_reference_dates_missing_dot(self):
        """
        GIVEN a maturity without a dot separator
        WHEN calculating ESTR reference dates
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError, match="Invalid maturity format"):
            calculate_estr_reference_dates("2403")

    @freeze_time("2025-12-14 12:00:00")
    def test_extract_estr_prices_from_pdf_success(self):
        """
        GIVEN a valid ESTR PDF file
        WHEN extracting ESTR prices from PDF
        THEN list of StirFutures is returned
        """
        target_date = date(2024, 1, 15)
        result = extract_estr_prices_from_pdf(self.MOCK_ESTR_PDF_SUCCESS, target_date)

        assert result == [
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                short_name=StirFuturesNameChoices.ESTR3M,
                full_name="3 Month ESTR Futures",
                maturity="25.09",
                first_accrual_date=date(2025, 9, 17),
                last_accrual_date=date(2025, 12, 16),
                date=date(2024, 1, 15),
                price=98.07,
                source=StirFuturesSourceChoices.PDF,
                comment="Prices extracted from PDF file.",
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2025, 12, 17),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 3, 17),
                maturity="25.12",
                price=98.0675,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 3, 18),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 6, 16),
                maturity="26.03",
                price=98.0875,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 6, 17),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 9, 15),
                maturity="26.06",
                price=98.1125,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 9, 16),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 12, 15),
                maturity="26.09",
                price=98.1025,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 12, 16),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 3, 16),
                maturity="26.12",
                price=98.0575,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 3, 17),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 6, 15),
                maturity="27.03",
                price=97.9975,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 6, 16),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 9, 14),
                maturity="27.06",
                price=97.935,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 9, 15),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 12, 14),
                maturity="27.09",
                price=97.8725,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 12, 15),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 3, 14),
                maturity="27.12",
                price=97.81,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2028, 3, 15),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 6, 20),
                maturity="28.03",
                price=97.7475,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2028, 6, 21),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 9, 19),
                maturity="28.06",
                price=97.6875,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2028, 9, 20),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 12, 19),
                maturity="28.09",
                price=97.63,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
        ]

    def test_extract_estr_prices_from_pdf_invalid_pdf(self):
        """
        GIVEN an invalid PDF file
        WHEN extracting ESTR prices from PDF
        THEN a ValueError is raised
        """
        invalid_pdf = b"Not a valid PDF"
        target_date = date(2024, 1, 15)

        with pytest.raises(ValueError, match="Failed to parse PDF"):
            extract_estr_prices_from_pdf(invalid_pdf, target_date)

    def test_extract_estr_prices_from_pdf_no_valid_rows(self):
        """
        GIVEN a PDF with no valid ESTR rows
        WHEN extracting ESTR prices from PDF
        THEN an empty list is returned
        """
        # Create a minimal PDF that will parse but has no ER3 data
        # Using a simple PDF structure that pdfplumber can parse
        # but won't contain ER3 rows
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
            b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
            b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n"
            b"/Contents 4 0 R\n>>\nendobj\n"
            b"4 0 obj\n<<\n/Length 44\n>>\nstream\nBT /F1 12 Tf 100 700 Td (No ER3 data) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000206 00000 n \n"
            b"trailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n290\n%%EOF"
        )

        target_date = date(2024, 1, 15)
        result = extract_estr_prices_from_pdf(pdf_content, target_date)

        assert result == []


class TestMutanFuturesPricesIngestion(TestCase):
    """Test cases for ingestion functions related to mutan futures."""

    MOCK_MUTAN_CSV_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/mutan_stir_futures/success.csv"
    )

    MOCK_MUTAN_REFERENCE_DATES_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/mutan_stir_futures/reference_date_success.html"
    )

    def setUp(self):
        self.maturity_months = [
            "25.09",
            "25.12",
            "26.03",
            "26.06",
            "26.09",
            "26.12",
            "27.03",
            "27.06",
            "27.09",
            "27.12",
            "28.03",
            "28.06",
            "28.09",
            "28.12",
            "29.03",
            "29.06",
            "29.09",
            "29.12",
            "30.03",
            "30.06",
        ]

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_mutan_futures_prices_from_tfx.cache_clear()
        _get_mutan_futures_accrual_dates.cache_clear()

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_from_tfx_success(self, mock_get):
        """
        GIVEN TFX CSV response with mutan futures prices
        WHEN getting mutan futures prices from TFX
        THEN prices for the target date are returned as DataFrame
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_MUTAN_CSV_SUCCESS
        )

        target_date = date(2025, 12, 5)
        result = _get_mutan_futures_prices_from_tfx(target_date)
        expected_data_length = 20
        jp_product_name = "無担保コールオーバーナイト３ヵ月金利先物"
        en_product_name = "Three-month TONA Futures"
        price_day = "2025-12-05"
        prices = [
            99.521,
            99.311,
            99.248,
            99.138,
            99.03,
            98.938,
            98.855,
            98.775,
            98.654,
            98.603,
            98.559,
            98.521,
            98.486,
            98.451,
            98.419,
            98.388,
            98.357,
            98.327,
            98.297,
            98.268,
        ]
        expected = pd.DataFrame(
            {
                "商品名": [jp_product_name] * expected_data_length,
                "Product": [en_product_name] * expected_data_length,
                "限月": self.maturity_months,
                "取引日": [price_day] * expected_data_length,
                "公式終値": prices,
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_from_tfx_no_data_for_date(self, mock_get):
        """
        GIVEN TFX CSV response with no data for target date
        WHEN getting mutan futures prices from TFX
        THEN an empty DataFrame is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_MUTAN_CSV_SUCCESS
        )

        target_date = date(2026, 1, 1)  # Date not in mock data
        result = _get_mutan_futures_prices_from_tfx(target_date)
        # When there's no data, the function returns an empty DataFrame
        # but with the same column structure (5 columns)
        # The "公式終値" column should be float64 (pandas infers it from CSV)
        expected = pd.DataFrame(
            columns=["商品名", "Product", "限月", "取引日", "公式終値"]
        )
        expected["公式終値"] = expected["公式終値"].astype("float64")
        pd.testing.assert_frame_equal(result, expected)

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_get_mutan_futures_prices_from_tfx_request_exception(self, mock_get):
        """
        GIVEN a request exception when fetching from TFX
        WHEN getting mutan futures prices from TFX
        THEN a ValueError is raised
        """
        mock_get.side_effect = Exception("Connection error")

        target_date = date(2025, 12, 5)
        with pytest.raises(ValueError, match="Failed to fetch data from TFX"):
            _get_mutan_futures_prices_from_tfx(target_date)

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_get_mutan_futures_prices_from_tfx_no_header(self, mock_get):
        """
        GIVEN TFX CSV response without expected header
        WHEN getting mutan futures prices from TFX
        THEN a ValueError is raised
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=b"No header here\nJust data"
        )

        target_date = date(2025, 12, 5)
        with pytest.raises(ValueError, match="Could not find data header"):
            _get_mutan_futures_prices_from_tfx(target_date)

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_get_mutan_futures_accrual_dates_success(self, mock_get):
        """
        GIVEN TFX HTML response with trading calendar
        WHEN getting mutan futures reference dates
        THEN reference dates are returned as DataFrame
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_MUTAN_REFERENCE_DATES_SUCCESS
        )

        result = _get_mutan_futures_accrual_dates()
        additional_maturity_months = [
            "23.03",
            "23.06",
            "23.09",
            "23.12",
            "24.03",
            "24.06",
            "24.09",
            "24.12",
            "25.03",
            "25.06",
        ]
        first_accrual_dates = [
            date(2023, 3, 15),
            date(2023, 6, 21),
            date(2023, 9, 20),
            date(2023, 12, 20),
            date(2024, 3, 21),
            date(2024, 6, 19),
            date(2024, 9, 18),
            date(2024, 12, 18),
            date(2025, 3, 19),
            date(2025, 6, 18),
            date(2025, 9, 17),
            date(2025, 12, 17),
            date(2026, 3, 18),
            date(2026, 6, 17),
            date(2026, 9, 16),
            date(2026, 12, 16),
            date(2027, 3, 17),
            date(2027, 6, 16),
            date(2027, 9, 15),
            date(2027, 12, 15),
            date(2028, 3, 15),
            date(2028, 6, 21),
            date(2028, 9, 20),
            date(2028, 12, 20),
            date(2029, 3, 21),
            date(2029, 6, 20),
            date(2029, 9, 19),
            date(2029, 12, 19),
            date(2030, 3, 21),
            date(2030, 6, 19),
        ]
        last_accrual_dates = [
            date(2023, 6, 20),
            date(2023, 9, 19),
            date(2023, 12, 19),
            date(2024, 3, 20),
            date(2024, 6, 18),
            date(2024, 9, 17),
            date(2024, 12, 17),
            date(2025, 3, 18),
            date(2025, 6, 17),
            date(2025, 9, 16),
            date(2025, 12, 16),
            date(2026, 3, 17),
            date(2026, 6, 16),
            date(2026, 9, 15),
            date(2026, 12, 15),
            date(2027, 3, 16),
            date(2027, 6, 15),
            date(2027, 9, 14),
            date(2027, 12, 14),
            date(2028, 3, 14),
            date(2028, 6, 20),
            date(2028, 9, 19),
            date(2028, 12, 19),
            date(2029, 3, 20),
            date(2029, 6, 19),
            date(2029, 9, 18),
            date(2029, 12, 18),
            date(2030, 3, 20),
            date(2030, 6, 18),
            date(2030, 9, 17),
        ]
        expected = pd.DataFrame(
            {
                "限月": additional_maturity_months + self.maturity_months,
                "first_accrual_date": first_accrual_dates,
                "last_accrual_date": last_accrual_dates,
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_get_mutan_futures_accrual_dates_request_exception(self, mock_get):
        """
        GIVEN a request exception when fetching trading calendar
        WHEN getting mutan futures reference dates
        THEN a ValueError is raised
        """
        mock_get.side_effect = Exception("Connection error")

        with pytest.raises(ValueError, match="Failed to fetch trading calendar"):
            _get_mutan_futures_accrual_dates()

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_get_mutan_futures_accrual_dates_no_table(self, mock_get):
        """
        GIVEN TFX HTML response without expected table
        WHEN getting mutan futures reference dates
        THEN a ValueError is raised
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=b"<html><body>No table here</body></html>"
        )

        with pytest.raises(ValueError, match="Could not find trading calendar table"):
            _get_mutan_futures_accrual_dates()

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_mutan_futures_prices_from_tfx"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_mutan_futures_accrual_dates"
    )
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_success(self, mock_ref_dates, mock_prices):
        """
        GIVEN TFX prices and reference dates DataFrames
        WHEN getting mutan futures prices
        THEN combined StirFutures list is returned
        """
        mock_prices.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.12",
                    "取引日": "2025-12-05",
                    "公式終値": 99.500,
                }
            ]
        )
        mock_ref_dates.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.12",
                    "first_accrual_date": date(2025, 12, 17),
                    "last_accrual_date": date(2026, 3, 16),
                }
            ]
        )

        target_date = date(2025, 12, 5)
        result = _get_mutan_futures_prices(target_date)
        assert result == [
            StirFutures(
                central_bank=CentralBankChoices.BOJ,
                short_name=StirFuturesNameChoices.MUTAN3M,
                full_name="3 Month Mutan STIR Futures",
                maturity="25.12",
                first_accrual_date=date(2025, 12, 17),
                last_accrual_date=date(2026, 3, 16),
                date=target_date,
                price=99.500,
                source=StirFuturesSourceChoices.TFX,
                comment="",
            )
        ]

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_mutan_futures_prices_from_tfx"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_mutan_futures_accrual_dates"
    )
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_no_matching_maturity(
        self, mock_ref_dates, mock_prices
    ):
        """
        GIVEN TFX prices with no matching reference dates
        WHEN getting mutan futures prices
        THEN prices are returned with None for accrual dates
        """
        mock_prices.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.12",
                    "取引日": "2025-12-05",
                    "公式終値": 99.500,
                }
            ]
        )
        mock_ref_dates.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.06",  # Different maturity
                    "first_accrual_date": date(2025, 6, 18),
                    "last_accrual_date": date(2025, 9, 16),
                }
            ]
        )

        target_date = date(2025, 12, 5)
        result = _get_mutan_futures_prices(target_date)
        assert result == [
            StirFutures(
                central_bank=CentralBankChoices.BOJ,
                short_name=StirFuturesNameChoices.MUTAN3M,
                full_name="3 Month Mutan STIR Futures",
                maturity="25.12",
                first_accrual_date=None,
                last_accrual_date=None,
                date=target_date,
                price=99.500,
                source=StirFuturesSourceChoices.TFX,
                comment="",
            )
        ]


class TestStirPricesIngestionServices(TestCase):
    """Test cases for stir_prices_ingestion_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = date(2024, 1, 15)
        self.test_date_2 = date(2024, 2, 15)
        # Create FRB futures prices
        self.frb_future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.25,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        # Create ECB futures prices
        self.ecb_future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 3, 31),
            date=self.test_date,
            price=96.50,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        # Create another FRB future for different date
        self.frb_future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.02",
            first_accrual_date=date(2024, 2, 1),
            last_accrual_date=date(2024, 2, 29),
            date=self.test_date_2,
            price=95.50,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

    def test_get_futures_prices_no_filter(self):
        """
        GIVEN futures prices for a specific date
        WHEN getting futures prices with price_date
        THEN all futures prices for that date are returned
        """
        result = get_futures_prices(self.test_date)
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "comment": "",
                "date": date(2024, 1, 15),
                "first_accrual_date": date(2024, 3, 1),
                "full_name": "3 Month ESTR Futures",
                "last_accrual_date": date(2024, 3, 31),
                "maturity": "24.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.ESTR3M.value,
                "source": StirFuturesSourceChoices.TFX.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2024, 1, 15),
                "first_accrual_date": date(2024, 1, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2024, 1, 31),
                "maturity": "24.01",
                "price": 95.25,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]

    def test_get_futures_prices_with_central_banks_filter(self):
        """
        GIVEN futures prices for multiple central banks
        WHEN getting futures prices with central_banks filter
        THEN only futures prices for specified central banks are returned
        """
        result = get_futures_prices(self.test_date, [CentralBankChoices.FRB])
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2024, 1, 15),
                "first_accrual_date": date(2024, 1, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2024, 1, 31),
                "maturity": "24.01",
                "price": 95.25,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]

    def test_get_futures_prices_empty(self):
        """
        GIVEN no futures prices for a date
        WHEN getting futures prices for that date
        THEN an empty list is returned
        """
        result = get_futures_prices(date(2025, 1, 1))
        assert result == []

    def test_get_futures_prices_multiple_maturities(self):
        """
        GIVEN futures prices with multiple maturities for same central bank
        WHEN getting futures prices
        THEN all maturities are returned sorted
        """
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 3, 31),
            date=self.test_date,
            price=95.75,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        result = get_futures_prices(self.test_date, [CentralBankChoices.FRB])
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2024, 1, 15),
                "first_accrual_date": date(2024, 1, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2024, 1, 31),
                "maturity": "24.01",
                "price": 95.25,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2024, 1, 15),
                "first_accrual_date": date(2024, 3, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2024, 3, 31),
                "maturity": "24.03",
                "price": 95.75,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]

    def test_get_futures_prices_with_none_price(self):
        """
        GIVEN futures price with None value
        WHEN getting futures prices
        THEN the futures with None price is still returned
        """
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="24.04",
            first_accrual_date=date(2024, 4, 1),
            last_accrual_date=date(2024, 4, 30),
            date=self.test_date,
            price=None,
            source=StirFuturesSourceChoices.TFX,
            comment="No price available",
        )

        result = get_futures_prices(self.test_date, [CentralBankChoices.BOJ])
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "comment": "No price available",
                "date": date(2024, 1, 15),
                "first_accrual_date": date(2024, 4, 1),
                "full_name": "3 Month Mutan STIR Futures",
                "last_accrual_date": date(2024, 4, 30),
                "maturity": "24.04",
                "price": None,
                "short_name": StirFuturesNameChoices.MUTAN3M.value,
                "source": StirFuturesSourceChoices.TFX.value,
            },
        ]

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_fedfunds_futures_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_mutan_futures_prices"
    )
    @freeze_time("2024-01-15 12:00:00")
    def test_extract_all_stir_futures_prices_success(self, mock_mutan, mock_ff):
        """
        GIVEN all STIR futures prices sources available
        WHEN extracting all STIR futures prices
        THEN prices from all central banks are returned
        """
        mock_ff.return_value = [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=date(2024, 1, 15),
                price=95.25,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            )
        ]
        mock_mutan.return_value = [
            StirFutures(
                central_bank=CentralBankChoices.BOJ,
                short_name=StirFuturesNameChoices.MUTAN3M,
                full_name="3 Month Mutan STIR Futures",
                maturity="24.03",
                first_accrual_date=date(2024, 3, 1),
                last_accrual_date=date(2024, 3, 31),
                date=date(2024, 1, 15),
                price=99.50,
                source=StirFuturesSourceChoices.TFX,
                comment="",
            )
        ]

        target_date = date(2024, 1, 15)
        result = extract_all_stir_futures_prices(target_date)
        assert result == [
            {
                "central_bank": CentralBankChoices.FRB,
                "short_name": StirFuturesNameChoices.FF1M,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": date(2024, 1, 15),
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.BOJ,
                "short_name": StirFuturesNameChoices.MUTAN3M,
                "full_name": "3 Month Mutan STIR Futures",
                "maturity": "24.03",
                "first_accrual_date": date(2024, 3, 1),
                "last_accrual_date": date(2024, 3, 31),
                "date": date(2024, 1, 15),
                "price": 99.5,
                "source": StirFuturesSourceChoices.TFX,
                "comment": "",
            },
        ]

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_fedfunds_futures_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services._get_mutan_futures_prices"
    )
    @freeze_time("2024-01-15 12:00:00")
    def test_extract_all_stir_futures_prices_one_source_fails(
        self, mock_mutan, mock_ff
    ):
        """
        GIVEN one source fails but other succeeds
        WHEN extracting all STIR futures prices
        THEN prices from successful source are returned
        """
        mock_ff.return_value = [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=date(2024, 1, 15),
                price=95.25,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            )
        ]
        mock_mutan.side_effect = Exception("TFX unavailable")

        target_date = date(2024, 1, 15)
        with pytest.raises(Exception, match="TFX unavailable"):
            extract_all_stir_futures_prices(target_date)

    def test_ingest_stir_futures_prices_success(self):
        """
        GIVEN a list of StirFutures prices
        WHEN ingesting stir futures prices
        THEN prices are created in database and list of updated items is returned
        """
        StirFuturesModel.objects.all().delete()
        stir_futures_prices = [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=self.test_date,
                price=95.25,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            ),
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.02",
                first_accrual_date=date(2024, 2, 1),
                last_accrual_date=date(2024, 2, 29),
                date=self.test_date,
                price=95.50,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            ),
        ]

        stir_futures_updated = ingest_stir_futures_prices(stir_futures_prices)
        assert stir_futures_updated == stir_futures_prices
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.02",
                "first_accrual_date": date(2024, 2, 1),
                "last_accrual_date": date(2024, 2, 29),
                "date": self.test_date,
                "price": 95.50,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
        ]

    def test_ingest_stir_futures_prices_with_none_price(self):
        """
        GIVEN a list of StirFutures prices with some None prices
        WHEN ingesting stir futures prices
        THEN all prices are ingested but only non-None prices are returned
        """
        StirFuturesModel.objects.all().delete()
        stir_futures_prices = [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=self.test_date,
                price=95.25,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            ),
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.02",
                first_accrual_date=date(2024, 2, 1),
                last_accrual_date=date(2024, 2, 29),
                date=self.test_date,
                price=None,
                source=StirFuturesSourceChoices.YAHOO,
                comment="No price available",
            ),
        ]

        stir_futures_updated = ingest_stir_futures_prices(stir_futures_prices)
        assert stir_futures_updated == [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=self.test_date,
                price=95.25,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            ),
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.02",
                "first_accrual_date": date(2024, 2, 1),
                "last_accrual_date": date(2024, 2, 29),
                "date": self.test_date,
                "price": None,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "No price available",
            },
        ]

    def test_ingest_stir_futures_prices_updates_existing(self):
        """
        GIVEN existing stir futures price in database
        WHEN ingesting the same price
        THEN existing record is updated
        """
        StirFuturesModel.objects.all().delete()
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.00,  # Old price
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        stir_futures_prices = [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=self.test_date,
                price=95.25,  # New price
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            ),
        ]

        stir_futures_updated = ingest_stir_futures_prices(stir_futures_prices)
        assert stir_futures_updated == [
            StirFutures(
                central_bank=CentralBankChoices.FRB,
                short_name=StirFuturesNameChoices.FF1M,
                full_name="1 Month Fed Funds STIR Futures",
                maturity="24.01",
                first_accrual_date=date(2024, 1, 1),
                last_accrual_date=date(2024, 1, 31),
                date=self.test_date,
                price=95.25,
                source=StirFuturesSourceChoices.YAHOO,
                comment="",
            ),
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
        ]

    def test_bulk_update_futures_prices_success(self):
        """
        GIVEN multiple bulk update items
        WHEN bulk updating futures prices
        THEN all prices are updated
        """
        StirFuturesModel.objects.all().delete()
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.00,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.02",
            first_accrual_date=date(2024, 2, 1),
            last_accrual_date=date(2024, 2, 29),
            date=self.test_date,
            price=95.10,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        updates = [
            BulkUpdateFuturesPricesItem(
                date=self.test_date,
                short_name=StirFuturesNameChoices.FF1M,
                maturity="24.01",
                price=95.50,
                logs="Updated 1",
            ),
            BulkUpdateFuturesPricesItem(
                date=self.test_date,
                short_name=StirFuturesNameChoices.FF1M,
                maturity="24.02",
                price=95.60,
                logs="Updated 2",
            ),
        ]

        result = bulk_update_futures_prices(updates)
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.50,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Updated 1",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.02",
                "first_accrual_date": date(2024, 2, 1),
                "last_accrual_date": date(2024, 2, 29),
                "date": self.test_date,
                "price": 95.60,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Updated 2",
            },
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.50,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Updated 1",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.02",
                "first_accrual_date": date(2024, 2, 1),
                "last_accrual_date": date(2024, 2, 29),
                "date": self.test_date,
                "price": 95.60,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Updated 2",
            },
        ]

    def test_bulk_update_futures_prices_from_csv_success(self):
        """
        GIVEN a valid CSV file with futures prices
        WHEN bulk updating futures prices from CSV
        THEN prices are updated from CSV data
        """
        StirFuturesModel.objects.all().delete()
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.00,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        csv_content = (
            "date,short_name,maturity,price,logs\n"
            "2024-01-15,FF1M,24.01,95.75,Custom log message\n"
        ).encode("utf-8")

        result = bulk_update_futures_prices_from_csv(csv_content)
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.75,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Custom log message",
            }
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.75,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Custom log message",
            },
        ]

    def test_bulk_update_futures_prices_from_csv_missing_columns(self):
        """
        GIVEN a CSV file with missing required columns
        WHEN bulk updating futures prices from CSV
        THEN a ValueError is raised
        """
        StirFuturesModel.objects.all().delete()
        csv_content = (
            "date,short_name,maturity\n"  # Missing price and logs
            "2024-01-15,FF1M,24.01\n"
        ).encode("utf-8")

        with pytest.raises(
            ValueError, match="CSV file must have the following columns"
        ):
            bulk_update_futures_prices_from_csv(csv_content)

    def test_bulk_update_futures_prices_from_csv_empty_logs(self):
        """
        GIVEN a CSV file with empty logs column
        WHEN bulk updating futures prices from CSV
        THEN default log message is generated
        """
        StirFuturesModel.objects.all().delete()
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.00,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        csv_content = (
            "date,short_name,maturity,price,logs\n"
            "2024-01-15,FF1M,24.01,95.75,\n"  # Empty logs
        ).encode("utf-8")

        result = bulk_update_futures_prices_from_csv(csv_content)
        assert [price.convert_to_dict() for price in result] == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.75,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Bulk update from CSV file of FF1M to price: 95.75.",
            }
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.75,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Bulk update from CSV file of FF1M to price: 95.75.",
            },
        ]

    def test_delete_stir_futures_prices_before_date(self):
        """
        GIVEN futures prices before and after a date for a central bank
        WHEN deleting prices before date
        THEN only prices before the date for that bank are deleted
        """
        price_before = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=date(2023, 12, 1),
            price=95.00,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        price_after = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.02",
            first_accrual_date=date(2024, 2, 1),
            last_accrual_date=date(2024, 2, 29),
            date=date(2024, 2, 1),
            price=95.10,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        price_other_bank = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=date(2023, 12, 1),
            price=96.00,
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )

        cutoff_date = date(2024, 1, 1)
        delete_stir_futures_prices_before_date(CentralBankChoices.FRB, cutoff_date)
        assert not StirFuturesModel.objects.filter(
            date=price_before.date,
            central_bank=price_before.central_bank,
            short_name=price_before.short_name,
            maturity=price_before.maturity,
        ).exists()
        assert StirFuturesModel.objects.filter(
            date=price_after.date,
            central_bank=price_after.central_bank,
            short_name=price_after.short_name,
            maturity=price_after.maturity,
        ).exists()
        assert StirFuturesModel.objects.filter(
            date=price_other_bank.date,
            central_bank=price_other_bank.central_bank,
            short_name=price_other_bank.short_name,
            maturity=price_other_bank.maturity,
        ).exists()

    def test_delete_stir_futures_price_update_logs_before_date(self):
        """
        GIVEN price update logs before and after a date
        WHEN deleting logs before date
        THEN only logs before the date are deleted
        """
        StirFuturesModel.objects.all().delete()
        StirFuturesPriceUpdateLogModel.objects.all().delete()

        future_before = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.00,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        future_after = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.02",
            first_accrual_date=date(2024, 2, 1),
            last_accrual_date=date(2024, 2, 29),
            date=date(2024, 2, 1),
            price=95.10,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        log_before = StirFuturesPriceUpdateLogModel.objects.create(
            stir_futures=future_before,
            logs="Old log",
        )
        log_before.date_added = datetime(2023, 12, 1, tzinfo=timezone.utc)
        log_before.save()

        log_after = StirFuturesPriceUpdateLogModel.objects.create(
            stir_futures=future_after,
            logs="New log",
        )
        log_after.date_added = datetime(2024, 2, 1, tzinfo=timezone.utc)
        log_after.save()

        cutoff_date = date(2024, 1, 1)
        delete_stir_futures_price_update_logs_before_date(cutoff_date)
        assert not StirFuturesPriceUpdateLogModel.objects.filter(
            id=log_before.pk
        ).exists()
        assert StirFuturesPriceUpdateLogModel.objects.filter(id=log_after.pk).exists()
