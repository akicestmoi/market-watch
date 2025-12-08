# from datetime import date, datetime, timezone
# from unittest.mock import MagicMock, patch

# import pytest  # type: ignore[reportMissingImports]
# from django.test import TestCase

# from central_banks_overview.models import CentralBankChoices, CentralBankDataModel
# from central_banks_overview.services.cb_data_services import (
#     CentralBankDataDates,
#     _get_specific_central_bank_data,
#     get_central_bank_data,
#     get_data_dates_to_ingest,
#     ingest_central_bank_data,
# )
# from market_overview.models import PriceSourceChoices


# class TestCentralBankDataServices(TestCase):
#     """Test cases for cb_data_services functions."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.test_date = date(2024, 1, 15)
#         self.test_date_2 = date(2024, 2, 15)
#         self.frb_data_1 = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.25,
#             comment="",
#         )
#         self.frb_data_2 = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date_2,
#             value=5.50,
#             comment="",
#         )
#         self.ecb_data_1 = CentralBankDataModel.objects.create(
#             cb_data_id=2,
#             central_bank=CentralBankChoices.ECB,
#             short_name="ECB_Deposit",
#             full_name="ECB Deposit Facility Rate",
#             date=self.test_date,
#             value=4.0,
#             comment="",
#         )

#     def test_get_central_bank_data_with_target_date(self):
#         """
#         GIVEN central bank data for a specific date
#         WHEN getting central bank data with target_date
#         THEN the correct data for that date is returned
#         """
#         result = list(get_central_bank_data(target_date=self.test_date))
#         assert result == [self.frb_data_1, self.ecb_data_1]

#     def test_get_central_bank_data_with_central_banks_filter(self):
#         """
#         GIVEN central bank data for multiple central banks
#         WHEN getting central bank data with central_banks filter
#         THEN only data for specified central banks is returned
#         """
#         result = list(
#             get_central_bank_data(
#                 target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
#             )
#         )
#         assert result == [self.frb_data_1]

#     def test_get_central_bank_data_last_value(self):
#         """
#         GIVEN central bank data for multiple dates
#         WHEN getting central bank data with last_value=True
#         THEN only the latest data for each short_name is returned
#         """
#         result = list(get_central_bank_data(last_value=True))
#         assert result == [self.ecb_data_1, self.frb_data_2]

#     def test_get_central_bank_data_last_value_and_target_date_error(self):
#         """
#         GIVEN both last_value and target_date are provided
#         WHEN getting central bank data
#         THEN a ValueError is raised
#         """
#         with pytest.raises(ValueError) as exc_info:
#             get_central_bank_data(target_date=self.test_date, last_value=True)
#         assert (
#             str(exc_info.value)
#             == "Last value is not supported when target date is provided."
#         )

#     def test_get_central_bank_data_all_data(self):
#         """
#         GIVEN central bank data in the database
#         WHEN getting central bank data without filters
#         THEN all data is returned
#         """
#         result = list(get_central_bank_data())
#         assert result == [self.frb_data_1, self.frb_data_2, self.ecb_data_1]

#     def test_get_central_bank_data_no_data_for_date(self):
#         """
#         GIVEN no central bank data for a specific date
#         WHEN getting central bank data with that date
#         THEN an empty queryset is returned
#         """
#         result = list(get_central_bank_data(target_date=date(2025, 1, 1)))
#         assert result == []

#     def test_get_central_bank_data_with_none_value(self):
#         """
#         GIVEN central bank data with None value
#         WHEN getting central bank data
#         THEN the data with None value is correctly included
#         """
#         data_with_none = CentralBankDataModel.objects.create(
#             cb_data_id=3,
#             central_bank=CentralBankChoices.BOJ,
#             short_name="BOJ_MUTAN",
#             full_name="BOJ Target Uncollateralized Overnight Rate",
#             date=self.test_date,
#             value=None,
#             comment="No data available",
#         )
#         result = list(get_central_bank_data(target_date=self.test_date))
#         assert result == [self.frb_data_1, self.ecb_data_1, data_with_none]

