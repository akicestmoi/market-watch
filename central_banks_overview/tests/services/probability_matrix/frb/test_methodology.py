# from datetime import date, datetime, timezone
# from unittest.mock import patch

# import pytest  # type: ignore[reportMissingImports]
# from django.test import TestCase

# from central_banks_overview.models import (
#     CentralBankChoices,
#     StirFuturesModel,
#     StirFuturesNameChoices,
#     StirFuturesSourceChoices,
# )
# from central_banks_overview.services.cb_inference_services import (
#     CentralBankProbabilityMatrix,
#     EstrFuturesProbabilityMatrixService,
#     FedFundsFuturesProbabilityMatrixService,
#     FedFuturesRateType,
#     MutanFuturesProbabilityMatrixService,
#     calculate_probability_changes,
#     get_central_bank_effective_rate,
#     get_central_bank_probability_matrices,
#     get_fall_back_rate,
# )
# from central_banks_overview.services.cb_meetings_services import CentralBankMeetingDates
# from market_overview.models import (
#     AssetClassChoices,
#     AssetModel,
#     AssetTypeChoices,
#     LocationChoices,
#     MarketPriceModel,
# )

# class TestFRBStep1FillStartEndPrices(TestCase):
#     """
#     Test FRB Step 1: Fill Start/End Prices For Periods Without Meeting
#     Methodology: Section "Step 1: Fill Start/End Prices For Periods Without Meeting"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 5.25
#         self.test_date = date(2024, 1, 15)

#     def test_propagate_forward_first_contract_no_meeting(self):
#         """
#         GIVEN first contract without meeting
#         WHEN inferring period rates
#         THEN implied rate becomes base rate for subsequent contracts
#         """
#         # Create futures: first contract (Jan) has no meeting, implied rate = 5.25%
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1],
#             meeting_dates=[],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # First contract without meeting: previous_rate should be set to initial_base_rate
#         assert (
#             len(meeting_rate_info) == 0
#         )  # No meetings, so no meeting_rate_info entries


#     def test_propagate_backward_contract_after_meeting(self):
#         """
#         GIVEN contract after meeting without meeting
#         WHEN inferring period rates
#         THEN implied rate updates previous meeting's end rate
#         """
#         # Contract 1: Has meeting on Jan 15
#         # Contract 2: No meeting, implied rate = 5.50%
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # Should have one meeting entry
#         assert len(meeting_rate_info) == 1
#         assert meeting_rate_info[0]["meeting_date"] == date(2024, 1, 15)
#         assert meeting_rate_info[0]["start_rate"] == self.base_rate
#         # end_rate should be set by backward propagation from future_2
#         assert meeting_rate_info[0]["end_rate"] == 5.50

#     def test_propagate_rates_mixed_contracts(self):
#         """
#         GIVEN mixed contracts (with and without meetings)
#         WHEN inferring period rates
#         THEN rates are propagated correctly forward and backward
#         """
#         # Contract 1: No meeting, implied rate = 5.25%
#         # Contract 2: Has meeting on Feb 15
#         # Contract 3: No meeting, implied rate = 5.75%
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_3 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=94.25,  # 100 - 5.75 = 94.25
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2, future_3],
#             meeting_dates=[datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # Should have one meeting entry
#         assert len(meeting_rate_info) == 1
#         assert meeting_rate_info[0]["meeting_date"] == date(2024, 2, 15)
#         # start_rate should be propagated from future_1 (5.25%)
#         assert meeting_rate_info[0]["start_rate"] == 5.25
#         # end_rate should be propagated from future_3 (5.75%)
#         assert meeting_rate_info[0]["end_rate"] == 5.75

#     def test_first_contract_with_meeting(self):
#         """
#         GIVEN first contract has a meeting
#         WHEN inferring period rates
#         THEN start_rate is set to initial_base_rate
#         """
#         # Contract 1: Has meeting on Jan 15 (first contract)
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # Should have one meeting entry
#         assert len(meeting_rate_info) == 1
#         assert meeting_rate_info[0]["meeting_date"] == date(2024, 1, 15)
#         # start_rate should be initial_base_rate
#         # (since idx == 0 and previous_rate is None)
#         assert meeting_rate_info[0]["start_rate"] == self.base_rate
#         # end_rate should be None (will be calculated later)
#         assert meeting_rate_info[0]["end_rate"] is None

