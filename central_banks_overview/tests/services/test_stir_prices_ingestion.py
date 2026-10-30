"""Tests for STIR futures price ingestion."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from django.test import TestCase
from freezegun import freeze_time

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesPriceUpdateLogModel,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.scrapers.common import StirFutures
from central_banks_overview.services.stir_prices_ingestion import (
    BulkUpdateFuturesPricesItem,
    bulk_update_futures_prices,
    bulk_update_futures_prices_from_csv,
    delete_stir_futures_price_update_logs_before_date,
    delete_stir_futures_prices_before_date,
    extract_all_stir_futures_prices,
    get_futures_prices,
    ingest_stir_futures_prices,
)
from core.conftest import parse_query_for_testing


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
        "central_banks_overview.services.stir_prices_ingestion.get_fedfunds_futures_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion.get_mutan_futures_prices"
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
        "central_banks_overview.services.stir_prices_ingestion.get_fedfunds_futures_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion.get_mutan_futures_prices"
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