#     def test_get_central_bank_data_last_value_with_multiple_short_names(self):
#         """
#         GIVEN central bank data with multiple short_names
#         WHEN getting last value for each
#         THEN the latest value for each short_name is returned
#         """
#         ecb_data_2 = CentralBankDataModel.objects.create(
#             cb_data_id=3,
#             central_bank=CentralBankChoices.ECB,
#             short_name="ECB_Refinancing",
#             full_name="ECB Main Refinancing Operation Rate",
#             date=self.test_date_2,
#             value=4.25,
#             comment="",
#         )

#         result = list(get_central_bank_data(last_value=True))
#         assert result == [self.ecb_data_1, ecb_data_2, self.frb_data_2]

#     def test_get_central_bank_data_last_value_no_data(self):
#         """
#         GIVEN no central bank data in the database
#         WHEN getting central bank data with last_value=True
#         THEN an empty queryset is returned
#         """
#         CentralBankDataModel.objects.all().delete()

#         result = list(get_central_bank_data(last_value=True))
#         assert result == []

#     @patch(
#         "central_banks_overview.services.cb_data_services.get_central_bank_next_meeting_date"
#     )
#     def test_get_data_dates_to_ingest_single_request(self, mock_next_meeting):
#         """
#         GIVEN a single requested central bank date
#         WHEN getting all central bank data dates
#         THEN the requested date is returned and meeting dates are fetched for others
#         """
#         mock_next_meeting.return_value = datetime(
#             2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc
#         )
#         result = get_data_dates_to_ingest(
#             [
#                 CentralBankDataDates(
#                     central_bank=CentralBankChoices.FRB, date=self.test_date
#                 )
#             ]
#         )
#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "date": date(2024, 1, 15),
#             },
#             {
#                 "central_bank": CentralBankChoices.BOJ,
#                 "date": date(2024, 3, 20),
#             },
#             {
#                 "central_bank": CentralBankChoices.ECB,
#                 "date": date(2024, 3, 20),
#             },
#         ]

#     @patch(
#         "central_banks_overview.services.cb_data_services.get_central_bank_next_meeting_date"
#     )
#     def test_get_data_dates_to_ingest_multiple_requests(self, mock_next_meeting):
#         """
#         GIVEN multiple requested central bank dates
#         WHEN getting all central bank data dates
#         THEN all requested dates are returned
#         """
#         mock_next_meeting.return_value = datetime(
#             2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc
#         )

#         result = get_data_dates_to_ingest(
#             [
#                 CentralBankDataDates(
#                     central_bank=CentralBankChoices.FRB, date=self.test_date
#                 ),
#                 CentralBankDataDates(
#                     central_bank=CentralBankChoices.ECB, date=self.test_date_2
#                 ),
#             ]
#         )
#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "date": date(2024, 1, 15),
#             },
#             {
#                 "central_bank": CentralBankChoices.BOJ,
#                 "date": date(2024, 3, 20),
#             },
#             {
#                 "central_bank": CentralBankChoices.ECB,
#                 "date": date(2024, 2, 15),
#             },
#         ]

#     @patch(
#         "central_banks_overview.services.cb_data_services.get_central_bank_next_meeting_date"
#     )
#     def test_get_data_dates_to_ingest_no_meeting_dates(self, mock_next_meeting):
#         """
#         GIVEN requested central bank dates and no meeting dates available
#         WHEN getting all central bank data dates
#         THEN only requested dates are returned
#         """
#         mock_next_meeting.return_value = None

#         requested = [
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.FRB, date=self.test_date
#             )
#         ]

#         result = get_data_dates_to_ingest(requested)
#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "date": date(2024, 1, 15),
#             },
#         ]