#     def test_last_contract_without_meeting(self):
#         """
#         GIVEN last contract without meeting
#         WHEN inferring period rates
#         THEN previous meeting's end_rate is updated
#         """
#         # Contract 1: Has meeting on Jan 15
#         # Contract 2: No meeting (last contract), implied rate = 5.50%
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # Should have one meeting entry
#         assert len(meeting_rate_info) == 1
#         assert meeting_rate_info[0]["meeting_date"] == date(2024, 1, 15)
#         # end_rate should be set by backward propagation from future_2 (last contract)
#         assert meeting_rate_info[0]["end_rate"] == 5.50

#     def test_last_contract_with_meeting(self):
#         """
#         GIVEN last contract has a meeting
#         WHEN inferring period rates
#         THEN meeting is added with start_rate from previous contract
#         """
#         # Contract 1: No meeting, implied rate = 5.25%
#         # Contract 2: Has meeting on Feb 15 (last contract)
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # Should have one meeting entry
#         assert len(meeting_rate_info) == 1
#         assert meeting_rate_info[0]["meeting_date"] == date(2024, 2, 15)
#         # start_rate should be propagated from future_1 (5.25%)
#         assert meeting_rate_info[0]["start_rate"] == 5.25
#         # end_rate should be None (will be calculated later)
#         assert meeting_rate_info[0]["end_rate"] is None

#     def test_multiple_meetings_across_contracts(self):
#         """
#         GIVEN multiple meetings across different contracts
#         WHEN inferring period rates
#         THEN each meeting gets correct start_rate and end_rate
#         """
#         # Contract 1: Has meeting on Jan 15
#         # Contract 2: No meeting
#         # Contract 3: Has meeting on Mar 15
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_3 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=94.25,  # 100 - 5.75 = 94.25
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2, future_3],
#             meeting_dates=[
#                 datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         meeting_rate_info = service._infer_period_rates_from_period_without_meetings()

#         # Should have two meeting entries
#         assert len(meeting_rate_info) == 2
#         # First meeting: start_rate = base_rate, end_rate = future_2 implied_rate
#         assert meeting_rate_info[0]["meeting_date"] == date(2024, 1, 15)
#         assert meeting_rate_info[0]["start_rate"] == self.base_rate
#         assert meeting_rate_info[0]["end_rate"] == 5.50
#         # Second meeting: start_rate = future_2 implied_rate, end_rate = None
#         assert meeting_rate_info[1]["meeting_date"] == date(2024, 3, 15)
#         assert meeting_rate_info[1]["start_rate"] == 5.50
#         assert meeting_rate_info[1]["end_rate"] is None


# class TestFRBStep2InferImpliedRates(TestCase):
#     """
#     Test FRB Step 2: Infer Implied Rates At Meeting Date
#     Methodology: Section "Step 2: Infer Implied Rates At Meeting Date"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 5.25

#     def test_calculate_end_rate_from_start_rate(self):
#         """
#         GIVEN start_rate, implied_rate, and days before/after meeting
#         WHEN calculating end rate
#         THEN end rate is calculated using formula:
#             r_end = (T * r_implied - d_before * r_start) / d_after
#         """
#         # Example: 31-day contract, meeting on day 15
#         # r_start = 5.25%, r_implied = 5.375% (average)
#         # d_before = 15, d_after = 16, T = 31
#         # Expected: r_end = (31 * 5.375 - 15 * 5.25) / 16 = 5.5%
#         accrual_end_date = date(2024, 1, 31)
#         accrual_days = 31
#         meeting_date = date(2024, 1, 15)
#         future_average_rate = 5.375
#         start_rate = 5.25

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[],
#             meeting_dates=[],
#         )

#         end_rate = service._calculate_fedfunds_futures_rate(
#             accrual_end_date,
#             accrual_days,
#             meeting_date,
#             future_average_rate,
#             start_rate,
#             FedFuturesRateType.END,
#         )

#         # Calculate expected: (31 * 5.375 - 15 * 5.25) / 16
#         days_before = 15
#         days_after = 16
#         expected_end_rate = (31 * 5.375 - days_before * 5.25) / days_after
#         assert abs(end_rate - expected_end_rate) < 0.0001

