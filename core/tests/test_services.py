"""Tests for shared core service helpers."""

from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests
from bs4 import BeautifulSoup
from django.db import IntegrityError
from django.test import TestCase
from freezegun import freeze_time
from rest_framework.exceptions import NotFound

from core.conftest import parse_query_for_testing
from core.services import (
    ValueChange,
    calculate_value_change,
    convert_local_wall_time_to_utc,
    convert_query_to_dictionary_list,
    convert_to_display_timezone,
    fetch_html,
    get,
    get_source_timezone,
    parse_datetime,
    update_with_logs,
    upsert_with_logs,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    MarketPriceModel,
    PriceUpdateLogModel,
)

FREEZE_TIME = datetime(2025, 12, 15, 0, 0, 0, tzinfo=timezone.utc)


class TestGet(TestCase):
    """Test cases for get function."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

    def test_get_success(self):
        """
        GIVEN an existing model instance
        WHEN get is called with valid lookup parameters
        THEN the instance should be returned
        """
        result = get(AssetModel, short_name="TEST")

        assert result == self.asset
        assert result.short_name == "TEST"

    def test_get_not_found(self):
        """
        GIVEN a non-existent model instance
        WHEN get is called with invalid lookup parameters
        THEN a NotFound exception should be raised
        """
        with pytest.raises(NotFound) as exc_info:
            get(AssetModel, short_name="NONEXISTENT")

        assert "No AssetModel found matching" in str(exc_info.value.detail)
        assert "NONEXISTENT" in str(exc_info.value.detail)


class TestUpdateWithLogs(TestCase):
    """Test cases for update_with_logs function."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.market_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date="2025-12-15",
            price=100.0,
        )

    def test_update_with_logs_success_with_changes(self):
        """
        GIVEN a model instance with updates
        WHEN update_with_logs is called with logging_on_fields
        THEN the model should be updated and a log entry should be created
        """
        PriceUpdateLogModel.fk_name = "market_price"
        updates = {"price": 150.0, "logs": "Initial log."}
        logging_on_fields = ["price"]

        result = update_with_logs(
            model_to_update=self.market_price,
            log_model=PriceUpdateLogModel,
            updates=updates,
            logging_on_fields=logging_on_fields,
            none_skip_fields=[],
            enable_none_updates=True,
        )

        assert result.price == 150.0
        result = PriceUpdateLogModel.objects.all()
        assert parse_query_for_testing(result) == [
            {
                "market_price_id": self.market_price.pk,
                "logs": "Initial log. Updated price from 100.0 to 150.0.",
            }
        ]

    def test_update_with_logs_no_changes(self):
        """
        GIVEN a model instance with no actual changes
        WHEN update_with_logs is called
        THEN the model should not be updated and no log should be created
        """
        PriceUpdateLogModel.fk_name = "market_price"
        updates = {"price": 100.0, "logs": "No change log"}
        logging_on_fields = ["price"]

        result = update_with_logs(
            model_to_update=self.market_price,
            log_model=PriceUpdateLogModel,
            updates=updates,
            logging_on_fields=logging_on_fields,
            none_skip_fields=[],
            enable_none_updates=True,
        )

        assert result.price == 100.0
        assert PriceUpdateLogModel.objects.count() == 0

    def test_update_with_logs_none_skip_fields(self):
        """
        GIVEN a model instance with none_skip_fields
        WHEN update_with_logs is called with None value for a skip field
        THEN the update should be skipped if existing value is not None
        """
        PriceUpdateLogModel.fk_name = "market_price"
        self.market_price.price = 100.0
        self.market_price.save()
        updates = {"price": None, "logs": "Skip log"}
        none_skip_fields = ["price"]

        result = update_with_logs(
            model_to_update=self.market_price,
            log_model=PriceUpdateLogModel,
            updates=updates,
            logging_on_fields=[],
            none_skip_fields=none_skip_fields,
            enable_none_updates=False,
        )

        assert result.price == 100.0  # Should remain unchanged
        assert PriceUpdateLogModel.objects.count() == 0

    def test_update_with_logs_enable_none_updates(self):
        """
        GIVEN a model instance with enable_none_updates=True
        WHEN update_with_logs is called with None value
        THEN the update should be applied
        """
        PriceUpdateLogModel.fk_name = "market_price"
        updates = {"price": None, "logs": "None update log."}
        logging_on_fields = ["price"]

        result = update_with_logs(
            model_to_update=self.market_price,
            log_model=PriceUpdateLogModel,
            updates=updates,
            logging_on_fields=logging_on_fields,
            none_skip_fields=[],
            enable_none_updates=True,
        )

        assert result.price is None
        result = PriceUpdateLogModel.objects.all()
        assert parse_query_for_testing(result) == [
            {
                "market_price_id": self.market_price.pk,
                "logs": "None update log. Updated price from 100.0 to None.",
            }
        ]

    def test_update_with_logs_missing_required_parameters(self):
        """
        GIVEN update_with_logs is called without required parameters
        WHEN neither none_skip_fields nor enable_none_updates is provided
        THEN a ValueError should be raised
        """
        updates = {"price": 150.0}

        with pytest.raises(ValueError) as exc_info:
            update_with_logs(
                model_to_update=self.market_price,
                log_model=PriceUpdateLogModel,
                updates=updates,
                logging_on_fields=[],
                none_skip_fields=[],
                enable_none_updates=False,
            )

        assert "Need to specify fields to skip or enable none updates" in str(
            exc_info.value
        )

    def test_update_with_logs_invalid_skip_fields(self):
        """
        GIVEN update_with_logs is called with invalid skip fields
        WHEN none_skip_fields contains fields not in the model
        THEN a ValueError should be raised
        """
        updates = {"price": 150.0}
        none_skip_fields = ["invalid_field"]

        with pytest.raises(ValueError) as exc_info:
            update_with_logs(
                model_to_update=self.market_price,
                log_model=PriceUpdateLogModel,
                updates=updates,
                logging_on_fields=[],
                none_skip_fields=none_skip_fields,
                enable_none_updates=False,
            )

        assert "Fields to skip must be in model" in str(exc_info.value)


