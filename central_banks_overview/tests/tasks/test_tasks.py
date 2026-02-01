from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

import central_banks_overview.tasks as tasks
from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankMeetingModel,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesPriceUpdateLogModel,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.cb_meetings_services import (
    _extract_boj_meeting_dates,
    _extract_ecb_meeting_dates,
    _extract_fomc_meeting_dates,
)
from central_banks_overview.services.stir_prices_ingestion_services import (
    _get_fedfunds_futures_price,
    _get_mutan_futures_accrual_dates,
    _get_mutan_futures_prices_from_tfx,
)
from core.tests import MockResponse, parse_query_for_testing, read_file_content
from market_overview.services.price_ingestion_services import ScrapingResult


class TestScheduledStirPricesIngestion(TestCase):
    """Test cases for scheduled_stir_prices_ingestion task."""

    MOCK_MUTAN_CSV_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/mutan_stir_futures/success.csv"
    )
    MOCK_MUTAN_REFERENCE_DATES_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/mutan_stir_futures/reference_date_success.html"
    )

    def setUp(self):
        """Set up test fixtures."""
        self.price_date = date(2025, 12, 12)

    def tearDown(self):
        """Clear caches to prevent test interference."""
        _get_fedfunds_futures_price.cache_clear()
        _get_mutan_futures_accrual_dates.cache_clear()
        _get_mutan_futures_prices_from_tfx.cache_clear()

    @freeze_time("2025-12-06")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_yahoo_finance_closing_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_scheduled_stir_prices_ingestion_success_one_bday_ago(
        self,
        mock_requests_get,
        mock_next_meeting,
        mock_yahoo_finance,
    ):
        """
        GIVEN valid STIR futures prices data from scraping
        WHEN scheduled_stir_prices_ingestion is called with two_bdays_ago=False
        THEN the task should successfully ingest prices for one business day ago
        """
        price_date = date(2025, 12, 5)  # One business day before
        mock_next_meeting.return_value = datetime(
            2026, 1, 15, 13, 0, tzinfo=timezone.utc
        )

        def yahoo_finance_side_effect(_, ticker):
            # ZQH26.CBT corresponds to March 2026 (H = Mar, 26 = 2026)
            if ticker == "ZQH26.CBT":
                return {"price": 96.5, "comment": None}
            return {"price": None, "comment": "No price"}

        mock_yahoo_finance.side_effect = yahoo_finance_side_effect

        # Mock TFX requests (for BOJ futures) - use mock CSV and HTML data
        def requests_get_side_effect(url, **kwargs):
            if "tradingcalendar.html" in url:
                # Return mock HTML for accrual dates
                return MockResponse(
                    status_code=200, content=self.MOCK_MUTAN_REFERENCE_DATES_SUCCESS
                )
            else:
                # Return mock CSV for prices
                return MockResponse(
                    status_code=200, content=self.MOCK_MUTAN_CSV_SUCCESS
                )

        mock_requests_get.side_effect = requests_get_side_effect

        # Verify no STIR futures prices exist before
        assert StirFuturesModel.objects.filter(date=price_date).count() == 0

        result = tasks.scheduled_stir_prices_ingestion(two_bdays_ago=False)
        assert result == {
            "date": price_date.isoformat(),
            "message": "STIR Futures prices successfully ingested for 2025-12-05",
            "status": "success",
            "stir_futures_updated": [
                "FF1M.26.03",
                "MUTAN3M.25.09",
                "MUTAN3M.25.12",
                "MUTAN3M.26.03",
                "MUTAN3M.26.06",
                "MUTAN3M.26.09",
                "MUTAN3M.26.12",
                "MUTAN3M.27.03",
                "MUTAN3M.27.06",
                "MUTAN3M.27.09",
                "MUTAN3M.27.12",
                "MUTAN3M.28.03",
                "MUTAN3M.28.06",
                "MUTAN3M.28.09",
                "MUTAN3M.28.12",
                "MUTAN3M.29.03",
                "MUTAN3M.29.06",
                "MUTAN3M.29.09",
                "MUTAN3M.29.12",
                "MUTAN3M.30.03",
                "MUTAN3M.30.06",
            ],
        }
        stir_futures = parse_query_for_testing(
            StirFuturesModel.objects.all().order_by("maturity", "date")
        )
        assert stir_futures[:5] == [
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": date(2025, 9, 17),
                "full_name": "3 Month Mutan STIR Futures",
                "last_accrual_date": date(2025, 12, 16),
                "maturity": "25.09",
                "price": 99.521,
                "short_name": StirFuturesNameChoices.MUTAN3M.value,
                "source": StirFuturesSourceChoices.TFX.value,
            },
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": date(2025, 12, 17),
                "full_name": "3 Month Mutan STIR Futures",
                "last_accrual_date": date(2026, 3, 17),
                "maturity": "25.12",
                "price": 99.311,
                "short_name": StirFuturesNameChoices.MUTAN3M.value,
                "source": StirFuturesSourceChoices.TFX.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "Yahoo Finance: No prices found.",
                "date": date(2025, 12, 5),
                "first_accrual_date": date(2025, 12, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2025, 12, 31),
                "maturity": "25.12",
                "price": None,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "Yahoo Finance: No prices found.",
                "date": date(2025, 12, 5),
                "first_accrual_date": date(2026, 1, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2026, 1, 31),
                "maturity": "26.01",
                "price": None,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "Yahoo Finance: No prices found.",
                "date": date(2025, 12, 5),
                "first_accrual_date": date(2026, 2, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2026, 2, 28),
                "maturity": "26.02",
                "price": None,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]

    @freeze_time("2025-12-06")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_yahoo_finance_closing_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_central_bank_next_meeting_date"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.requests.get"
    )
    def test_scheduled_stir_prices_ingestion_success_two_bdays_ago(
        self,
        mock_requests_get,
        mock_next_meeting,
        mock_yahoo_finance,
    ):
        """
        GIVEN valid STIR futures prices data from scraping
        WHEN scheduled_stir_prices_ingestion is called with two_bdays_ago=True
        THEN the task should successfully ingest prices for two business days ago
        """
        price_date = date(2025, 12, 4)  # Two business days before 2025-12-06
        mock_next_meeting.return_value = datetime(
            2026, 1, 15, 13, 0, tzinfo=timezone.utc
        )

        def yahoo_finance_side_effect(_, ticker):
            if ticker == "ZQH26.CBT":
                return {"price": 96.5, "comment": None}
            return {"price": None, "comment": "No price"}

        mock_yahoo_finance.side_effect = yahoo_finance_side_effect

        # Mock TFX requests (for BOJ futures) - use mock CSV data
        def requests_get_side_effect(url, **kwargs):
            if "tradingcalendar.html" in url:
                return MockResponse(
                    status_code=200, content=self.MOCK_MUTAN_REFERENCE_DATES_SUCCESS
                )
            else:
                return MockResponse(
                    status_code=200, content=self.MOCK_MUTAN_CSV_SUCCESS
                )

        mock_requests_get.side_effect = requests_get_side_effect

        # Verify no STIR futures prices exist before
        StirFuturesModel.objects.filter(date=price_date).count()

        result = tasks.scheduled_stir_prices_ingestion(two_bdays_ago=True)
        assert result == {
            "date": price_date.isoformat(),
            "message": "STIR Futures prices successfully ingested for 2025-12-04",
            "status": "success",
            "stir_futures_updated": [
                "FF1M.26.03",
                "MUTAN3M.25.09",
                "MUTAN3M.25.12",
                "MUTAN3M.26.03",
                "MUTAN3M.26.06",
                "MUTAN3M.26.09",
                "MUTAN3M.26.12",
                "MUTAN3M.27.03",
                "MUTAN3M.27.06",
                "MUTAN3M.27.09",
                "MUTAN3M.27.12",
                "MUTAN3M.28.03",
                "MUTAN3M.28.06",
                "MUTAN3M.28.09",
                "MUTAN3M.28.12",
                "MUTAN3M.29.03",
                "MUTAN3M.29.06",
                "MUTAN3M.29.09",
                "MUTAN3M.29.12",
                "MUTAN3M.30.03",
                "MUTAN3M.30.06",
            ],
        }
        stir_futures = parse_query_for_testing(
            StirFuturesModel.objects.all().order_by("maturity", "date")
        )
        assert stir_futures[:5] == [
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "comment": "",
                "date": date(2025, 12, 4),
                "first_accrual_date": date(2025, 9, 17),
                "full_name": "3 Month Mutan STIR Futures",
                "last_accrual_date": date(2025, 12, 16),
                "maturity": "25.09",
                "price": 99.52,
                "short_name": StirFuturesNameChoices.MUTAN3M.value,
                "source": StirFuturesSourceChoices.TFX.value,
            },
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "comment": "",
                "date": date(2025, 12, 4),
                "first_accrual_date": date(2025, 12, 17),
                "full_name": "3 Month Mutan STIR Futures",
                "last_accrual_date": date(2026, 3, 17),
                "maturity": "25.12",
                "price": 99.31,
                "short_name": StirFuturesNameChoices.MUTAN3M.value,
                "source": StirFuturesSourceChoices.TFX.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "Yahoo Finance: No prices found.",
                "date": date(2025, 12, 4),
                "first_accrual_date": date(2025, 12, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2025, 12, 31),
                "maturity": "25.12",
                "price": None,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "Yahoo Finance: No prices found.",
                "date": date(2025, 12, 4),
                "first_accrual_date": date(2026, 1, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2026, 1, 31),
                "maturity": "26.01",
                "price": None,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "Yahoo Finance: No prices found.",
                "date": date(2025, 12, 4),
                "first_accrual_date": date(2026, 2, 1),
                "full_name": "1 Month Fed Funds STIR Futures",
                "last_accrual_date": date(2026, 2, 28),
                "maturity": "26.02",
                "price": None,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]

    @freeze_time("2025-12-15")
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.get_yahoo_finance_closing_prices"
    )
    def test_scheduled_stir_prices_ingestion_error(self, mock_yahoo_finance):
        """
        GIVEN an error occurs during scraping
        WHEN scheduled_stir_prices_ingestion is called
        THEN the task should return an error status
        """
        price_date = date(2025, 12, 12)
        mock_yahoo_finance.side_effect = Exception("Network error")

        result = tasks.scheduled_stir_prices_ingestion(two_bdays_ago=False)
        assert result == {
            "date": price_date.isoformat(),
            "message": "Error: Network error",
            "status": "error",
        }