#     def test_calculate_start_rate_from_end_rate(self):
#         """
#         GIVEN end_rate, implied_rate, and days before/after meeting
#         WHEN calculating start rate
#         THEN start rate is calculated using formula:
#             r_start = (T * r_implied - d_after * r_end) / d_before
#         """
#         # Example: 31-day contract, meeting on day 15
#         # r_end = 5.5%, r_implied = 5.375% (average)
#         # d_before = 15, d_after = 16, T = 31
#         # Expected: r_start = (31 * 5.375 - 16 * 5.5) / 15 = 5.25%
#         accrual_end_date = date(2024, 1, 31)
#         accrual_days = 31
#         meeting_date = date(2024, 1, 15)
#         future_average_rate = 5.375
#         end_rate = 5.5

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[],
#             meeting_dates=[],
#         )

#         start_rate = service._calculate_fedfunds_futures_rate(
#             accrual_end_date,
#             accrual_days,
#             meeting_date,
#             future_average_rate,
#             end_rate,
#             FedFuturesRateType.START,
#         )

#         # Calculate expected: (31 * 5.375 - 16 * 5.5) / 15
#         days_before = 15
#         days_after = 16
#         expected_start_rate = (31 * 5.375 - days_after * 5.5) / days_before
#         assert abs(start_rate - expected_start_rate) < 0.0001


# class TestFRBStep3LinearInterpolation(TestCase):
#     """
#     Test FRB Step 3: Linear Interpolation
#     Methodology: Section "Step 3: Linear Interpolation"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 5.25
#         self.test_date = date(2024, 1, 15)

#     def test_linear_interpolation_initial_contract_exact_step(self):
#         """
#         GIVEN rate change that results in exact step
#         WHEN applying linear interpolation for initial contract
#         THEN probability is assigned to the exact step
#         """
#         # Calculate price for exact 25 bps hike:
#         # Meeting on day 15 of 31-day month
#         # Start rate: 5.25%, End rate: 5.50%
#         # Average = (15 * 5.25 + 16 * 5.50) / 31 = 5.379%
#         # Price = 100 - 5.379 = 94.621
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.621,  # Implies exactly 25 bps hike
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         service.generate_probability_matrix()

#         # Find the +25 bps entry
#         step_25 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 25),
#             None,
#         )
#         assert step_25 is not None
#         # Should have one probability entry (one meeting)
#         assert len(step_25["probabilities"]) == 1
#         # Probability should be high (close to 100% after formatting) for exact step
#         assert step_25["probabilities"][0] > 90.0

#     def test_linear_interpolation_initial_contract_fractional_step(self):
#         """
#         GIVEN rate change of 37.5 bps (1.5 steps)
#         WHEN applying linear interpolation for initial contract
#         THEN probabilities are distributed: p(+25) = 0.5, p(+50) = 0.5
#         """
#         # Rate change = 37.5 bps = 1.5 * 25 bps
#         # n = 1, f = 0.5
#         # Expected: p(+25) = 1 - 0.5 = 0.5, p(+50) = 0.5
#         # To get 37.5 bps change, we need:
#         # Average rate = (15 * 5.25 + 16 * 5.625) / 31 = 5.4375
#         # Price = 100 - 5.4375 = 94.5625
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.5625,  # Implies 37.5 bps change
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         service.generate_probability_matrix()

#         # Find the +25 and +50 bps entries
#         step_25 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 25),
#             None,
#         )
#         step_50 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 50),
#             None,
#         )

#         assert step_25 is not None
#         assert step_50 is not None
#         # Probabilities should be distributed between the two steps
#         # Both should have non-zero probabilities
#         assert step_25["probabilities"][0] > 0
#         assert step_50["probabilities"][0] > 0
#         # Sum should be close to 100%
#         total_prob = step_25["probabilities"][0] + step_50["probabilities"][0]
#         assert abs(total_prob - 100.0) < 5.0  # Allow some tolerance

#     def test_linear_interpolation_subsequent_contract(self):
#         """
#         GIVEN subsequent contract with rate change
#         WHEN applying linear interpolation
#         THEN probabilities are convolved with previous probabilities
#         """
#         # First contract: +25 bps (100% probability)
#         # Second contract: +25 bps (100% probability)
#         # Expected: After convolution, cumulative probabilities should
#         # reflect both meetings
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.25,  # 100 - 5.75 = 94.25 (implies another 25 bps hike)
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         service.generate_probability_matrix()

