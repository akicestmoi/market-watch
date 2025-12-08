# import json
# from datetime import date, datetime, timezone

# from django.test import Client, TestCase
# from freezegun import freeze_time  # type: ignore[reportMissingImports]

# from central_banks_overview.models import (
#     CentralBankChoices,
#     CentralBankDataModel,
#     CentralBankMeetingModel,
# )
# from central_banks_overview.services.cb_inference_services import (
#     CentralBankProbabilityMatrix,
# )
# from market_overview.models import (
#     AssetClassChoices,
#     AssetModel,
#     AssetTypeChoices,
#     LocationChoices,
#     MarketPriceModel,
# )


# class TestCentralBanksRecapView(TestCase):
#     """Test cases for central_banks_recap_view."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = Client()
#         self.base_url = "/central-banks-recap/"
#         self.reference_date = date(2024, 1, 15)
#         self.previous_date = date(2024, 1, 10)

#         # Create EFFR asset for FRB effective rate
#         self.effr_asset = AssetModel.objects.create(
#             short_name="EFFR",
#             full_name="Effective Fed Funds Rate",
#             asset_id=7,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.US,
#             ticker="500",
#         )

#         # Create ESTR asset for ECB effective rate
#         self.estr_asset = AssetModel.objects.create(
#             short_name="ESTR",
#             full_name="Euro Short-Term Rate",
#             asset_id=8,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.EU,
#             ticker="ESTR",
#         )

#         # Create MUTAN asset for BOJ effective rate
#         self.mutan_asset = AssetModel.objects.create(
#             short_name="MUTAN",
#             full_name="Uncollateralized Overnight Call Rate",
#             asset_id=9,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.JP,
#             ticker="MUTAN",
#         )

#         # Create market prices for effective rates
#         MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=self.reference_date,
#             price=5.25,
#         )

#         MarketPriceModel.objects.create(
#             asset=self.estr_asset,
#             date=self.reference_date,
#             price=4.0,
#         )

#         MarketPriceModel.objects.create(
#             asset=self.mutan_asset,
#             date=self.reference_date,
#             price=0.1,
#         )

#         # Create central bank data
#         self.frb_data = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.reference_date,
#             value=5.25,
#             comment="",
#         )

#         # Create meeting dates
#         self.frb_meeting = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             order=1,
#             date=datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc),
#         )

#     @freeze_time("2024-01-16")
#     def test_central_banks_recap_view_success(self):
#         """
#         GIVEN central bank data, effective rates, and meeting dates
#         WHEN accessing central banks recap view
#         THEN the view renders successfully with central bank data
#         """
#         response = self.client.get(
#             self.base_url,
#             {
#                 "reference_date": self.reference_date.isoformat(),
#                 "previous_date": self.previous_date.isoformat(),
#             },
#         )

#         assert response.status_code == 200
#         assert response.context.get("reference_date") == self.reference_date.isoformat()
#         assert response.context.get("previous_date") == self.previous_date.isoformat()

#         central_banks_data = response.context.get("central_banks_data")
#         assert central_banks_data is not None
#         assert CentralBankChoices.FRB in central_banks_data
#         assert (
#             central_banks_data[CentralBankChoices.FRB]["display_name"]
#             == "Federal Reserve (FRB)"
#         )
#         assert len(central_banks_data[CentralBankChoices.FRB]["data"]) > 0

#     @freeze_time("2024-01-16")
#     def test_central_banks_recap_view_default_dates(self):
#         """
#         GIVEN no date parameters
#         WHEN accessing central banks recap view
#         THEN default dates are used
#         """
#         response = self.client.get(self.base_url)

#         assert response.status_code == 200
#         reference_date = response.context.get("reference_date")
#         previous_date = response.context.get("previous_date")
#         assert reference_date is not None
#         assert previous_date is not None

#     @freeze_time("2024-01-16")
#     def test_central_banks_recap_view_future_reference_date_error(self):
#         """
#         GIVEN reference date in the future
#         WHEN accessing central banks recap view
#         THEN an error message is added to context
#         """
#         future_date = date(2025, 1, 1)
#         response = self.client.get(
#             self.base_url,
#             {
#                 "reference_date": future_date.isoformat(),
#                 "previous_date": self.previous_date.isoformat(),
#             },
#         )

#         assert response.status_code == 200
#         error_messages = response.context.get("error_messages")
#         assert error_messages is not None
#         errors = json.loads(error_messages)
#         assert "reference_date" in errors

#     @freeze_time("2024-01-16")
#     def test_central_banks_recap_view_all_central_banks(self):
#         """
#         GIVEN data for all central banks
#         WHEN accessing central banks recap view
#         THEN data for all central banks is returned
#         """
#         # Create ECB and BOJ data
#         ecb_data = CentralBankDataModel.objects.create(
#             cb_data_id=2,
#             central_bank=CentralBankChoices.ECB,
#             short_name="ECB_Deposit",
#             full_name="ECB Deposit Facility Rate",
#             date=self.reference_date,
#             value=4.0,
#             comment="",
#         )

#         boj_data = CentralBankDataModel.objects.create(
#             cb_data_id=5,
#             central_bank=CentralBankChoices.BOJ,
#             short_name="BOJ_MUTAN",
#             full_name="BOJ Target Uncollateralized Overnight Rate",
#             date=self.reference_date,
#             value=0.1,
#             comment="",
#         )

#         # Create meetings
#         ecb_meeting = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             order=1,
#             date=datetime(2024, 4, 15, 13, 15, 0, tzinfo=timezone.utc),
#         )

#         boj_meeting = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             order=1,
#             date=datetime(2024, 5, 1, 4, 0, 0, tzinfo=timezone.utc),
#         )

#         response = self.client.get(
#             self.base_url,
#             {
#                 "reference_date": self.reference_date.isoformat(),
#                 "previous_date": self.previous_date.isoformat(),
#             },
#         )

#         assert response.status_code == 200
#         central_banks_data = response.context.get("central_banks_data")
#         assert len(central_banks_data) == 3
#         assert CentralBankChoices.FRB in central_banks_data
#         assert CentralBankChoices.ECB in central_banks_data
#         assert CentralBankChoices.BOJ in central_banks_data