#     @patch(
#         "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
#     )
#     @patch(
#         "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
#     )
#     def test_ingest_central_bank_data_success(
#         self, mock_get_base_info, mock_get_specific_data
#     ):
#         """
#         GIVEN central bank data dates and base info
#         WHEN ingesting central bank data
#         THEN data is created in the database
#         """
#         mock_get_base_info.return_value = [
#             {
#                 "cb_data_id": 1,
#                 "central_bank": CentralBankChoices.FRB,
#                 "short_name": "FRB_FEDFUNDS",
#                 "full_name": "FRB Target Fed Funds Rate",
#                 "ticker": "test_ticker",
#                 "source": "GLOBAL_RATES",
#             }
#         ]
#         mock_get_specific_data.return_value = {
#             "cb_data_id": 1,
#             "central_bank": CentralBankChoices.FRB,
#             "short_name": "FRB_FEDFUNDS",
#             "full_name": "FRB Target Fed Funds Rate",
#             "date": self.test_date,
#             "value": 5.25,
#             "comment": "",
#         }

#         central_bank_data_dates = [
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.FRB, date=self.test_date
#             )
#         ]

#         result = ingest_central_bank_data(central_bank_data_dates)
#         assert result == [
#             {
#                 "data_name": "FRB Target Fed Funds Rate",
#                 "date": date(2024, 1, 15),
#             },
#         ]
#         assert CentralBankDataModel.objects.filter(
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.25,
#             comment="",
#         ).exists()

#     @patch(
#         "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
#     )
#     @patch(
#         "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
#     )
#     def test_ingest_central_bank_data_updates_existing(
#         self, mock_get_base_info, mock_get_specific_data
#     ):
#         """
#         GIVEN existing central bank data
#         WHEN ingesting central bank data for the same date
#         THEN existing data is updated
#         """
#         # Delete setUp data to avoid duplicates
#         CentralBankDataModel.objects.all().delete()

#         existing_data = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.0,
#             comment="Old comment",
#         )
#         mock_get_base_info.return_value = [
#             {
#                 "cb_data_id": 1,
#                 "central_bank": CentralBankChoices.FRB,
#                 "short_name": "FRB_FEDFUNDS",
#                 "full_name": "FRB Target Fed Funds Rate",
#                 "ticker": "test_ticker",
#                 "source": "GLOBAL_RATES",
#             }
#         ]

#         mock_get_specific_data.return_value = {
#             "cb_data_id": 1,
#             "central_bank": CentralBankChoices.FRB,
#             "short_name": "FRB_FEDFUNDS",
#             "full_name": "FRB Target Fed Funds Rate",
#             "date": self.test_date,
#             "value": 5.25,
#             "comment": "New comment",
#         }

#         central_bank_data_dates = [
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.FRB, date=self.test_date
#             )
#         ]

#         result = ingest_central_bank_data(central_bank_data_dates)
#         assert result == [
#             {
#                 "data_name": "FRB Target Fed Funds Rate",
#                 "date": date(2024, 1, 15),
#             },
#         ]
#         existing_data.refresh_from_db()
#         assert CentralBankDataModel.objects.filter(
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.25,
#             comment="New comment",
#         ).exists()

#     @patch(
#         "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
#     )
#     @patch(
#         "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
#     )
#     def test_ingest_central_bank_data_no_date_for_central_bank(
#         self, mock_get_base_info, mock_get_specific_data
#     ):
#         """
#         GIVEN base info without matching date in central_bank_data_dates
#         WHEN ingesting central bank data
#         THEN that central bank is skipped
#         """
#         mock_get_base_info.return_value = [
#             {
#                 "cb_data_id": 1,
#                 "central_bank": CentralBankChoices.FRB,
#                 "short_name": "FRB_FEDFUNDS",
#                 "full_name": "FRB Target Fed Funds Rate",
#                 "ticker": "test_ticker",
#                 "source": "GLOBAL_RATES",
#             }
#         ]

#         # Request ECB date but base info has FRB
#         central_bank_data_dates = [
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.ECB, date=self.test_date
#             )
#         ]