class TestUpsertWithLogs(TestCase):
    """Test cases for upsert_with_logs function."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.market_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date="2025-12-15",
            price=100.0,
        )

    def test_upsert_with_logs_update_existing(self):
        """
        GIVEN an existing model instance
        WHEN upsert_with_logs is called with matching lookup_kwargs
        THEN the instance should be updated with logs
        """
        PriceUpdateLogModel.fk_name = "market_price"
        lookup_kwargs = {
            "asset": self.asset,
            "date": date(2025, 12, 15),
        }
        updates = {"price": 150.0, "logs": "Update log."}
        logging_on_fields = ["price"]

        result = upsert_with_logs(
            model=MarketPriceModel,
            log_model=PriceUpdateLogModel,
            lookup_kwargs=lookup_kwargs,
            updates=updates,
            logging_on_fields=logging_on_fields,
            none_skip_fields=[],
            enable_none_updates=True,
        )

        assert result.price == 150.0
        result = PriceUpdateLogModel.objects.all()
        assert parse_query_for_testing(result) == [
            {
                "market_price_id": self.market_price.pk,
                "logs": "Update log. Updated price from 100.0 to 150.0.",
            }
        ]

    def test_upsert_with_logs_create_new(self):
        """
        GIVEN a non-existent model instance
        WHEN upsert_with_logs is called with non-matching lookup_kwargs
        THEN a new instance should be created
        """
        lookup_kwargs = {
            "asset": self.asset,
            "date": date(2025, 12, 16),
        }
        updates = {"price": 200.0, "logs": "Create log."}

        previous_price_in_db = {
            "asset_id": 1,
            "asset_short_name": "TEST",
            "comment": "",
            "date": date(2025, 12, 15),
            "price": 100.0,
        }
        result = MarketPriceModel.objects.all()
        assert parse_query_for_testing(result) == [previous_price_in_db]

        result = upsert_with_logs(
            model=MarketPriceModel,
            log_model=PriceUpdateLogModel,
            lookup_kwargs=lookup_kwargs,
            updates=updates,
            logging_on_fields=[],
            none_skip_fields=[],
            enable_none_updates=True,
        )
        new_price_in_db = {
            "asset_id": 1,
            "asset_short_name": "TEST",
            "comment": "",
            "date": date(2025, 12, 16),
            "price": 200.0,
        }
        result = MarketPriceModel.objects.all()
        assert parse_query_for_testing(result) == [
            previous_price_in_db,
            new_price_in_db,
        ]
        # No log should be created for new instances
        assert PriceUpdateLogModel.objects.count() == 0

    @patch.object(MarketPriceModel.objects, "create")
    @patch.object(MarketPriceModel.objects, "get")
    def test_upsert_with_logs_cancels_after_integrity_error(
        self, mock_get, mock_create
    ):
        """
        GIVEN a concurrent create already inserted the row
        WHEN upsert_with_logs hits IntegrityError on create
        THEN it should return the existing row without updating it
        """
        lookup_kwargs = {
            "asset": self.asset,
            "date": date(2025, 12, 16),
        }
        updates = {"price": 200.0, "logs": "Raced create."}
        # Avoid MarketPriceModel.objects.create — it is patched on this test.
        raced = MarketPriceModel(
            asset=self.asset,
            date=date(2025, 12, 16),
            price=150.0,
        )
        raced.save()
        mock_get.side_effect = [
            MarketPriceModel.DoesNotExist,
            raced,
        ]
        mock_create.side_effect = IntegrityError("unique_market_price_per_asset_date")

        result = upsert_with_logs(
            model=MarketPriceModel,
            log_model=PriceUpdateLogModel,
            lookup_kwargs=lookup_kwargs,
            updates=updates,
            logging_on_fields=["price"],
            none_skip_fields=[],
            enable_none_updates=True,
        )

        assert result.pk == raced.pk
        raced.refresh_from_db()
        assert raced.price == 150.0
        assert PriceUpdateLogModel.objects.count() == 0


@freeze_time(FREEZE_TIME)
class TestConvertQueryToDictionaryList(TestCase):
    """Test cases for convert_query_to_dictionary_list function."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.asset2 = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

    def test_convert_query_to_dictionary_list_default(self):
        """
        GIVEN a QuerySet
        WHEN convert_query_to_dictionary_list is called with default parameters
        THEN a list of dictionaries should be returned with auto fields removed
        """
        queryset = AssetModel.objects.all()
        result = convert_query_to_dictionary_list(queryset)
        assert result == [
            {
                "asset_class": "STOCKS",
                "asset_id": 1,
                "asset_type": "EQUITY_INDEX",
                "full_name": "Test Asset",
                "location": None,
                "maturity": None,
                "short_name": "TEST",
                "source": "",
                "ticker": "",
            },
            {
                "asset_class": "STOCKS",
                "asset_id": 2,
                "asset_type": "EQUITY_INDEX",
                "full_name": "Test Asset 2",
                "location": None,
                "maturity": None,
                "short_name": "TEST2",
                "source": "",
                "ticker": "",
            },
        ]

    def test_convert_query_to_dictionary_list_keep_auto_fields(self):
        """
        GIVEN a QuerySet
        WHEN convert_query_to_dictionary_list is called with remove_auto_fields=False
        THEN auto fields should be included in the result
        """
        queryset = AssetModel.objects.all()
        result = convert_query_to_dictionary_list(queryset, remove_auto_fields=False)

        assert result == [
            {
                "asset_class": "STOCKS",
                "asset_id": 1,
                "asset_type": "EQUITY_INDEX",
                "full_name": "Test Asset",
                "location": None,
                "maturity": None,
                "short_name": "TEST",
                "source": "",
                "ticker": "",
                "date_added": FREEZE_TIME,
                "last_modified": FREEZE_TIME,
            },
            {
                "asset_class": "STOCKS",
                "asset_id": 2,
                "asset_type": "EQUITY_INDEX",
                "full_name": "Test Asset 2",
                "location": None,
                "maturity": None,
                "short_name": "TEST2",
                "source": "",
                "ticker": "",
                "date_added": FREEZE_TIME,
                "last_modified": FREEZE_TIME,
            },
        ]

    def test_convert_query_to_dictionary_list_remove_foreign_key(self):
        """
        GIVEN a QuerySet with foreign key relationships
        WHEN convert_query_to_dictionary_list is called with remove_foreign_key=True
        THEN foreign key ID fields should be removed
        """
        market_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date="2025-12-15",
            price=100.0,
        )
        queryset = MarketPriceModel.objects.filter(pk=market_price.pk)
        result_without_removal = convert_query_to_dictionary_list(
            queryset, remove_foreign_key=False
        )
        assert result_without_removal == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "comment": "",
                "date": date(2025, 12, 15),
                "price": 100.0,
            }
        ]

        result_with_removal = convert_query_to_dictionary_list(
            queryset, remove_foreign_key=True
        )
        assert result_with_removal == [
            {
                "comment": "",
                "date": date(2025, 12, 15),
                "price": 100.0,
            }
        ]

    def test_convert_query_to_dictionary_list_remove_specific_fields(self):
        """
        GIVEN a QuerySet
        WHEN convert_query_to_dictionary_list is called with remove_specific_fields
        THEN specified fields should be removed
        """
        queryset = AssetModel.objects.order_by("asset_id")
        result = convert_query_to_dictionary_list(
            queryset, remove_specific_fields=["short_name", "full_name"]
        )
        assert result == [
            {
                "asset_class": "STOCKS",
                "asset_id": 1,
                "asset_type": "EQUITY_INDEX",
                "location": None,
                "maturity": None,
                "source": "",
                "ticker": "",
            },
            {
                "asset_class": "STOCKS",
                "asset_id": 2,
                "asset_type": "EQUITY_INDEX",
                "location": None,
                "maturity": None,
                "source": "",
                "ticker": "",
            },
        ]

    def test_convert_query_to_dictionary_list_empty_queryset(self):
        """
        GIVEN an empty QuerySet
        WHEN convert_query_to_dictionary_list is called
        THEN an empty list should be returned
        """
        queryset = AssetModel.objects.filter(short_name="NONEXISTENT")
        result = convert_query_to_dictionary_list(queryset)

        assert result == []


