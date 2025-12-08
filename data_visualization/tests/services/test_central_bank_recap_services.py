# from datetime import date, datetime, timezone

# from django.test import TestCase

# from central_banks_overview.models import (
#     CentralBankChoices,
#     CentralBankDataModel,
#     CentralBankMeetingModel,
# )
# from central_banks_overview.services.cb_inference_services import (
#     CentralBankProbabilityMatrix,
# )
# from data_visualization.services.central_bank_recap_services import (
#     get_central_bank_data_item,
#     get_central_bank_formatted_probability_matrix,
#     get_formatted_probability_matrix_changes,
# )
# from market_overview.models import (
#     AssetClassChoices,
#     AssetModel,
#     AssetTypeChoices,
#     LocationChoices,
#     MarketPriceModel,
# )


# class TestCentralBankRecapServices(TestCase):
#     """Test cases for central_bank_recap_services functions."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.test_date = date(2024, 1, 15)

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
#         self.effr_price = MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=self.test_date,
#             price=5.25,
#         )

#         # Create central bank data
#         self.frb_data = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.25,
#             comment="",
#         )

#         # Create meeting dates
#         self.frb_meeting = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             order=1,
#             date=datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc),
#         )

#     def test_get_central_bank_data_item_frb_success(self):
#         """
#         GIVEN central bank data, effective rate, and meeting date for FRB
#         WHEN getting central bank data item
#         THEN the correct data items are returned with FRB-specific additional data
#         """
#         result = get_central_bank_data_item(CentralBankChoices.FRB, self.test_date)

#         assert (
#             len(result) >= 4
#         )  # Effective Rate + data items + Next Meeting + US Inflation Rate
#         assert result[0]["label"] == "Effective Rate"
#         assert result[0]["value"] == "5.25 %"
#         assert any(item["label"] == "FRB Target Fed Funds Rate" for item in result)
#         assert any(item["label"] == "Next Meeting" for item in result)
#         assert any(item["label"] == "US Inflation Rate" for item in result)
#         assert any(item["value"] == "3.0 %" for item in result)

#     def test_get_central_bank_data_item_ecb_success(self):
#         """
#         GIVEN central bank data, effective rate, and meeting date for ECB
#         WHEN getting central bank data item
#         THEN the correct data items are returned with ECB-specific additional data
#         """
#         # Create ECB data
#         ecb_data = CentralBankDataModel.objects.create(
#             cb_data_id=2,
#             central_bank=CentralBankChoices.ECB,
#             short_name="ECB_Deposit",
#             full_name="ECB Deposit Facility Rate",
#             date=self.test_date,
#             value=4.0,
#             comment="",
#         )

#         # Create ESTR price
#         MarketPriceModel.objects.create(
#             asset=self.estr_asset,
#             date=self.test_date,
#             price=4.0,
#         )

#         # Create ECB meeting
#         ecb_meeting = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             order=1,
#             date=datetime(2024, 4, 15, 13, 15, 0, tzinfo=timezone.utc),
#         )

#         result = get_central_bank_data_item(CentralBankChoices.ECB, self.test_date)

#         assert (
#             len(result) >= 5
#         )  # Effective Rate + data items + Next Meeting + 2 inflation rates
#         assert result[0]["label"] == "Effective Rate"
#         assert result[0]["value"] == "4.0 %"
#         assert any(item["label"] == "ECB Deposit Facility Rate" for item in result)
#         assert any(item["label"] == "France Inflation Rate" for item in result)
#         assert any(item["label"] == "Eurozone Inflation Rate" for item in result)

#     def test_get_central_bank_data_item_boj_success(self):
#         """
#         GIVEN central bank data, effective rate, and meeting date for BOJ
#         WHEN getting central bank data item
#         THEN the correct data items are returned with BOJ-specific additional data
#         """
#         # Create BOJ data
#         boj_data = CentralBankDataModel.objects.create(
#             cb_data_id=5,
#             central_bank=CentralBankChoices.BOJ,
#             short_name="BOJ_MUTAN",
#             full_name="BOJ Target Uncollateralized Overnight Rate",
#             date=self.test_date,
#             value=0.1,
#             comment="",
#         )

#         # Create MUTAN price
#         MarketPriceModel.objects.create(
#             asset=self.mutan_asset,
#             date=self.test_date,
#             price=0.1,
#         )

#         # Create BOJ meeting
#         boj_meeting = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             order=1,
#             date=datetime(2024, 5, 1, 4, 0, 0, tzinfo=timezone.utc),
#         )

#         result = get_central_bank_data_item(CentralBankChoices.BOJ, self.test_date)

#         assert (
#             len(result) >= 4
#         )  # Effective Rate + data items + Next Meeting + Japan Inflation Rate
#         assert result[0]["label"] == "Effective Rate"
#         assert result[0]["value"] == "0.1 %"
#         assert any(
#             item["label"] == "BOJ Target Uncollateralized Overnight Rate"
#             for item in result
#         )
#         assert any(item["label"] == "Japan Inflation Rate" for item in result)
#         assert any(item["value"] == "2.9 %" for item in result)

#     def test_get_central_bank_data_item_no_next_meeting(self):
#         """
#         GIVEN central bank data without next meeting date
#         WHEN getting central bank data item
#         THEN an IndexError is raised (which the view will catch)
#         """
#         from unittest.mock import patch