#         result = ingest_central_bank_data(central_bank_data_dates)
#         assert result == []
#         mock_get_specific_data.assert_not_called()

#     @patch(
#         "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
#     )
#     @patch(
#         "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
#     )
#     def test_ingest_central_bank_data_multiple_central_banks(
#         self, mock_get_base_info, mock_get_specific_data
#     ):
#         """
#         GIVEN multiple central banks with dates
#         WHEN ingesting central bank data
#         THEN all central banks are processed
#         """
#         # Delete setUp data to avoid duplicates
#         CentralBankDataModel.objects.all().delete()

#         mock_get_base_info.return_value = [
#             {
#                 "cb_data_id": 1,
#                 "central_bank": CentralBankChoices.FRB,
#                 "short_name": "FRB_FEDFUNDS",
#                 "full_name": "FRB Target Fed Funds Rate",
#                 "ticker": "test_ticker",
#                 "source": "GLOBAL_RATES",
#             },
#             {
#                 "cb_data_id": 2,
#                 "central_bank": CentralBankChoices.ECB,
#                 "short_name": "ECB_Deposit",
#                 "full_name": "ECB Deposit Facility Rate",
#                 "ticker": "test_ticker2",
#                 "source": "WEBSTAT",
#             },
#         ]

#         def mock_get_specific_data_side_effect(target_date, base_info):
#             return {
#                 "cb_data_id": base_info["cb_data_id"],
#                 "central_bank": base_info["central_bank"],
#                 "short_name": base_info["short_name"],
#                 "full_name": base_info["full_name"],
#                 "date": target_date,
#                 "value": (
#                     5.25 if base_info["central_bank"] == CentralBankChoices.FRB else 4.0
#                 ),
#                 "comment": "",
#             }

#         mock_get_specific_data.side_effect = mock_get_specific_data_side_effect

#         central_bank_data_dates = [
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.FRB, date=self.test_date
#             ),
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.ECB, date=self.test_date
#             ),
#         ]

#         result = ingest_central_bank_data(central_bank_data_dates)
#         assert result == [
#             {
#                 "data_name": "FRB Target Fed Funds Rate",
#                 "date": date(2024, 1, 15),
#             },
#             {
#                 "data_name": "ECB Deposit Facility Rate",
#                 "date": date(2024, 1, 15),
#             },
#         ]
#         assert CentralBankDataModel.objects.filter(
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.25,
#             comment="",
#         ).exists()
#         assert CentralBankDataModel.objects.filter(
#             central_bank=CentralBankChoices.ECB,
#             short_name="ECB_Deposit",
#             full_name="ECB Deposit Facility Rate",
#             date=self.test_date,
#             value=4.0,
#             comment="",
#         ).exists()

#     @patch(
#         "central_banks_overview.services.cb_data_services._get_specific_central_bank_data"
#     )
#     @patch(
#         "central_banks_overview.services.cb_data_services._get_central_bank_base_info"
#     )
#     def test_ingest_central_bank_data_with_none_value(
#         self, mock_get_base_info, mock_get_specific_data
#     ):
#         """
#         GIVEN central bank data with None value
#         WHEN ingesting central bank data
#         THEN data with None value is saved
#         """
#         mock_get_base_info.return_value = [
#             {
#                 "cb_data_id": 1,
#                 "central_bank": CentralBankChoices.FRB,
#                 "short_name": "FRB_FEDFUNDS",
#                 "full_name": "FRB Target Fed Funds Rate",
#                 "ticker": "test_ticker",
#                 "source": "GLOBAL_RATES",
#             }
#         ]

#         mock_get_specific_data.return_value = {
#             "cb_data_id": 1,
#             "central_bank": CentralBankChoices.FRB,
#             "short_name": "FRB_FEDFUNDS",
#             "full_name": "FRB Target Fed Funds Rate",
#             "date": self.test_date,
#             "value": None,
#             "comment": "No data available",
#         }

