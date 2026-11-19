"""Tests for shared ORM helpers in 'core.services.orm'."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.test import TestCase
from freezegun import freeze_time
from rest_framework.exceptions import NotFound

from core.services.orm import (
    convert_query_to_dictionary_list,
    update_with_logs,
    upsert_with_logs,
)
from core.testing import parse_query_for_testing
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    MarketPriceModel,
    PriceUpdateLogModel,
)

FREEZE_TIME = datetime(2025, 12, 15, 0, 0, 0, tzinfo=timezone.utc)


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
        GIVEN a concurrent create already inserted the market price
        WHEN upsert_with_logs hits IntegrityError on create
        THEN it should return the existing market price without updating it
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
            NotFound(detail="No MarketPriceModel found matching lookup"),
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