class TestScheduledStirFuturesPriceUpdateLogsCleanup(TestCase):
    """Test cases for scheduled_stir_futures_price_update_logs_cleanup task."""

    @freeze_time("2025-12-15")
    def test_scheduled_stir_futures_price_update_logs_cleanup_success_not_january(self):
        """
        GIVEN it's not January
        WHEN scheduled_stir_futures_price_update_logs_cleanup is called
        THEN the task should clean up logs from the previous month
        """
        logs_date = date(2025, 11, 1)  # Previous month
        # Create test logs before cutoff date
        stir_future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="2026-03",
            date=date(2025, 12, 15),
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )
        log_before = StirFuturesPriceUpdateLogModel.objects.create(
            stir_futures=stir_future,
            logs="Test log before cutoff",
        )
        log_before.date_added = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        log_before.save()

        log_after = StirFuturesPriceUpdateLogModel.objects.create(
            stir_futures=stir_future,
            logs="Test log after cutoff",
        )
        log_after.date_added = datetime(2025, 12, 1, 12, 0, 0, tzinfo=timezone.utc)
        log_after.save()

        # Verify logs exist before cleanup
        assert parse_query_for_testing(
            StirFuturesPriceUpdateLogModel.objects.all()
        ) == [
            {
                "stir_futures_id": stir_future.pk,
                "logs": "Test log after cutoff",
            },
            {
                "stir_futures_id": stir_future.pk,
                "logs": "Test log before cutoff",
            },
        ]

        result = tasks.scheduled_stir_futures_price_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Stir futures price update logs deleted successfully for 2025-11-01",
            "status": "success",
        }
        assert parse_query_for_testing(
            StirFuturesPriceUpdateLogModel.objects.all()
        ) == [
            {
                "stir_futures_id": stir_future.pk,
                "logs": "Test log after cutoff",
            }
        ]

    @freeze_time("2025-01-15")
    def test_scheduled_stir_futures_price_update_logs_cleanup_success_january(self):
        """
        GIVEN it's January
        WHEN scheduled_stir_futures_price_update_logs_cleanup is called
        THEN the task should clean up logs from December of the previous year
        """
        logs_date = date(2024, 12, 1)  # Previous year December
        # Create test logs before cutoff date
        stir_future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="2026-03",
            date=date(2025, 1, 15),
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )
        log_before = StirFuturesPriceUpdateLogModel.objects.create(
            stir_futures=stir_future,
            logs="Test log before cutoff",
        )
        log_before.date_added = datetime(2024, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        log_before.save()

        log_after = StirFuturesPriceUpdateLogModel.objects.create(
            stir_futures=stir_future,
            logs="Test log after cutoff",
        )
        log_after.date_added = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        log_after.save()

        # Verify logs exist before cleanup
        assert parse_query_for_testing(
            StirFuturesPriceUpdateLogModel.objects.all()
        ) == [
            {
                "stir_futures_id": stir_future.pk,
                "logs": "Test log after cutoff",
            },
            {
                "stir_futures_id": stir_future.pk,
                "logs": "Test log before cutoff",
            },
        ]

        result = tasks.scheduled_stir_futures_price_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Stir futures price update logs deleted successfully for 2024-12-01",
            "status": "success",
        }
        assert parse_query_for_testing(
            StirFuturesPriceUpdateLogModel.objects.all()
        ) == [
            {
                "stir_futures_id": stir_future.pk,
                "logs": "Test log after cutoff",
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "central_banks_overview.tasks.stir_futures_services.delete_stir_futures_price_update_logs_before_date"
    )
    def test_scheduled_stir_futures_price_update_logs_cleanup_error(self, mock_delete):
        """
        GIVEN an error occurs during log cleanup
        WHEN scheduled_stir_futures_price_update_logs_cleanup is called
        THEN the task should return an error status
        """
        logs_date = date(2025, 11, 1)
        mock_delete.side_effect = Exception("Database error")

        result = tasks.scheduled_stir_futures_price_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Error: Database error",
            "status": "error",
        }


