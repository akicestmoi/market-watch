from datetime import date
from typing import List
from unittest.mock import patch

import pytest  # type: ignore[reportMissingImports]
from django.test import TestCase

from central_banks_overview.models import CentralBankChoices, CentralBankDataModel
from central_banks_overview.services.cb_data_services import (
    CentralBankData,
    CentralBankDataBaseInfo,
    CentralBankDataDate,
    CentralBankDataIngestionResponseItem,
    _get_specific_central_bank_data,
    get_central_bank_data,
    ingest_central_bank_data,
    ingest_requested_central_bank_data,
)
from core.tests import parse_query_for_testing
from market_overview.models import PriceSourceChoices
from market_overview.services.price_ingestion_services import ScrapingResult


class TestCentralBankDataServices(TestCase):
    """Test cases for cb_data_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = date(2024, 1, 15)
        self.test_date_2 = date(2024, 2, 15)
        self.frb_data_1 = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        )
        self.frb_data_2 = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date_2,
            value=5.50,
            comment="",
        )
        self.ecb_data_1 = CentralBankDataModel.objects.create(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=self.test_date,
            value=4.0,
            comment="",
        )

    def test_get_central_bank_data_with_target_date(self):
        """
        GIVEN central bank data for a specific date
        WHEN getting central bank data with target_date
        THEN the correct data for that date is returned
        """
        result = list(get_central_bank_data(target_date=self.test_date))
        assert result == [self.frb_data_1, self.ecb_data_1]

    def test_get_central_bank_data_with_central_banks_filter(self):
        """
        GIVEN central bank data for multiple central banks
        WHEN getting central bank data with central_banks filter
        THEN only data for specified central banks is returned
        """
        result = list(
            get_central_bank_data(
                target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
            )
        )
        assert result == [self.frb_data_1]

    def test_get_central_bank_data_last_value(self):
        """
        GIVEN central bank data for multiple dates
        WHEN getting central bank data with last_value=True
        THEN only the latest data for each short_name is returned
        """
        result = list(get_central_bank_data(last_value=True))
        assert result == [self.ecb_data_1, self.frb_data_2]

    def test_get_central_bank_data_last_value_and_target_date_error(self):
        """
        GIVEN both last_value and target_date are provided
        WHEN getting central bank data
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError) as exc_info:
            get_central_bank_data(target_date=self.test_date, last_value=True)
        assert (
            str(exc_info.value)
            == "Last value is not supported when target date is provided."
        )

    def test_get_central_bank_data_all_data(self):
        """
        GIVEN central bank data in the database
        WHEN getting central bank data without filters
        THEN all data is returned
        """
        result = list(get_central_bank_data())
        assert result == [self.frb_data_1, self.frb_data_2, self.ecb_data_1]

    def test_get_central_bank_data_no_data_for_date(self):
        """
        GIVEN no central bank data for a specific date
        WHEN getting central bank data with that date
        THEN an empty queryset is returned
        """
        result = list(get_central_bank_data(target_date=date(2025, 1, 1)))
        assert result == []

    def test_get_central_bank_data_with_none_value(self):
        """
        GIVEN central bank data with None value
        WHEN getting central bank data
        THEN the data with None value is correctly included
        """
        data_with_none = CentralBankDataModel.objects.create(
            cb_data_id=3,
            central_bank=CentralBankChoices.BOJ,
            short_name="BOJ_MUTAN",
            full_name="BOJ Target Uncollateralized Overnight Rate",
            date=self.test_date,
            value=None,
            comment="No data available",
        )
        result = list(get_central_bank_data(target_date=self.test_date))
        assert result == [self.frb_data_1, self.ecb_data_1, data_with_none]

    def test_get_central_bank_data_last_value_with_multiple_short_names(self):
        """
        GIVEN central bank data with multiple short_names
        WHEN getting last value for each
        THEN the latest value for each short_name is returned
        """
        ecb_data_2 = CentralBankDataModel.objects.create(
            cb_data_id=3,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Refinancing",
            full_name="ECB Main Refinancing Operation Rate",
            date=self.test_date_2,
            value=4.25,
            comment="",
        )

        result = list(get_central_bank_data(last_value=True))
        assert result == [self.ecb_data_1, ecb_data_2, self.frb_data_2]

    def test_get_central_bank_data_last_value_no_data(self):
        """
        GIVEN no central bank data in the database
        WHEN getting central bank data with last_value=True
        THEN an empty queryset is returned
        """
        CentralBankDataModel.objects.all().delete()

        result = list(get_central_bank_data(last_value=True))
        assert result == []

    @patch(
        "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
    )
    def test_ingest_central_bank_data_success(self, mock_get_specific_data):
        """
        GIVEN central bank, date, and base info
        WHEN ingesting central bank data
        THEN data is created in the database
        """
        mock_get_specific_data.return_value = CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        )
        all_data_info: List[CentralBankDataBaseInfo] = [
            CentralBankDataBaseInfo(
                cb_data_id=1,
                central_bank=CentralBankChoices.FRB,
                short_name="FRB_FEDFUNDS",
                full_name="FRB Target Fed Funds Rate",
                ticker="test_ticker",
                source=PriceSourceChoices.GLOBAL_RATES,
            )
        ]

        result = ingest_central_bank_data(
            CentralBankChoices.FRB, self.test_date, all_data_info
        )
        assert result == [
            CentralBankDataIngestionResponseItem(
                data_name="FRB Target Fed Funds Rate",
                date=date(2024, 1, 15),
            ),
        ]
        assert CentralBankDataModel.objects.filter(
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        ).exists()

    @patch(
        "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
    )
    def test_ingest_central_bank_data_updates_existing(self, mock_get_specific_data):
        """
        GIVEN existing central bank data
        WHEN ingesting central bank data for the same date
        THEN existing data is updated
        """
        CentralBankDataModel.objects.all().delete()
        existing_data = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.0,
            comment="Old comment",
        )
        mock_get_specific_data.return_value = CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        )
        all_data_info: List[CentralBankDataBaseInfo] = [
            CentralBankDataBaseInfo(
                cb_data_id=1,
                central_bank=CentralBankChoices.FRB,
                short_name="FRB_FEDFUNDS",
                full_name="FRB Target Fed Funds Rate",
                ticker="test_ticker",
                source=PriceSourceChoices.GLOBAL_RATES,
            )
        ]

        result = ingest_central_bank_data(
            CentralBankChoices.FRB, self.test_date, all_data_info
        )
        assert result == [
            CentralBankDataIngestionResponseItem(
                data_name="FRB Target Fed Funds Rate",
                date=date(2024, 1, 15),
            ),
        ]
        existing_data.refresh_from_db()
        assert CentralBankDataModel.objects.filter(
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        ).exists()

    @patch(
        "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
    )
    def test_ingest_central_bank_data_no_matching_central_bank(
        self, mock_get_specific_data
    ):
        """
        GIVEN base info without matching central bank
        WHEN ingesting central bank data
        THEN that central bank is skipped
        """
        all_data_info: List[CentralBankDataBaseInfo] = [
            CentralBankDataBaseInfo(
                cb_data_id=1,
                central_bank=CentralBankChoices.FRB,
                short_name="FRB_FEDFUNDS",
                full_name="FRB Target Fed Funds Rate",
                ticker="test_ticker",
                source=PriceSourceChoices.GLOBAL_RATES,
            )
        ]

        # Request ECB but base info has FRB
        result = ingest_central_bank_data(
            CentralBankChoices.ECB, self.test_date, all_data_info
        )
        assert result == []
        mock_get_specific_data.assert_not_called()

    @patch(
        "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
    )
    @patch(
        "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
    )
    def test_ingest_central_bank_data_with_default_all_data_info(
        self, mock_get_base_info, mock_get_specific_data
    ):
        """
        GIVEN central bank and date without providing all_data_info
        WHEN ingesting central bank data
        THEN _get_central_bank_base_info is called and data is ingested
        """
        CentralBankDataModel.objects.all().delete()
        mock_get_base_info.return_value = [
            CentralBankDataBaseInfo(
                cb_data_id=1,
                central_bank=CentralBankChoices.FRB,
                short_name="FRB_FEDFUNDS",
                full_name="FRB Target Fed Funds Rate",
                ticker="test_ticker",
                source=PriceSourceChoices.GLOBAL_RATES,
            ),
            CentralBankDataBaseInfo(
                cb_data_id=2,
                central_bank=CentralBankChoices.ECB,
                short_name="ECB_Deposit",
                full_name="ECB Deposit Facility Rate",
                ticker="test_ticker2",
                source=PriceSourceChoices.WEBSTAT,
            ),
        ]
        mock_get_specific_data.return_value = CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        )

        result = ingest_central_bank_data(CentralBankChoices.FRB, self.test_date)
        mock_get_base_info.assert_called_once()
        assert result == [
            CentralBankDataIngestionResponseItem(
                data_name="FRB Target Fed Funds Rate",
                date=date(2024, 1, 15),
            ),
        ]
        assert CentralBankDataModel.objects.filter(
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        ).exists()
        assert not CentralBankDataModel.objects.filter(
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=self.test_date,
            value=4.0,
            comment="",
        ).exists()

    @patch(
        "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
    )
    def test_ingest_central_bank_data_with_none_value(self, mock_get_specific_data):
        """
        GIVEN central bank data with None value
        WHEN ingesting central bank data
        THEN data with None value is saved
        """
        all_data_info: List[CentralBankDataBaseInfo] = [
            CentralBankDataBaseInfo(
                cb_data_id=1,
                central_bank=CentralBankChoices.FRB,
                short_name="FRB_FEDFUNDS",
                full_name="FRB Target Fed Funds Rate",
                ticker="test_ticker",
                source=PriceSourceChoices.GLOBAL_RATES,
            )
        ]
        mock_get_specific_data.return_value = CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=None,
            comment="No data available",
        )

        result = ingest_central_bank_data(
            CentralBankChoices.FRB, self.test_date, all_data_info
        )
        assert result == [
            CentralBankDataIngestionResponseItem(
                data_name="FRB Target Fed Funds Rate",
                date=date(2024, 1, 15),
            ),
        ]
        assert CentralBankDataModel.objects.filter(
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=None,
            comment="No data available",
        ).exists()

    @patch(
        "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
    )
    @patch(
        "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
    )
    def test_ingest_requested_central_bank_data(
        self, mock_get_base_info, mock_get_specific_data
    ):
        """
        GIVEN specified dates for central banks
        WHEN ingesting requested central bank data
        THEN only the specified central banks are processed
        """
        CentralBankDataModel.objects.all().delete()
        mock_get_base_info.return_value = [
            CentralBankDataBaseInfo(
                cb_data_id=1,
                central_bank=CentralBankChoices.FRB,
                short_name="FRB_FEDFUNDS",
                full_name="FRB Target Fed Funds Rate",
                ticker="test_ticker",
                source=PriceSourceChoices.GLOBAL_RATES,
            ),
            CentralBankDataBaseInfo(
                cb_data_id=2,
                central_bank=CentralBankChoices.ECB,
                short_name="ECB_Deposit",
                full_name="ECB Deposit Facility Rate",
                ticker="test_ticker2",
                source=PriceSourceChoices.WEBSTAT,
            ),
            CentralBankDataBaseInfo(
                cb_data_id=3,
                central_bank=CentralBankChoices.BOJ,
                short_name="BOJ_MUTAN",
                full_name="BOJ Target Uncollateralized Overnight Rate",
                ticker="test_ticker3",
                source=PriceSourceChoices.GLOBAL_RATES,
            ),
        ]

        def mock_get_specific_data_side_effect(target_date, base_info):
            """Return mock data based on the central bank."""
            values = {
                CentralBankChoices.FRB: 5.25,
                CentralBankChoices.ECB: 4.0,
                CentralBankChoices.BOJ: 5.0,
            }
            return CentralBankData(
                cb_data_id=base_info["cb_data_id"],
                central_bank=base_info["central_bank"],
                short_name=base_info["short_name"],
                full_name=base_info["full_name"],
                date=target_date,
                value=values.get(base_info["central_bank"], None),
                comment="",
            )

        mock_get_specific_data.side_effect = mock_get_specific_data_side_effect

        dates_to_ingest = [
            CentralBankDataDate(
                central_bank=CentralBankChoices.FRB, date=self.test_date
            ),
            CentralBankDataDate(
                central_bank=CentralBankChoices.ECB, date=self.test_date_2
            ),
        ]

        result = ingest_requested_central_bank_data(dates_to_ingest)
        assert result == [
            CentralBankDataIngestionResponseItem(
                data_name="FRB Target Fed Funds Rate",
                date=self.test_date,
            ),
            CentralBankDataIngestionResponseItem(
                data_name="ECB Deposit Facility Rate",
                date=self.test_date_2,
            ),
        ]
        data_in_db = CentralBankDataModel.objects.all()
        assert parse_query_for_testing(data_in_db, ["cb_data_id"]) == [
            {
                "cb_data_id": 1,
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date,
                "value": 5.25,
                "comment": "",
            },
            {
                "cb_data_id": 2,
                "central_bank": CentralBankChoices.ECB.value,
                "short_name": "ECB_Deposit",
                "full_name": "ECB Deposit Facility Rate",
                "date": self.test_date_2,
                "value": 4.0,
                "comment": "",
            },
        ]

    @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
    def test_get_specific_central_bank_data_success_with_global_rates(
        self, mock_scrap_function
    ):
        """
        GIVEN central bank base info with GLOBAL_RATES source
        WHEN getting specific central bank data
        THEN the scraping function is called and data is returned
        """
        mock_scrap_function.return_value = ScrapingResult(price=5.25, comment="Success")

        central_bank_data = CentralBankDataBaseInfo(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            ticker="test_ticker",
            source=PriceSourceChoices.GLOBAL_RATES,
        )

        result = _get_specific_central_bank_data(self.test_date, central_bank_data)
        assert result == CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="Success",
        )
        mock_scrap_function.assert_called_once_with(self.test_date, "test_ticker")

    @patch("central_banks_overview.services.cb_data_services.get_webstat_rates")
    def test_get_specific_central_bank_data_success_with_webstat(
        self, mock_scrap_function
    ):
        """
        GIVEN central bank base info with WEBSTAT source
        WHEN getting specific central bank data
        THEN the scraping function is called and data is returned
        """
        mock_scrap_function.return_value = ScrapingResult(price=4.0, comment="ECB data")

        central_bank_data = CentralBankDataBaseInfo(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            ticker="test_ticker_ecb",
            source=PriceSourceChoices.WEBSTAT,
        )

        result = _get_specific_central_bank_data(self.test_date, central_bank_data)
        assert result == CentralBankData(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=self.test_date,
            value=4.0,
            comment="ECB data",
        )
        mock_scrap_function.assert_called_once_with(self.test_date, "test_ticker_ecb")

    def test_get_specific_central_bank_data_no_scraping_function(self):
        """
        GIVEN central bank base info with unknown source
        WHEN getting specific central bank data
        THEN None price and error comment are returned
        """
        central_bank_data = {
            "cb_data_id": 3,
            "central_bank": CentralBankChoices.BOJ,
            "short_name": "BOJ_MUTAN",
            "full_name": "BOJ Target Uncollateralized Overnight Rate",
            "ticker": "test_ticker_boj",
            "source": "UNKNOWN_SOURCE",
        }

        result = _get_specific_central_bank_data(self.test_date, central_bank_data)  # type: ignore[reportArgumentType]
        assert result == CentralBankData(
            cb_data_id=3,
            central_bank=CentralBankChoices.BOJ,
            short_name="BOJ_MUTAN",
            full_name="BOJ Target Uncollateralized Overnight Rate",
            date=self.test_date,
            value=None,
            comment="No scraping function found.",
        )

    @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
    def test_get_specific_central_bank_data_no_price(self, mock_scrap_function):
        """
        GIVEN scraping function returns None price
        WHEN getting specific central bank data
        THEN data with None price is returned
        """
        mock_scrap_function.return_value = ScrapingResult(
            price=None, comment="No data available"
        )

        central_bank_data = CentralBankDataBaseInfo(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            ticker="test_ticker",
            source=PriceSourceChoices.GLOBAL_RATES,
        )

        result = _get_specific_central_bank_data(self.test_date, central_bank_data)
        assert result == CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=None,
            comment="No data available",
        )

    @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
    def test_get_specific_central_bank_data_empty_comment(self, mock_scrap_function):
        """
        GIVEN scraping function returns empty comment
        WHEN getting specific central bank data
        THEN data with empty comment is returned
        """
        mock_scrap_function.return_value = ScrapingResult(price=5.50, comment="")

        central_bank_data = CentralBankDataBaseInfo(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            ticker="test_ticker",
            source=PriceSourceChoices.GLOBAL_RATES,
        )

        result = _get_specific_central_bank_data(self.test_date, central_bank_data)
        assert result == CentralBankData(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.50,
            comment="",
        )
