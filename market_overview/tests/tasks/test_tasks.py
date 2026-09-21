from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

import market_overview.tasks as tasks
from core.tests import MockResponse, parse_query_for_testing
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    HolidayModel,
    MarketPriceModel,
    PriceSourceChoices,
    PriceUpdateLogModel,
)


def _mock_ingestion_lock():
    lock = MagicMock()
    lock.release = MagicMock()
    return lock


class TestScheduledMarketDataIngestion(TestCase):
    """Test cases for scheduled_market_data_ingestion task."""

    @freeze_time("2025-12-15")
    @patch(
        "market_overview.tasks.try_acquire_redis_lock",
        return_value=_mock_ingestion_lock(),
    )
    @patch(
        "market_overview.services.price_ingestion_services.get_yahoo_finance_closing_prices"
    )
    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_scheduled_market_data_ingestion_success_one_bday_ago(
        self, mock_requests_get, mock_yahoo_finance, _mock_lock
    ):
        """
        GIVEN valid market data from scraping
        WHEN scheduled_market_data_ingestion is called with two_bdays_ago=False
        THEN the task should successfully ingest data for one business day ago
        """
        AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            source=PriceSourceChoices.YAHOO,
        )
        price_date = date(2025, 12, 12)  # One business day before 2025-12-15
        # Mock Yahoo Finance scraping
        mock_yahoo_finance.return_value = {"price": 100.0, "comment": None}
        # Mock other scraping sources (NYFED, Treasury, etc.)
        mock_response = MockResponse(status_code=200, text="<xml>test</xml>")
        mock_requests_get.return_value = mock_response

        # Verify no prices exist before
        assert MarketPriceModel.objects.filter(date=price_date).count() == 0

        result = tasks.scheduled_market_data_ingestion(two_bdays_ago=False)
        assert result == {
            "asset_not_updated": [],
            "asset_not_updated_holiday": [],
            "date": "2025-12-12",
            "message": "Market data ingested successfully for 2025-12-12",
            "status": "success",
        }
        assert parse_query_for_testing(MarketPriceModel.objects.all()) == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "date": price_date,
                "comment": None,
                "price": 100.0,
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "market_overview.tasks.try_acquire_redis_lock",
        return_value=_mock_ingestion_lock(),
    )
    @patch(
        "market_overview.services.price_ingestion_services.get_yahoo_finance_closing_prices"
    )
    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_scheduled_market_data_ingestion_success_one_bday_ago_no_scrapping_function(
        self, mock_requests_get, mock_yahoo_finance, _mock_lock
    ):
        """
        GIVEN valid market data from scraping
        WHEN scheduled_market_data_ingestion is called with two_bdays_ago=False
        THEN the task should successfully ingest data for one business day ago
        """
        AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        price_date = date(2025, 12, 12)  # One business day before 2025-12-15
        # Mock Yahoo Finance scraping
        mock_yahoo_finance.return_value = {"price": 100.0, "comment": None}
        # Mock other scraping sources (NYFED, Treasury, etc.)
        mock_response = MockResponse(status_code=200, text="<xml>test</xml>")
        mock_requests_get.return_value = mock_response

        # Verify no prices exist before
        assert MarketPriceModel.objects.filter(date=price_date).count() == 0

        result = tasks.scheduled_market_data_ingestion(two_bdays_ago=False)
        assert result == {
            "asset_not_updated": [
                "TEST",
            ],
            "asset_not_updated_holiday": [],
            "date": "2025-12-12",
            "message": "Market data ingested successfully for 2025-12-12",
            "status": "success",
        }
        assert parse_query_for_testing(MarketPriceModel.objects.all()) == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "date": price_date,
                "comment": "No scraping function found.",
                "price": None,
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "market_overview.tasks.try_acquire_redis_lock",
        return_value=_mock_ingestion_lock(),
    )
    @patch(
        "market_overview.services.price_ingestion_services.get_yahoo_finance_closing_prices"
    )
    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_scheduled_market_data_ingestion_success_two_bdays_ago(
        self, mock_requests_get, mock_yahoo_finance, _mock_lock
    ):
        """
        GIVEN valid market data from scraping
        WHEN scheduled_market_data_ingestion is called with two_bdays_ago=True
        THEN the task should successfully ingest data for two business days ago
        """
        AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            source=PriceSourceChoices.YAHOO,
        )
        price_date = date(2025, 12, 11)  # Two business days before 2025-12-15
        # Mock Yahoo Finance scraping
        mock_yahoo_finance.return_value = {"price": 100.0, "comment": None}
        # Mock other scraping sources
        mock_response = MockResponse(status_code=200, text="<xml>test</xml>")
        mock_requests_get.return_value = mock_response

        # Verify no prices exist before
        assert MarketPriceModel.objects.filter(date=price_date).count() == 0

        result = tasks.scheduled_market_data_ingestion(two_bdays_ago=True)
        assert result == {
            "asset_not_updated": [],
            "asset_not_updated_holiday": [],
            "date": "2025-12-11",
            "message": "Market data ingested successfully for 2025-12-11",
            "status": "success",
        }
        assert parse_query_for_testing(MarketPriceModel.objects.all()) == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "date": price_date,
                "comment": None,
                "price": 100.0,
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "market_overview.tasks.try_acquire_redis_lock",
        return_value=_mock_ingestion_lock(),
    )
    @patch("market_overview.services.price_ingestion_services.get_market_data")
    def test_scheduled_market_data_ingestion_error(
        self, mock_get_market_data, _mock_lock
    ):
        """
        GIVEN an error occurs during scraping
        WHEN scheduled_market_data_ingestion is called
        THEN the task should return an error status
        """
        price_date = date(2025, 12, 12)
        mock_get_market_data.side_effect = Exception("Network error")

        result = tasks.scheduled_market_data_ingestion(two_bdays_ago=False)
        assert result == {
            "status": "error",
            "message": "Error: Network error",
            "date": price_date.isoformat(),
        }

    @freeze_time("2025-12-15")
    @patch(
        "market_overview.tasks.try_acquire_redis_lock",
        return_value=None,
    )
    def test_scheduled_market_data_ingestion_skipped_when_locked(self, _mock_lock):
        """
        GIVEN another ingestion already holds the Redis lock for the date
        WHEN scheduled_market_data_ingestion is called
        THEN the task should skip without scraping
        """
        result = tasks.scheduled_market_data_ingestion(two_bdays_ago=False)
        assert result == {
            "status": "skipped",
            "message": "Market data ingestion already in progress for 2025-12-12",
            "date": "2025-12-12",
        }