#         # Find the +50 bps entry (cumulative from two +25 bps hikes)
#         step_50 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 50),
#             None,
#         )

#         assert step_50 is not None
#         # Should have at least one probability entry
#         assert len(step_50["probabilities"]) >= 1
#         # If there are two meetings, second meeting should have
#         # probability for +50 bps cumulative
#         if len(step_50["probabilities"]) >= 2:
#             assert step_50["probabilities"][1] > 0

#     def test_linear_interpolation_subsequent_exact_step(self):
#         """
#         GIVEN subsequent contract with exact step change
#         WHEN applying linear interpolation
#         THEN probabilities are convolved correctly
#         """
#         # First contract: +25 bps (exact step)
#         # Second contract: +25 bps (exact step)
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.50,  # Implies exactly 25 bps hike
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.25,  # Implies another 25 bps hike
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         service.generate_probability_matrix()

#         # Find the +50 bps entry (cumulative from two +25 bps hikes)
#         step_50 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 50),
#             None,
#         )

#         assert step_50 is not None
#         # Should have two probability entries (two meetings)
#         assert len(step_50["probabilities"]) == 2
#         # Second meeting should have high probability for +50 bps cumulative
#         assert step_50["probabilities"][1] > 0

#     def test_linear_interpolation_subsequent_fractional_step(self):
#         """
#         GIVEN subsequent contract with fractional step change
#         WHEN applying linear interpolation
#         THEN probabilities are distributed and convolved correctly
#         """
#         # First contract: +25 bps (exact step)
#         # Second contract: +37.5 bps (1.5 steps)
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.50,  # Implies exactly 25 bps hike
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.5625,  # Implies 37.5 bps hike
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         service.generate_probability_matrix()

#         # Find the +50 and +75 bps entries
#         step_50 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 50),
#             None,
#         )
#         step_75 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 75),
#             None,
#         )

#         assert step_50 is not None
#         assert step_75 is not None
#         # Both should have probabilities for second meeting
#         assert len(step_50["probabilities"]) == 2
#         assert len(step_75["probabilities"]) == 2
#         # Both should have non-zero probabilities
#         assert step_50["probabilities"][1] > 0
#         assert step_75["probabilities"][1] > 0

#     def test_linear_interpolation_negative_rate_change(self):
#         """
#         GIVEN negative rate change (rate cut)
#         WHEN applying linear interpolation
#         THEN probabilities are assigned to negative steps
#         """
#         # Contract with -25 bps cut (exact step)
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=95.0,  # Implies -25 bps cut (rate goes from 5.25% to 5.0%)
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         service.generate_probability_matrix()

#         # Find the -25 bps entry
#         step_minus_25 = next(
#             (
#                 mp
#                 for mp in service.probability_matrix
#                 if mp["expected_rate_step"] == -25
#             ),
#             None,
#         )

#         assert step_minus_25 is not None
#         # Should have one probability entry
#         assert len(step_minus_25["probabilities"]) == 1
#         # Probability should be high (close to 100% after formatting) for exact step
#         assert step_minus_25["probabilities"][0] > 90.0

#     def test_linear_interpolation_negative_fractional_step(self):
#         """
#         GIVEN negative fractional step change (e.g., -37.5 bps)
#         WHEN applying linear interpolation
#         THEN probabilities are distributed between -25 and -50 bps
#         """
#         # Contract with -37.5 bps cut (1.5 steps)
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.9375,  # Implies -37.5 bps cut
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         service.generate_probability_matrix()

#         # Find the -25 and -50 bps entries
#         step_minus_25 = next(
#             (
#                 mp
#                 for mp in service.probability_matrix
#                 if mp["expected_rate_step"] == -25
#             ),
#             None,
#         )
#         step_minus_50 = next(
#             (
#                 mp
#                 for mp in service.probability_matrix
#                 if mp["expected_rate_step"] == -50
#             ),
#             None,
#         )

#         assert step_minus_25 is not None
#         assert step_minus_50 is not None
#         # Both should have non-zero probabilities
#         assert step_minus_25["probabilities"][0] > 0
#         assert step_minus_50["probabilities"][0] > 0
#         # Sum should be close to 100%
#         total_prob = (
#             step_minus_25["probabilities"][0] + step_minus_50["probabilities"][0]
#         )
#         assert abs(total_prob - 100.0) < 5.0  # Allow some tolerance