#         # Mock get_central_bank_next_meeting_date to return None (simulating no meetings)
#         with patch(
#             "data_visualization.services.central_bank_recap_services.cb_meetings_services.get_central_bank_next_meeting_date"
#         ) as mock_next_meeting:
#             mock_next_meeting.return_value = None

#             result = get_central_bank_data_item(CentralBankChoices.FRB, self.test_date)

#             next_meeting_item = next(
#                 item for item in result if item["label"] == "Next Meeting"
#             )
#             assert next_meeting_item["value"] == "N/A"

#     def test_get_central_bank_data_item_no_value(self):
#         """
#         GIVEN central bank data with None value
#         WHEN getting central bank data item
#         THEN N/A is returned for that value
#         """
#         # Create data with None value
#         CentralBankDataModel.objects.create(
#             cb_data_id=3,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_TEST",
#             full_name="FRB Test Rate",
#             date=self.test_date,
#             value=None,
#             comment="No data",
#         )

#         result = get_central_bank_data_item(CentralBankChoices.FRB, self.test_date)

#         test_item = next(item for item in result if item["label"] == "FRB Test Rate")
#         assert test_item["value"] == "N/A"

#     def test_get_central_bank_formatted_probability_matrix_success(self):
#         """
#         GIVEN probability matrices from inference service
#         WHEN getting formatted probability matrix
#         THEN the matrix is sorted by expected_rate_step and returned
#         """
#         from unittest.mock import patch

#         with patch(
#             "data_visualization.services.central_bank_recap_services.cb_inference_services.get_central_bank_probability_matrices"
#         ) as mock_get_matrices:
#             mock_get_matrices.return_value = [
#                 {
#                     "central_bank": CentralBankChoices.FRB,
#                     "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
#                     "probability_matrix": [
#                         {
#                             "expected_rate_step": 25,
#                             "probabilities": [0.3, 0.25],
#                         },
#                         {
#                             "expected_rate_step": 0,
#                             "probabilities": [0.7, 0.75],
#                         },
#                         {
#                             "expected_rate_step": -25,
#                             "probabilities": [0.0, 0.0],
#                         },
#                     ],
#                 }
#             ]

#             result = get_central_bank_formatted_probability_matrix(
#                 CentralBankChoices.FRB, self.test_date
#             )

#             assert result is not None
#             assert result["central_bank"] == CentralBankChoices.FRB
#             assert len(result["probability_matrix"]) == 3
#             # Should be sorted by expected_rate_step
#             assert result["probability_matrix"][0]["expected_rate_step"] == -25
#             assert result["probability_matrix"][1]["expected_rate_step"] == 0
#             assert result["probability_matrix"][2]["expected_rate_step"] == 25

#     def test_get_central_bank_formatted_probability_matrix_not_found(self):
#         """
#         GIVEN no probability matrix for central bank
#         WHEN getting formatted probability matrix
#         THEN None is returned
#         """
#         from unittest.mock import patch

#         with patch(
#             "data_visualization.services.central_bank_recap_services.cb_inference_services.get_central_bank_probability_matrices"
#         ) as mock_get_matrices:
#             mock_get_matrices.return_value = []

#             result = get_central_bank_formatted_probability_matrix(
#                 CentralBankChoices.FRB, self.test_date
#             )

#             assert result is None

#     def test_get_formatted_probability_matrix_changes_success(self):
#         """
#         GIVEN current and previous probability matrices
#         WHEN getting formatted probability matrix changes
#         THEN the changes are calculated and sorted by expected_rate_step
#         """
#         previous_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.FRB,
#             "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.7, 0.75],
#                 },
#                 {
#                     "expected_rate_step": 25,
#                     "probabilities": [0.3, 0.25],
#                 },
#             ],
#         }

#         current_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.FRB,
#             "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.75, 0.80],
#                 },
#                 {
#                     "expected_rate_step": 25,
#                     "probabilities": [0.25, 0.20],
#                 },
#             ],
#         }

#         result = get_formatted_probability_matrix_changes(
#             current_matrix, previous_matrix
#         )

#         assert result is not None
#         assert result["central_bank"] == CentralBankChoices.FRB
#         assert len(result["probability_matrix"]) == 2
#         # Should be sorted by expected_rate_step
#         assert result["probability_matrix"][0]["expected_rate_step"] == 0
#         assert result["probability_matrix"][1]["expected_rate_step"] == 25
#         # Check differences
#         assert abs(result["probability_matrix"][0]["probabilities"][0] - 0.05) < 0.0001
#         assert (
#             abs(result["probability_matrix"][1]["probabilities"][0] - (-0.05)) < 0.0001
#         )

#     def test_get_formatted_probability_matrix_changes_none_current(self):
#         """
#         GIVEN None current probability matrix
#         WHEN getting formatted probability matrix changes
#         THEN None is returned
#         """
#         previous_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.FRB,
#             "meeting_dates": [date(2024, 3, 20)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.7],
#                 },
#             ],
#         }

#         result = get_formatted_probability_matrix_changes(None, previous_matrix)

#         assert result is None

#     def test_get_formatted_probability_matrix_changes_none_previous(self):
#         """
#         GIVEN None previous probability matrix
#         WHEN getting formatted probability matrix changes
#         THEN None is returned
#         """
#         current_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.FRB,
#             "meeting_dates": [date(2024, 3, 20)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.75],
#                 },
#             ],
#         }

#         result = get_formatted_probability_matrix_changes(current_matrix, None)

#         assert result is None