class TestScheduledUpdateCbInfoAndStirFuturesPricesCleanupAfterMeetings(TestCase):
    """Test cases for scheduled update cb info and cleanup after meetings task."""

    def setUp(self):
        """Set up test fixtures."""
        self.past_meeting_date = datetime(2025, 12, 10, 13, 0, tzinfo=timezone.utc)
        self.future_meeting_date = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        # With freeze_time("2025-12-15"), price_date = 2025-12-15 - 7 days = 2025-12-08
        self.expected_price_date = date(2025, 12, 8)
        # date_to_ingest = (2025-12-15 - BDay(1)) = 2025-12-12 (Friday)
        self.expected_date_to_ingest = date(2025, 12, 12)

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _extract_fomc_meeting_dates.cache_clear()
        _extract_ecb_meeting_dates.cache_clear()
        _extract_boj_meeting_dates.cache_clear()

    @freeze_time("2025-12-15")
    @patch("central_banks_overview.services.cb_data_services.ingest_central_bank_data")
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    def test_scheduled_update_cb_info_cleanup_success(
        self,
        mock_extract_boj,
        mock_extract_ecb,
        mock_extract_fomc,
        mock_ingest_data,
    ):
        """
        GIVEN multiple central banks with past meeting dates
        WHEN the scheduled function is called
        THEN the task should clean up prices for all and update data
        """
        # Create meeting records: All central banks have past meetings
        CentralBankMeetingModel.objects.bulk_create(
            [
                CentralBankMeetingModel(
                    central_bank=CentralBankChoices.FRB,
                    order=1,
                    date=self.past_meeting_date,
                ),
                CentralBankMeetingModel(
                    central_bank=CentralBankChoices.ECB,
                    order=1,
                    date=self.past_meeting_date,
                ),
                CentralBankMeetingModel(
                    central_bank=CentralBankChoices.BOJ,
                    order=1,
                    date=self.past_meeting_date,
                ),
            ]
        )

        # Create prices for each central bank
        StirFuturesModel.objects.bulk_create(
            [
                StirFuturesModel(
                    central_bank=CentralBankChoices.FRB,
                    short_name=StirFuturesNameChoices.FF1M,
                    maturity="26.03",
                    date=date(2025, 12, 5),  # Before cutoff
                    price=96.5,
                    source=StirFuturesSourceChoices.YAHOO,
                ),
                StirFuturesModel(
                    central_bank=CentralBankChoices.ECB,
                    short_name=StirFuturesNameChoices.ESTR3M,
                    maturity="26.03",
                    date=date(2025, 12, 5),  # Before cutoff
                    price=96.5,
                    source=StirFuturesSourceChoices.PDF,
                ),
                StirFuturesModel(
                    central_bank=CentralBankChoices.BOJ,
                    short_name=StirFuturesNameChoices.MUTAN3M,
                    maturity="26.03",
                    date=date(2025, 12, 5),  # Before cutoff
                    price=96.5,
                    source=StirFuturesSourceChoices.TFX,
                ),
                StirFuturesModel(
                    central_bank=CentralBankChoices.FRB,
                    short_name=StirFuturesNameChoices.FF1M,
                    maturity="26.04",
                    date=date(2025, 12, 10),  # After cutoff - should be kept
                    price=96.6,
                    source=StirFuturesSourceChoices.YAHOO,
                ),
            ]
        )

        mock_ingest_data.return_value = []
        mock_extract_fomc.return_value = []
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        # Verify initial state
        assert StirFuturesModel.objects.count() == 4
        assert CentralBankMeetingModel.objects.count() == 3

        result = (
            tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings()
        )
        assert result == {
            "status": "success",
            "message": "Central bank meetings updated successfully for ['FRB - 2025-12-08', 'BOJ - 2025-12-08', 'ECB - 2025-12-08']",
        }

        # Verify only the price after cutoff remains
        remaining_prices = StirFuturesModel.objects.all()
        assert remaining_prices.count() == 1
        assert parse_query_for_testing(remaining_prices) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2025, 12, 10),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.04",
                "price": 96.6,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]
        # No meeting records should be left as meeting of 2025-12-10 is past
        # and mocked extract functions return empty lists
        assert parse_query_for_testing(CentralBankMeetingModel.objects.all()) == []
        assert mock_ingest_data.call_count == 3

    @freeze_time("2025-12-15")
    @patch("central_banks_overview.services.cb_data_services.ingest_central_bank_data")
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @patch("market_overview.services.price_ingestion_services.get_webstat_rates")
    @patch("market_overview.services.price_ingestion_services.scrap_from_global_rates")
    def test_scheduled_update_cb_info_cleanup_success_mixed_scenario(
        self,
        mock_scrap_global_rates,
        mock_get_webstat_rates,
        mock_extract_boj_meeting_dates,
        mock_extract_ecb_meeting_dates,
        mock_extract_fomc_meeting_dates,
        mock_ingest_data,
    ):
        """
        GIVEN a mix of past meetings, future meetings, and None
        WHEN the scheduled function is called
        THEN the task should only clean up prices for central banks with past meetings
        """
        # Create meeting records
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=self.past_meeting_date,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=self.future_meeting_date,
        )

        # Create prices for FRB (should be deleted)
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="26.03",
            date=date(2025, 12, 5),  # Before cutoff
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )
        # Create prices for ECB (should NOT be deleted - no past meeting)
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            maturity="26.03",
            date=date(2025, 12, 5),  # Before cutoff
            price=96.5,
            source=StirFuturesSourceChoices.PDF,
        )

        # Mock scraping functions
        mock_get_webstat_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        mock_scrap_global_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        # Mock data ingestion to succeed so we can test the main flow
        mock_ingest_data.return_value = []
        # Mock extraction functions - FRB has past meeting, ECB has future meeting
        # Note: ECB extraction adds default time (13:15 UTC), so we need to match that
        ecb_future_meeting = datetime(2026, 1, 15, 13, 15, tzinfo=timezone.utc)
        mock_extract_fomc_meeting_dates.return_value = [self.past_meeting_date]
        mock_extract_ecb_meeting_dates.return_value = [ecb_future_meeting]
        mock_extract_boj_meeting_dates.return_value = []

        # Verify initial state
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.ESTR3M.value,
                "source": StirFuturesSourceChoices.PDF.value,
            },
        ]
        assert parse_query_for_testing(CentralBankMeetingModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "date": "2025-12-10 13:00:00+0000",
                "order": 1,
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "date": "2026-01-15 13:00:00+0000",
                "order": 1,
            },
        ]

        result = (
            tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings()
        )
        # ECB should not be updated as it has a future meeting
        assert result == {
            "status": "success",
            "message": "Central bank meetings updated successfully for ['FRB - 2025-12-08']",
        }
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.ESTR3M.value,
                "source": StirFuturesSourceChoices.PDF.value,
            },
        ]
        assert parse_query_for_testing(CentralBankMeetingModel.objects.all()) == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "date": "2026-01-15 13:00:00+0000",
                "order": 1,
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @patch("market_overview.services.price_ingestion_services.get_webstat_rates")
    @patch("market_overview.services.price_ingestion_services.scrap_from_global_rates")
    def test_scheduled_update_cb_info_cleanup_no_past_meetings_all_future(
        self,
        mock_scrap_global_rates,
        mock_get_webstat_rates,
        mock_extract_boj_meeting_dates,
        mock_extract_ecb_meeting_dates,
        mock_extract_fomc_meeting_dates,
    ):
        """
        GIVEN all central banks have future meeting dates
        WHEN the scheduled function is called
        THEN the task should skip cleanup and return success
        """
        # Create meeting records: All have future meetings
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=self.future_meeting_date,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=self.future_meeting_date,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            order=1,
            date=self.future_meeting_date,
        )

        # Create prices (should NOT be deleted - no past meetings)
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="26.03",
            date=date(2025, 12, 5),  # Before cutoff
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )

        # Mock scraping functions
        mock_get_webstat_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        mock_scrap_global_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        # Mock extraction functions - all return future meetings
        mock_extract_fomc_meeting_dates.return_value = [self.future_meeting_date]
        mock_extract_ecb_meeting_dates.return_value = [self.future_meeting_date]
        mock_extract_boj_meeting_dates.return_value = [self.future_meeting_date]

        # Verify initial state - prices and meetings exist
        initial_prices = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]
        initial_meetings = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "date": "2026-01-15 13:00:00+0000",
                "order": 1,
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "date": "2026-01-15 13:00:00+0000",
                "order": 1,
            },
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "date": "2026-01-15 13:00:00+0000",
                "order": 1,
            },
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == initial_prices
        assert (
            parse_query_for_testing(CentralBankMeetingModel.objects.all())
            == initial_meetings
        )

        result = (
            tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings()
        )
        assert result == {
            "status": "success",
            "message": "No central bank meetings to update",
        }
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == initial_prices
        assert (
            parse_query_for_testing(CentralBankMeetingModel.objects.all())
            == initial_meetings
        )

    @freeze_time("2025-12-15")
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @patch("market_overview.services.price_ingestion_services.get_webstat_rates")
    @patch("market_overview.services.price_ingestion_services.scrap_from_global_rates")
    def test_scheduled_update_cb_info_cleanup_no_past_meetings_all_none(
        self,
        mock_scrap_global_rates,
        mock_get_webstat_rates,
        mock_extract_boj_meeting_dates,
        mock_extract_ecb_meeting_dates,
        mock_extract_fomc_meeting_dates,
    ):
        """
        GIVEN all central banks have no meeting dates
        WHEN the scheduled function is called
        THEN the task should skip cleanup and return success
        """
        # No meeting records created
        # Create prices (should NOT be deleted - no meetings)
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="26.03",
            date=date(2025, 12, 5),  # Before cutoff
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )

        # Mock scraping functions
        mock_get_webstat_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        mock_scrap_global_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        # Mock extraction functions - all return empty lists (no meetings)
        mock_extract_fomc_meeting_dates.return_value = []
        mock_extract_ecb_meeting_dates.return_value = []
        mock_extract_boj_meeting_dates.return_value = []

        initial_prices = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == initial_prices
        assert CentralBankMeetingModel.objects.all().count() == 0

        result = (
            tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings()
        )
        assert result == {
            "status": "success",
            "message": "No central bank meetings to update",
        }
        assert CentralBankMeetingModel.objects.all().count() == 0
        # Verify price was NOT deleted (no meetings)
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == initial_prices

    @freeze_time("2025-12-15")
    @patch("central_banks_overview.services.cb_data_services.ingest_central_bank_data")
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @patch("market_overview.services.price_ingestion_services.get_webstat_rates")
    @patch("market_overview.services.price_ingestion_services.scrap_from_global_rates")
    def test_scheduled_update_cb_info_cleanup_error_during_data_ingestion(
        self,
        mock_scrap_global_rates,
        mock_get_webstat_rates,
        mock_extract_boj_meeting_dates,
        mock_extract_ecb_meeting_dates,
        mock_extract_fomc_meeting_dates,
        mock_ingest_data,
    ):
        """
        GIVEN an error occurs during data ingestion
        WHEN the scheduled function is called
        THEN the task should return an error status
        """
        # Create meeting record: FRB has past meeting
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=self.past_meeting_date,
        )

        # Create price to be deleted
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="26.03",
            date=date(2025, 12, 5),  # Before cutoff
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )

        # Mock scraping functions
        mock_get_webstat_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        mock_scrap_global_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        # Mock extraction functions - return empty lists
        mock_extract_fomc_meeting_dates.return_value = []
        mock_extract_ecb_meeting_dates.return_value = []
        mock_extract_boj_meeting_dates.return_value = []
        # Mock ingestion to raise an error
        mock_ingest_data.side_effect = Exception("Ingestion error")

        initial_prices = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == initial_prices

        result = (
            tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings()
        )

        assert result == {
            "status": "error",
            "message": "Error: Ingestion error",
        }
        # Verify price was still deleted (cleanup happens before data ingestion)
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == []

    @freeze_time("2025-12-15")
    @patch(
        "central_banks_overview.services.cb_meetings_services.ingest_central_bank_meeting_dates"
    )
    @patch("central_banks_overview.services.cb_data_services.ingest_central_bank_data")
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @patch("market_overview.services.price_ingestion_services.get_webstat_rates")
    @patch("market_overview.services.price_ingestion_services.scrap_from_global_rates")
    def test_scheduled_update_cb_info_cleanup_error_during_meetings_ingestion(
        self,
        mock_scrap_global_rates,
        mock_get_webstat_rates,
        mock_extract_boj_meeting_dates,
        mock_extract_ecb_meeting_dates,
        mock_extract_fomc_meeting_dates,
        mock_ingest_data,
        mock_ingest_meetings,
    ):
        """
        GIVEN an error occurs during meetings ingestion
        WHEN the scheduled function is called
        THEN the task should return an error status
        """
        # Create meeting record: FRB has past meeting
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=self.past_meeting_date,
        )

        # Create price to be deleted
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            maturity="26.03",
            date=date(2025, 12, 5),  # Before cutoff
            price=96.5,
            source=StirFuturesSourceChoices.YAHOO,
        )

        # Mock scraping functions
        mock_get_webstat_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        mock_scrap_global_rates.return_value = ScrapingResult(
            price=None, comment="No data"
        )
        # Mock extraction functions - return empty lists
        mock_extract_fomc_meeting_dates.return_value = []
        mock_extract_ecb_meeting_dates.return_value = []
        mock_extract_boj_meeting_dates.return_value = []
        # Mock data ingestion to succeed (so we can test meetings ingestion error)
        mock_ingest_data.return_value = []
        # Mock meetings ingestion to raise an error
        mock_ingest_meetings.side_effect = Exception("Meetings ingestion error")

        initial_prices = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "comment": "",
                "date": date(2025, 12, 5),
                "first_accrual_date": None,
                "full_name": "",
                "last_accrual_date": None,
                "maturity": "26.03",
                "price": 96.5,
                "short_name": StirFuturesNameChoices.FF1M.value,
                "source": StirFuturesSourceChoices.YAHOO.value,
            },
        ]
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == initial_prices

        result = (
            tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings()
        )

        assert result == {
            "status": "error",
            "message": "Error: Meetings ingestion error",
        }
        # Verify price was still deleted (cleanup happens before meetings ingestion)
        assert parse_query_for_testing(StirFuturesModel.objects.all()) == []