class TestScheduledPriceUpdateLogsCleanup(TestCase):
    """Test cases for scheduled_price_update_logs_cleanup task."""

    @freeze_time("2025-12-15")
    def test_scheduled_price_update_logs_cleanup_success_not_january(self):
        """
        GIVEN it's not January
        WHEN scheduled_price_update_logs_cleanup is called
        THEN the task should clean up logs from the previous month
        """
        logs_date = date(2025, 11, 1)  # Previous month
        # Create test logs before cutoff date
        asset = AssetModel.objects.create(
            short_name="TEST_ASSET",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        market_price = MarketPriceModel.objects.create(
            asset=asset,
            date=date(2025, 12, 15),
            price=100.0,
        )
        log_before = PriceUpdateLogModel.objects.create(
            market_price=market_price,
            logs="Test log before cutoff",
        )
        log_before.date_added = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        log_before.save()

        log_after = PriceUpdateLogModel.objects.create(
            market_price=market_price,
            logs="Test log after cutoff",
        )
        log_after.date_added = datetime(2025, 12, 1, 12, 0, 0, tzinfo=timezone.utc)
        log_after.save()

        # Verify logs exist before cleanup
        assert parse_query_for_testing(PriceUpdateLogModel.objects.all()) == [
            {
                "market_price_id": market_price.pk,
                "logs": "Test log after cutoff",
            },
            {
                "market_price_id": market_price.pk,
                "logs": "Test log before cutoff",
            },
        ]

        result = tasks.scheduled_price_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Price update logs deleted successfully for 2025-11-01",
            "status": "success",
        }
        assert parse_query_for_testing(PriceUpdateLogModel.objects.all()) == [
            {
                "market_price_id": market_price.pk,
                "logs": "Test log after cutoff",
            }
        ]

    @freeze_time("2025-01-15")
    def test_scheduled_price_update_logs_cleanup_success_january(self):
        """
        GIVEN it's January
        WHEN scheduled_price_update_logs_cleanup is called
        THEN the task should clean up logs from December of the previous year
        """
        logs_date = date(2024, 12, 1)  # December of previous year
        # Create test logs before cutoff date
        asset = AssetModel.objects.create(
            short_name="TEST_ASSET",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        market_price = MarketPriceModel.objects.create(
            asset=asset,
            date=date(2025, 1, 15),
            price=100.0,
        )
        log_before = PriceUpdateLogModel.objects.create(
            market_price=market_price,
            logs="Test log before cutoff",
        )
        log_before.date_added = datetime(2024, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        log_before.save()

        log_after = PriceUpdateLogModel.objects.create(
            market_price=market_price,
            logs="Test log after cutoff",
        )
        log_after.date_added = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        log_after.save()

        # Verify logs exist before cleanup
        assert parse_query_for_testing(PriceUpdateLogModel.objects.all()) == [
            {
                "market_price_id": market_price.pk,
                "logs": "Test log after cutoff",
            },
            {
                "market_price_id": market_price.pk,
                "logs": "Test log before cutoff",
            },
        ]

        result = tasks.scheduled_price_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Price update logs deleted successfully for 2024-12-01",
            "status": "success",
        }
        assert parse_query_for_testing(PriceUpdateLogModel.objects.all()) == [
            {
                "market_price_id": market_price.pk,
                "logs": "Test log after cutoff",
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "market_overview.tasks.market_data_services.delete_price_update_logs_before_date"
    )
    def test_scheduled_price_update_logs_cleanup_error(self, mock_delete):
        """
        GIVEN an error occurs during log cleanup
        WHEN scheduled_price_update_logs_cleanup is called
        THEN the task should return an error status
        """
        logs_date = date(2025, 11, 1)
        mock_delete.side_effect = Exception("Database error")

        result = tasks.scheduled_price_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Error: Database error",
            "status": "error",
        }


class TestScheduledHolidaysIngestion(TestCase):
    """Test cases for scheduled_holidays_ingestion task."""

    @freeze_time("2025-12-15")
    @patch("market_overview.services.holiday_services.requests.get")
    def test_scheduled_holidays_ingestion_success(self, mock_requests_get):
        """
        GIVEN valid holiday data from scraping
        WHEN scheduled_holidays_ingestion is called
        THEN the task should successfully ingest holidays and delete old ones
        """
        # Create holidays before cutoff date
        # before_date = 2025-12-15 - 30 days = 2025-11-15
        HolidayModel.objects.create(
            date=date(2025, 11, 1),
            name="Old Holiday",
            location="US",
        )
        HolidayModel.objects.create(
            date=date(2025, 11, 10),
            name="Another Old Holiday",
            location="FR",
        )

        # Create holidays after cutoff date (should not be deleted)
        HolidayModel.objects.create(
            date=date(2025, 11, 20),
            name="Recent Holiday",
            location="US",
        )

        # Mock holiday API responses with actual holiday data
        mock_response = MockResponse(
            status_code=200,
            json_data=[
                {
                    "date": "2025-12-25",
                    "localName": "Christmas Day",
                    "countryCode": "US",
                },
                {
                    "date": "2026-01-01",
                    "localName": "New Year's Day",
                    "countryCode": "US",
                },
            ],
        )
        mock_requests_get.return_value = mock_response

        result = tasks.scheduled_holidays_ingestion()
        assert result == {
            "status": "success",
            "message": "Holidays successfully ingested.",
        }
        # Verify new holidays were ingested
        holidays = parse_query_for_testing(HolidayModel.objects.all())
        assert holidays == [
            {
                "date": date(2025, 11, 20),
                "name": "Recent Holiday",
                "location": "US",
            },
            {
                "date": date(2025, 12, 25),
                "name": "Christmas Day",
                "location": "US",
            },
            {
                "date": date(2026, 1, 1),
                "name": "New Year's Day",
                "location": "US",
            },
        ]

    @freeze_time("2025-12-15")
    @patch("market_overview.services.holiday_services.requests.get")
    def test_scheduled_holidays_ingestion_error(self, mock_requests_get):
        """
        GIVEN an error occurs during holidays scraping
        WHEN scheduled_holidays_ingestion is called
        THEN the task should return an error status
        """
        mock_requests_get.side_effect = Exception("API error")

        result = tasks.scheduled_holidays_ingestion()

        assert result["status"] == "error"
        assert "Error: API error" in result["message"]