class TestFetchHtml(TestCase):
    """Test cases for fetch_html function."""

    @patch("core.services.requests.get")
    def test_fetch_html_success(self, mock_get):
        """
        GIVEN a valid URL
        WHEN fetch_html is called
        THEN a BeautifulSoup object should be returned
        """
        url = "https://example.com"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_get.return_value = mock_response

        result = fetch_html(url)

        assert isinstance(result, BeautifulSoup)
        body = result.find("body")
        assert body is not None
        assert body.text == "Test"
        mock_get.assert_called_once_with(url, timeout=10)

    @patch("core.services.requests.get")
    def test_fetch_html_http_error(self, mock_get):
        """
        GIVEN a URL that returns an HTTP error
        WHEN fetch_html is called
        THEN None should be returned
        """
        url = "https://example.com"
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetch_html(url)

        assert result is None
        mock_get.assert_called_once_with(url, timeout=10)

    @patch("core.services.requests.get")
    def test_fetch_html_request_exception(self, mock_get):
        """
        GIVEN a URL that raises a RequestException
        WHEN fetch_html is called
        THEN None should be returned
        """
        url = "https://example.com"
        mock_get.side_effect = requests.RequestException("Connection error")

        result = fetch_html(url)

        assert result is None
        mock_get.assert_called_once_with(url, timeout=10)

    @patch("core.services.requests.get")
    def test_fetch_html_timeout(self, mock_get):
        """
        GIVEN a URL that times out
        WHEN fetch_html is called
        THEN None should be returned
        """
        url = "https://example.com"
        mock_get.side_effect = requests.Timeout("Request timed out")

        result = fetch_html(url)

        assert result is None
        mock_get.assert_called_once_with(url, timeout=10)