#         central_bank_data_dates = [
#             CentralBankDataDates(
#                 central_bank=CentralBankChoices.FRB, date=self.test_date
#             )
#         ]

#         result = ingest_central_bank_data(central_bank_data_dates)
#         assert result == [
#             {
#                 "data_name": "FRB Target Fed Funds Rate",
#                 "date": date(2024, 1, 15),
#             },
#         ]
#         assert CentralBankDataModel.objects.filter(
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=None,
#             comment="No data available",
#         ).exists()

#     # @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
#     # def test_get_specific_central_bank_data_success_with_global_rates(
#     #     self, mock_scrap_function
#     # ):
#     #     """
#     #     GIVEN central bank base info with GLOBAL_RATES source
#     #     WHEN getting specific central bank data
#     #     THEN the scraping function is called and data is returned
#     #     """
#     #     mock_scrap_function.return_value = {"price": 5.25, "comment": "Success"}

#     #     central_bank_data = {
#     #         "cb_data_id": 1,
#     #         "central_bank": CentralBankChoices.FRB,
#     #         "short_name": "FRB_FEDFUNDS",
#     #         "full_name": "FRB Target Fed Funds Rate",
#     #         "ticker": "test_ticker",
#     #         "source": PriceSourceChoices.GLOBAL_RATES,
#     #     }

#     #     result = get_specific_central_bank_data(self.test_date, central_bank_data)

#     #     assert result["cb_data_id"] == 1
#     #     assert result["central_bank"] == CentralBankChoices.FRB
#     #     assert result["short_name"] == "FRB_FEDFUNDS"
#     #     assert result["full_name"] == "FRB Target Fed Funds Rate"
#     #     assert result["date"] == self.test_date
#     #     assert result["value"] == 5.25
#     #     assert result["comment"] == "Success"
#     #     mock_scrap_function.assert_called_once_with(self.test_date, "test_ticker")

#     # @patch("central_banks_overview.services.cb_data_services.get_webstat_rates")
#     # def test_get_specific_central_bank_data_success_with_webstat(
#     #     self, mock_scrap_function
#     # ):
#     #     """
#     #     GIVEN central bank base info with WEBSTAT source
#     #     WHEN getting specific central bank data
#     #     THEN the scraping function is called and data is returned
#     #     """
#     #     mock_scrap_function.return_value = {"price": 4.0, "comment": "ECB data"}

#     #     central_bank_data = {
#     #         "cb_data_id": 2,
#     #         "central_bank": CentralBankChoices.ECB,
#     #         "short_name": "ECB_Deposit",
#     #         "full_name": "ECB Deposit Facility Rate",
#     #         "ticker": "test_ticker_ecb",
#     #         "source": PriceSourceChoices.WEBSTAT,
#     #     }

#     #     result = get_specific_central_bank_data(self.test_date, central_bank_data)

#     #     assert result["cb_data_id"] == 2
#     #     assert result["central_bank"] == CentralBankChoices.ECB
#     #     assert result["short_name"] == "ECB_Deposit"
#     #     assert result["full_name"] == "ECB Deposit Facility Rate"
#     #     assert result["date"] == self.test_date
#     #     assert result["value"] == 4.0
#     #     assert result["comment"] == "ECB data"
#     #     mock_scrap_function.assert_called_once_with(self.test_date, "test_ticker_ecb")

#     # def test_get_specific_central_bank_data_no_scraping_function(self):
#     #     """
#     #     GIVEN central bank base info with unknown source
#     #     WHEN getting specific central bank data
#     #     THEN None price and error comment are returned
#     #     """
#     #     central_bank_data = {
#     #         "cb_data_id": 3,
#     #         "central_bank": CentralBankChoices.BOJ,
#     #         "short_name": "BOJ_MUTAN",
#     #         "full_name": "BOJ Target Uncollateralized Overnight Rate",
#     #         "ticker": "test_ticker_boj",
#     #         "source": "UNKNOWN_SOURCE",  # Not in CENTRAL_BANK_DATA_MAP
#     #     }