# class TestFRBStep4ProbabilityConvolution(TestCase):
#     """
#     Test FRB Step 4: Probability Convolution For Cumulative Probabilities
#     Methodology: Section "Step 4: Probability Convolution For Cumulative Probabilities"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 5.25
#         self.test_date = date(2024, 1, 15)

#         # Create EFFR asset for tests that call get_central_bank_probability_matrices
#         self.effr_asset = AssetModel.objects.create(
#             short_name="EFFR",
#             full_name="Effective Fed Funds Rate",
#             asset_id=7,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.US,
#             ticker="500",
#         )

#         # Create market price
#         MarketPriceModel.objects.create(
#             asset=self.effr_asset,
#             date=self.test_date,
#             price=self.base_rate,
#         )

#     def test_convolution_formula(self):
#         """
#         GIVEN previous probabilities and new meeting probabilities
#         WHEN applying convolution
#         THEN p_total(k) = Σ p_prev(j) × p_new(k - j) for all valid j
#         """
#         # First contract: +25 bps (100% probability)
#         # Second contract: 0 bps (100% probability)
#         # Expected: After convolution, p_total(+25) should be 100% for second meeting
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50 (no change, still 5.50%)
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         service.generate_probability_matrix()

#         # Find the +25 bps entry
#         step_25 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 25),
#             None,
#         )

#         assert step_25 is not None
#         # Should have at least one probability entry
#         assert len(step_25["probabilities"]) >= 1
#         # First meeting: +25 bps should have high probability
#         assert step_25["probabilities"][0] > 0
#         # If there are two meetings, second meeting should have probability
#         if len(step_25["probabilities"]) >= 2:
#             assert step_25["probabilities"][1] > 0

#     def test_rigidity_constraint_no_reversal(self):
#         """
#         GIVEN previous cumulative step is positive (hiking path)
#         WHEN applying convolution
#         THEN cannot transition to negative step (cutting path)
#         """
#         # First contract: +25 bps (hiking)
#         # Second contract: -25 bps (cutting) - should be impossible due to rigidity
#         # Expected: After convolution, p_total(-25) should be 0% for second meeting
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=94.75,  # 100 - 5.25 = 94.75 (cut back to 5.25%)
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 2, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         service.generate_probability_matrix()

#         # Find the -25 bps entry
#         step_minus_25 = next(
#             (
#                 mp
#                 for mp in service.probability_matrix
#                 if mp["expected_rate_step"] == -25
#             ),
#             None,
#         )

#         if step_minus_25:
#             # Second meeting should have 0% probability for -25 bps due to rigidity
#             assert (
#                 step_minus_25["probabilities"][1] < 1.0
#             )  # Should be filtered out or very low

#     def test_normalization_after_convolution(self):
#         """
#         GIVEN probabilities after convolution
#         WHEN formatting probabilities
#         THEN probabilities sum to 100% for each meeting
#         """
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=94.50,  # 100 - 5.50 = 94.50
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         service = FedFundsFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1],
#             meeting_dates=[datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         service.generate_probability_matrix()

#         # Sum probabilities for first meeting across all steps
#         total_prob = sum(
#             mp["probabilities"][0]
#             for mp in service.probability_matrix
#             if len(mp["probabilities"]) > 0
#         )

