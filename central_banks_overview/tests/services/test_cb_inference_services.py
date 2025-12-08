# from datetime import date

# from django.test import TestCase

# from central_banks_overview.models import CentralBankChoices
# from central_banks_overview.services.cb_inference_services import (
#     CentralBankProbabilityMatrix,
#     calculate_probability_changes,
#     get_central_bank_effective_rate,
#     get_fall_back_rate,
# )
# from market_overview.models import (
#     AssetClassChoices,
#     AssetModel,
#     AssetTypeChoices,
#     LocationChoices,
#     MarketPriceModel,
# )


# class TestCentralBankInferenceServices(TestCase):
#     """Test cases for cb_inference_services functions."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.test_date = date(2024, 1, 15)
#         self.test_date_earlier = date(2024, 1, 10)

#         # Create EFFR asset (for FRB)
#         self.effr_asset = AssetModel.objects.create(
#             short_name="EFFR",
#             full_name="Effective Fed Funds Rate",
#             asset_id=7,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.US,
#             ticker="500",
#         )

#         # Create ESTR asset (for ECB)
#         self.estr_asset = AssetModel.objects.create(
#             short_name="ESTR",
#             full_name="Euro Short-Term Rate",
#             asset_id=8,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.EU,
#             ticker="ESTR",
#         )

#         # Create MUTAN asset (for BOJ)
#         self.mutan_asset = AssetModel.objects.create(
#             short_name="MUTAN",
#             full_name="Uncollateralized Overnight Call Rate",
#             asset_id=9,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.JP,
#             ticker="MUTAN",
#         )

#         # Create market prices
#         self.effr_price = MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=self.test_date,
#             price=5.25,
#         )

#         self.effr_price_earlier = MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=self.test_date_earlier,
#             price=5.0,
#         )

#     def test_get_central_bank_effective_rate_success(self):
#         """
#         GIVEN market price for central bank target rate
#         WHEN getting effective rate
#         THEN the correct rate is returned
#         """
#         result = get_central_bank_effective_rate(CentralBankChoices.FRB, self.test_date)
#         assert result == 5.25

#     def test_get_fall_back_rate_success(self):
#         """
#         GIVEN no market price for target date but earlier price exists
#         WHEN getting fall back rate
#         THEN the last available price is returned
#         """
#         result = get_fall_back_rate(CentralBankChoices.FRB, date(2024, 1, 20))
#         assert result == 5.25

#     def test_get_fall_back_rate_with_earlier_date(self):
#         """
#         GIVEN multiple market prices
#         WHEN getting fall back rate for a date
#         THEN the most recent price before or on that date is returned
#         """
#         result = get_fall_back_rate(CentralBankChoices.FRB, self.test_date_earlier)
#         assert result == 5.0

#     def test_calculate_probability_changes(self):
#         """
#         GIVEN current and previous probability matrices
#         WHEN calculating probability changes
#         THEN the differences between probabilities are returned
#         """
#         previous_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.FRB,
#             "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": -25,
#                     "probabilities": [0.1, 0.05],
#                 },
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.7, 0.75],
#                 },
#                 {
#                     "expected_rate_step": 25,
#                     "probabilities": [0.2, 0.20],
#                 },
#             ],
#         }

#         current_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.FRB,
#             "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": -25,
#                     "probabilities": [0.05, 0.02],
#                 },
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.75, 0.80],
#                 },
#                 {
#                     "expected_rate_step": 25,
#                     "probabilities": [0.20, 0.18],
#                 },
#             ],
#         }

#         result = calculate_probability_changes(current_matrix, previous_matrix)

#         assert result["central_bank"] == CentralBankChoices.FRB
#         assert result["meeting_dates"] == [date(2024, 3, 20), date(2024, 5, 1)]
#         assert len(result["probability_matrix"]) == 3