class TestCalculateValueChange(TestCase):
    """Test cases for calculate_value_change."""

    def test_calculate_value_change_percent_and_bps(self):
        """
        GIVEN current and previous levels
        WHEN calculate_value_change is called
        THEN absolute, percent, and bps fields are populated
        """
        assert calculate_value_change(110.0, 100.0) == ValueChange(
            absolute=10.0,
            percent=10.0,
            bps=1000.0,
        )

    def test_calculate_value_change_undefined_when_previous_zero(self):
        """
        GIVEN a zero previous value
        WHEN calculate_value_change is called
        THEN percent is None while absolute and bps remain defined
        """
        assert calculate_value_change(5.0, 0.0) == ValueChange(
            absolute=5.0,
            percent=None,
            bps=500.0,
        )

    def test_calculate_value_change_missing_inputs(self):
        """
        GIVEN a missing current or previous value
        WHEN calculate_value_change is called
        THEN all fields are None
        """
        assert calculate_value_change(None, 100.0) == ValueChange(
            absolute=None,
            percent=None,
            bps=None,
        )
        assert calculate_value_change(100.0, None) == ValueChange(
            absolute=None,
            percent=None,
            bps=None,
        )


class TestParseDatetime(TestCase):
    """Test cases for parse_datetime."""

    def test_parse_datetime_iso(self):
        """
        GIVEN an ISO datetime string with offset
        WHEN parse_datetime is called
        THEN an aware datetime normalized to UTC is returned
        """
        parsed = parse_datetime("2026-10-23T22:05:55+02:00")
        assert parsed is not None
        assert parsed == datetime(2026, 10, 23, 20, 5, 55, tzinfo=timezone.utc)

    def test_parse_datetime_naive_assumes_utc(self):
        """
        GIVEN a naive ISO datetime string
        WHEN parse_datetime is called
        THEN timezone is set to UTC
        """
        parsed = parse_datetime("2026-10-23T22:05:55")
        assert parsed is not None
        assert parsed.tzinfo == timezone.utc

    def test_parse_datetime_naive_with_source_timezone(self):
        """
        GIVEN a naive datetime and America/New_York as the source zone
        WHEN parse_datetime is called
        THEN the wall clock is localized then stored as UTC
        """
        parsed = parse_datetime(
            "2025-01-29T14:00:00",
            naive_timezone="America/New_York",
        )
        assert parsed == datetime(2025, 1, 29, 19, 0, 0, tzinfo=timezone.utc)

    def test_parse_datetime_empty_returns_none(self):
        """
        GIVEN an empty value
        WHEN parse_datetime is called
        THEN None is returned
        """
        assert parse_datetime(None) is None
        assert parse_datetime("") is None