#     #     result = get_specific_central_bank_data(self.test_date, central_bank_data)

#     #     assert result["cb_data_id"] == 3
#     #     assert result["central_bank"] == CentralBankChoices.BOJ
#     #     assert result["short_name"] == "BOJ_MUTAN"
#     #     assert result["full_name"] == "BOJ Target Uncollateralized Overnight Rate"
#     #     assert result["date"] == self.test_date
#     #     assert result["value"] is None
#     #     assert result["comment"] == "No scraping function found."

#     # @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
#     # def test_get_specific_central_bank_data_no_price(self, mock_scrap_function):
#     #     """
#     #     GIVEN scraping function returns None price
#     #     WHEN getting specific central bank data
#     #     THEN data with None price is returned
#     #     """
#     #     mock_scrap_function.return_value = {
#     #         "price": None,
#     #         "comment": "No data available",
#     #     }

#     #     central_bank_data = {
#     #         "cb_data_id": 1,
#     #         "central_bank": CentralBankChoices.FRB,
#     #         "short_name": "FRB_FEDFUNDS",
#     #         "full_name": "FRB Target Fed Funds Rate",
#     #         "ticker": "test_ticker",
#     #         "source": PriceSourceChoices.GLOBAL_RATES,
#     #     }

#     #     result = get_specific_central_bank_data(self.test_date, central_bank_data)

#     #     assert result["cb_data_id"] == 1
#     #     assert result["central_bank"] == CentralBankChoices.FRB
#     #     assert result["date"] == self.test_date
#     #     assert result["value"] is None
#     #     assert result["comment"] == "No data available"

#     # @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
#     # def test_get_specific_central_bank_data_zero_price(self, mock_scrap_function):
#     #     """
#     #     GIVEN scraping function returns zero price
#     #     WHEN getting specific central bank data
#     #     THEN data with zero price is returned
#     #     """
#     #     mock_scrap_function.return_value = {"price": 0.0, "comment": "Zero rate"}

#     #     central_bank_data = {
#     #         "cb_data_id": 5,
#     #         "central_bank": CentralBankChoices.BOJ,
#     #         "short_name": "BOJ_MUTAN",
#     #         "full_name": "BOJ Target Uncollateralized Overnight Rate",
#     #         "ticker": "test_ticker",
#     #         "source": PriceSourceChoices.GLOBAL_RATES,
#     #     }

#     #     result = get_specific_central_bank_data(self.test_date, central_bank_data)

#     #     assert result["cb_data_id"] == 5
#     #     assert result["central_bank"] == CentralBankChoices.BOJ
#     #     assert result["date"] == self.test_date
#     #     assert result["value"] == 0.0
#     #     assert result["comment"] == "Zero rate"

#     # @patch("central_banks_overview.services.cb_data_services.scrap_from_global_rates")
#     # def test_get_specific_central_bank_data_empty_comment(self, mock_scrap_function):
#     #     """
#     #     GIVEN scraping function returns empty comment
#     #     WHEN getting specific central bank data
#     #     THEN data with empty comment is returned
#     #     """
#     #     mock_scrap_function.return_value = {"price": 5.50, "comment": ""}

#     #     central_bank_data = {
#     #         "cb_data_id": 1,
#     #         "central_bank": CentralBankChoices.FRB,
#     #         "short_name": "FRB_FEDFUNDS",
#     #         "full_name": "FRB Target Fed Funds Rate",
#     #         "ticker": "test_ticker",
#     #         "source": PriceSourceChoices.GLOBAL_RATES,
#     #     }

#     #     result = get_specific_central_bank_data(self.test_date, central_bank_data)

#     #     assert result["cb_data_id"] == 1
#     #     assert result["central_bank"] == CentralBankChoices.FRB
#     #     assert result["date"] == self.test_date
#     #     assert result["value"] == 5.50
#     #     assert result["comment"] == ""