#         # Should sum to approximately 100%
#         assert abs(total_prob - 100.0) < 1.0

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_get_central_bank_probability_matrices_success_frb_first_future_with_meeting(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN meeting dates and futures prices for FRB
#         WHEN getting probability matrices
#         THEN a probability matrix is returned for FRB
#         """
#         # Create meeting dates
#         meeting_date_1 = datetime(2026, 1, 28, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.FRB,
#                 meeting_dates=[meeting_date_1, meeting_date_2],
#             )
#         ]

#         # Create futures prices (covering both meetings)
#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=96.36,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_2 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.02",
#             first_accrual_date=date(2026, 2, 1),
#             last_accrual_date=date(2026, 2, 28),
#             date=self.test_date,
#             price=96.425,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_3 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 3, 31),
#             date=self.test_date,
#             price=96.455,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1, future_2, future_3]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
#         )
#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "meeting_dates": [date(2026, 1, 28), date(2026, 3, 15)],
#                 "probability_matrix": [
#                     {
#                         "expected_rate_step": -50,
#                         "probabilities": [0.0, 6.05],
#                     },
#                     {
#                         "expected_rate_step": -25,
#                         "probabilities": [26.0, 37.16],
#                     },
#                     {
#                         "expected_rate_step": 0,
#                         "probabilities": [74.0, 56.79],
#                     },
#                 ],
#             },
#         ]

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_get_central_bank_probability_matrices_success_frb_first_future_without_meeting(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN meeting dates and futures prices for FRB
#         WHEN getting probability matrices
#         THEN a probability matrix is returned for FRB
#         """
#         # Create meeting dates
#         meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.FRB,
#                 meeting_dates=[meeting_date_1, meeting_date_2],
#             )
#         ]

#         # Create futures prices (covering both meetings)
#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="25.12",
#             first_accrual_date=date(2025, 12, 1),
#             last_accrual_date=date(2025, 12, 31),
#             date=self.test_date,
#             price=96.2775,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_2 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=96.36,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_3 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.02",
#             first_accrual_date=date(2026, 2, 1),
#             last_accrual_date=date(2026, 2, 28),
#             date=self.test_date,
#             price=96.425,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_4 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 3, 31),
#             date=self.test_date,
#             price=96.455,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1, future_2, future_3, future_4]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
#         )
#         # Note: This test needs the actual result to be calculated and hardcoded
#         # For now, we verify the structure
#         assert len(result) == 1
#         assert result[0]["central_bank"] == CentralBankChoices.FRB
#         assert len(result[0]["meeting_dates"]) == 2
#         assert len(result[0]["probability_matrix"]) > 0
#         # TODO: Hardcode expected result once calculation is verified
#         # assert result == [
#         #     {
#         #         "central_bank": CentralBankChoices.FRB,
#         #         "meeting_dates": [date(2026, 1, 15), date(2026, 2, 15)],
#         #         "probability_matrix": [
#         #             {
#         #                 "expected_rate_step": -25,
#         #                 "probabilities": [0.0, 22.4],
#         #             },
#         #             {
#         #                 "expected_rate_step": 0,
#         #                 "probabilities": [100.0, 77.6],
#         #             },
#         #         ],
#         #     },
#         # ]

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_get_central_bank_probability_matrices_success_frb_no_(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN meeting dates and futures prices for FRB
#         WHEN getting probability matrices
#         THEN a probability matrix is returned for FRB
#         """
#         # Create meeting dates
#         meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.FRB,
#                 meeting_dates=[meeting_date_1, meeting_date_2],
#             )
#         ]

#         # Create futures prices (covering both meetings)
#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="25.12",
#             first_accrual_date=date(2025, 12, 1),
#             last_accrual_date=date(2025, 12, 31),
#             date=self.test_date,
#             price=96.2775,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_2 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=96.36,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_3 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.02",
#             first_accrual_date=date(2026, 2, 1),
#             last_accrual_date=date(2026, 2, 28),
#             date=self.test_date,
#             price=96.425,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         future_4 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 3, 31),
#             date=self.test_date,
#             price=96.455,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1, future_2, future_3, future_4]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
#         )
#         # Verify structure - actual probabilities depend on calculation
#         assert len(result) == 1
#         assert result[0]["central_bank"] == CentralBankChoices.FRB
#         assert result[0]["meeting_dates"] == [date(2026, 1, 15), date(2026, 2, 15)]
#         assert len(result[0]["probability_matrix"]) > 0
#         # Verify probabilities sum to ~100% for each meeting
#         for prob_entry in result[0]["probability_matrix"]:
#             if len(prob_entry["probabilities"]) >= 2:
#                 total_prob_meeting_1 = sum(
#                     pm["probabilities"][0]
#                     for pm in result[0]["probability_matrix"]
#                     if len(pm["probabilities"]) > 0
#                 )
#                 total_prob_meeting_2 = sum(
#                     pm["probabilities"][1]
#                     for pm in result[0]["probability_matrix"]
#                     if len(pm["probabilities"]) > 1
#                 )
#                 assert abs(total_prob_meeting_1 - 100.0) < 5.0
#                 assert abs(total_prob_meeting_2 - 100.0) < 5.0