#         # Find entries by expected_rate_step
#         step_minus_25 = next(
#             e for e in result["probability_matrix"] if e["expected_rate_step"] == -25
#         )
#         step_0 = next(
#             e for e in result["probability_matrix"] if e["expected_rate_step"] == 0
#         )
#         step_25 = next(
#             e for e in result["probability_matrix"] if e["expected_rate_step"] == 25
#         )

#         # Check probabilities with approximate comparison due to floating point precision
#         assert abs(step_minus_25["probabilities"][0] - (-0.05)) < 0.0001
#         assert abs(step_minus_25["probabilities"][1] - (-0.03)) < 0.0001
#         assert abs(step_0["probabilities"][0] - 0.05) < 0.0001
#         assert abs(step_0["probabilities"][1] - 0.05) < 0.0001
#         assert abs(step_25["probabilities"][0] - 0.0) < 0.0001
#         assert abs(step_25["probabilities"][1] - (-0.02)) < 0.0001

#     def test_get_central_bank_effective_rate_no_price_error(self):
#         """
#         GIVEN no market price for central bank target rate on target date
#         WHEN getting effective rate
#         THEN a DoesNotExist error is raised
#         """
#         # Clear all prices
#         MarketPriceModel.objects.all().delete()

#         try:
#             get_central_bank_effective_rate(CentralBankChoices.FRB, self.test_date)
#             assert False, "Expected DoesNotExist error"
#         except MarketPriceModel.DoesNotExist:
#             pass

#     def test_get_fall_back_rate_no_prices_error(self):
#         """
#         GIVEN no market prices at all
#         WHEN getting fall back rate
#         THEN a ValueError is raised
#         """
#         MarketPriceModel.objects.all().delete()

#         try:
#             get_fall_back_rate(CentralBankChoices.FRB, self.test_date)
#             assert False, "Expected ValueError"
#         except ValueError as e:
#             assert "No rates found" in str(e)

#     def test_get_fall_back_rate_only_future_prices_error(self):
#         """
#         GIVEN only prices after target date
#         WHEN getting fall back rate
#         THEN a ValueError is raised
#         """
#         MarketPriceModel.objects.all().delete()

#         # Create price after target date
#         MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=date(2024, 2, 1),
#             price=5.5,
#         )

#         try:
#             get_fall_back_rate(CentralBankChoices.FRB, self.test_date)
#             assert False, "Expected ValueError"
#         except ValueError as e:
#             assert "No rates found" in str(e)

#     def test_get_fall_back_rate_with_none_prices(self):
#         """
#         GIVEN market prices with None values
#         WHEN getting fall back rate
#         THEN None prices are skipped and last non-None price is returned
#         """
#         MarketPriceModel.objects.all().delete()

#         # Create price with None value
#         MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=date(2024, 1, 5),
#             price=None,
#         )

#         # Create valid price
#         MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=date(2024, 1, 10),
#             price=5.0,
#         )

#         # Create another None price
#         MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=date(2024, 1, 12),
#             price=None,
#         )

#         result = get_fall_back_rate(CentralBankChoices.FRB, date(2024, 1, 15))
#         assert result == 5.0

#     def test_calculate_probability_changes_single_meeting(self):
#         """
#         GIVEN probability matrices with single meeting
#         WHEN calculating probability changes
#         THEN the differences are calculated correctly
#         """
#         previous_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.ECB,
#             "meeting_dates": [date(2024, 4, 15)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.6],
#                 },
#             ],
#         }

#         current_matrix: CentralBankProbabilityMatrix = {
#             "central_bank": CentralBankChoices.ECB,
#             "meeting_dates": [date(2024, 4, 15)],
#             "probability_matrix": [
#                 {
#                     "expected_rate_step": 0,
#                     "probabilities": [0.8],
#                 },
#             ],
#         }

#         result = calculate_probability_changes(current_matrix, previous_matrix)

#         assert result["central_bank"] == CentralBankChoices.ECB
#         assert len(result["probability_matrix"]) == 1
#         assert abs(result["probability_matrix"][0]["probabilities"][0] - 0.2) < 0.0001