class TestSourceTimezone(TestCase):
    """Test cases for source wall-clock → UTC helpers."""

    def test_get_source_timezone_us_is_new_york(self):
        """
        GIVEN the US location code
        WHEN get_source_timezone is called
        THEN America/New_York is returned
        """
        assert str(get_source_timezone("US")) == "America/New_York"

    def test_convert_local_wall_time_to_utc_fomc_winter(self):
        """
        GIVEN a 14:00 America/New_York wall clock in January
        WHEN converting to UTC
        THEN 19:00 UTC (EST) is returned
        """
        utc_datetime = convert_local_wall_time_to_utc(
            2025,
            1,
            29,
            14,
            source_timezone="America/New_York",
        )
        assert utc_datetime == datetime(2025, 1, 29, 19, 0, 0, tzinfo=timezone.utc)

    def test_convert_local_wall_time_to_utc_fomc_summer(self):
        """
        GIVEN a 14:00 America/New_York wall clock in June
        WHEN converting to UTC
        THEN 18:00 UTC (EDT) is returned
        """
        utc_datetime = convert_local_wall_time_to_utc(
            2025,
            6,
            18,
            14,
            source_timezone="America/New_York",
        )
        assert utc_datetime == datetime(2025, 6, 18, 18, 0, 0, tzinfo=timezone.utc)

    def test_fomc_new_york_displays_as_paris_20_00(self):
        """
        GIVEN an FOMC announcement stored from 14:00 New York time
        WHEN converting for display
        THEN Paris shows 20:00 in both winter and summer
        """
        winter_utc = convert_local_wall_time_to_utc(
            2025,
            1,
            29,
            14,
            source_timezone="America/New_York",
        )
        summer_utc = convert_local_wall_time_to_utc(
            2025,
            6,
            18,
            14,
            source_timezone="America/New_York",
        )
        assert convert_to_display_timezone(winter_utc).strftime("%H:%M") == "20:00"
        assert convert_to_display_timezone(summer_utc).strftime("%H:%M") == "20:00"


class TestDisplayTimezone(TestCase):
    """Test cases for display timezone helpers."""

    def test_convert_to_display_timezone_paris_winter(self):
        """
        GIVEN a UTC datetime in winter
        WHEN converting for display
        THEN Europe/Paris CET (+01:00) is applied
        """
        utc_dt = datetime(2025, 12, 5, 7, 45, 0, tzinfo=timezone.utc)
        paris = convert_to_display_timezone(utc_dt)
        assert paris.strftime("%H:%M") == "08:45"
        assert str(paris.tzinfo) == "Europe/Paris"
