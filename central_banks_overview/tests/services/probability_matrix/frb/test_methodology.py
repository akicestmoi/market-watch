from datetime import date, datetime, timezone

import pytest  # type: ignore[reportMissingImports]
from django.test import TestCase

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.cb_inference_services import (
    FedFundsFuturesProbabilityMatrixService,
    FedFuturesRateType,
)


class TestProbabilityMatrixCalculationBaseTestCase(TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 3.64
        self.test_date = date(2025, 12, 15)
        self.future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.365,  # Implied rate = 3.635%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        self.future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.42,  # Implied rate = 3.58%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        self.future_3 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.test_date,
            price=96.455,  # Implied rate = 3.545%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        self.future_4 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.04",
            first_accrual_date=date(2026, 4, 1),
            last_accrual_date=date(2026, 4, 30),
            date=self.test_date,
            price=96.50,  # Implied rate = 3.50%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )


class TestStep0ValidateMeetingCoverage(TestProbabilityMatrixCalculationBaseTestCase):
    """
    Test FRB Step 0: Validate Meeting Coverage by Futures
    Methodology: Section "Step 0: Validate Meeting Coverage by Futures"
    """

    def test_validation_meeting_not_covered_by_future(self):
        """
        GIVEN a meeting date that falls outside all future accrual periods
        WHEN creating service
        THEN ValueError is raised
        """
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.365,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        with pytest.raises(ValueError) as exc_info:
            FedFundsFuturesProbabilityMatrixService(
                initial_base_rate=self.base_rate,
                future_prices=[future_1],
                meeting_dates=[datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)],
            )
        assert "is not covered by any future contract" in str(exc_info.value)

    def test_validation_last_meeting_no_future_after(self):
        """
        GIVEN last meeting without a future after it
        WHEN creating service
        THEN ValueError is raised
        """
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.365,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        with pytest.raises(ValueError) as exc_info:
            FedFundsFuturesProbabilityMatrixService(
                initial_base_rate=self.base_rate,
                future_prices=[future_1],
                meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
            )
        assert "requires a future contract after it to determine end_rate" in str(
            exc_info.value
        )

    def test_validation_future_success(self):
        """
        GIVEN requirements for future coverage are met
        WHEN creating service
        THEN no error is raised
        """
        # Future with meeting
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.365,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        # Future after meeting
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.42,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )
        assert service is not None


class TestStep1FillStartEndPrices(TestProbabilityMatrixCalculationBaseTestCase):
    """
    Test FRB Step 1: Fill Start/End Prices For Periods Without Meeting
    Methodology: Section "Step 1: Fill Start/End Prices For Periods Without Meeting"
    For a comprehensive test coverage, we need to test all possible combinations of
    meetings and futures contracts.
    Note that rates differential are not yet calculated at this step,
    and should always be None.
    """

    def test_combination_1_no_no_no(self):
        """
        GIVEN Combination 1: No meeting, No meeting, No meeting
        WHEN inferring period rates
        THEN no meeting_rate_info entries
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[],
        )

        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == []

    def test_combination_2_no_no_yes(self):
        """
        GIVEN Combination 2: No meeting, No meeting, Meeting
        WHEN inferring period rates
        THEN meeting has start_rate from second contract's implied_rate
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": 3.58,
                "end_rate": 3.5,
                "rate_diff": None,
            }
        ]

    def test_combination_3_no_yes_no(self):
        """
        GIVEN Combination 3: No meeting, Meeting, No meeting
        WHEN inferring period rates
        THEN meeting has start_rate from first contract and end_rate from third
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": 3.635,
                "end_rate": 3.545,
                "rate_diff": None,
            }
        ]

    def test_combination_4_no_yes_yes(self):
        """
        GIVEN Combination 4: No meeting, Meeting, Meeting
        WHEN inferring period rates
        THEN both meetings get correct start_rate and end_rate
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": 3.635,
                "end_rate": None,
                "rate_diff": None,
            },
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": None,
                "end_rate": 3.50,
                "rate_diff": None,
            },
        ]

    def test_combination_5_yes_no_no(self):
        """
        GIVEN Combination 5: Meeting, No meeting, No meeting
        WHEN inferring period rates
        THEN meeting has start_rate from base_rate and end_rate from second contract
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )

        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": self.base_rate,
                "end_rate": 3.58,
                "rate_diff": None,
            }
        ]

    def test_combination_6_yes_no_yes(self):
        """
        GIVEN Combination 6: Meeting, No meeting, Meeting
        WHEN inferring period rates
        THEN both meetings get correct start_rate and end_rate
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": self.base_rate,
                "end_rate": 3.58,
                "rate_diff": None,
            },
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": 3.58,
                "end_rate": 3.50,
                "rate_diff": None,
            },
        ]

    def test_combination_7_yes_yes_no(self):
        """
        GIVEN Combination 7: Meeting, Meeting, No meeting
        WHEN inferring period rates
        THEN both meetings get correct start_rate and end_rate
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": self.base_rate,
                "end_rate": None,
                "rate_diff": None,
            },
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": None,
                "end_rate": 3.545,
                "rate_diff": None,
            },
        ]

    def test_combination_8_yes_yes_yes(self):
        """
        GIVEN Combination 8: Meeting, Meeting, Meeting
        WHEN inferring period rates
        THEN all meetings get correct start_rate and end_rate
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._infer_period_rates_from_period_without_meetings()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": self.base_rate,
                "end_rate": None,
                "rate_diff": None,
            },
            # The second meeting start_rate should use the inferred end_rate
            # of the first meeting after calculation.
            # The second meeting end_rate should use the inferred start_rate
            # of the next meeting after calculation.
            # These will be filled after inferrence calculation
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": None,
                "end_rate": None,
                "rate_diff": None,
            },
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": None,
                "end_rate": 3.50,
                "rate_diff": None,
            },
        ]


class TestFRBStep2InferImpliedRates(TestProbabilityMatrixCalculationBaseTestCase):
    """
    Test FRB Step 2: Infer Implied Rates At Meeting Date
    Methodology: Section "Step 2: Infer Implied Rates At Meeting Date"
    """

    def test_calculate_end_rate_from_start_rate(self):
        """
        GIVEN start_rate, implied_rate, and days before/after meeting
        WHEN calculating end rate
        THEN end rate is calculated using formula:
            r_end = (T * r_implied - d_before * r_start) / d_after
        """
        # Example: 31-day contract, meeting on day 18
        # r_start = 3.7225%, r_implied = 3.64% (average)
        # d_before = 18, d_after = 16, T = 31
        # Expected: r_end = (31 * 3.64 - 18 * 3.7225) / 13
        accrual_end_date = date(2026, 3, 31)
        accrual_days = 31
        meeting_date = date(2026, 3, 18)
        future_average_rate = 3.64
        start_rate = 3.7225

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[],
            meeting_dates=[],
        )

        end_rate = service._calculate_fedfunds_futures_rate(
            accrual_end_date,
            accrual_days,
            meeting_date,
            future_average_rate,
            start_rate,
            FedFuturesRateType.END,
        )

        days_before = 18
        days_after = 13
        expected_end_rate = (31 * 3.64 - days_before * 3.7225) / days_after
        assert abs(end_rate - expected_end_rate) < 0.0001

    def test_calculate_start_rate_from_end_rate(self):
        """
        GIVEN end_rate, implied_rate, and days before/after meeting
        WHEN calculating start rate
        THEN start rate is calculated using formula:
            r_start = (T * r_implied - d_after * r_end) / d_before
        """
        # Example: 31-day contract, meeting on day 18
        # r_end = 3.58%, r_implied = 3.64% (average)
        # d_before = 18, d_after = 16, T = 31
        # Expected: r_start = (31 * 3.64 - 13 * 3.58) / 18
        accrual_end_date = date(2026, 3, 31)
        accrual_days = 31
        meeting_date = date(2026, 3, 18)
        future_average_rate = 3.64
        end_rate = 3.58

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[],
            meeting_dates=[],
        )

        start_rate = service._calculate_fedfunds_futures_rate(
            accrual_end_date,
            accrual_days,
            meeting_date,
            future_average_rate,
            end_rate,
            FedFuturesRateType.START,
        )

        # Calculate expected: (31 * 3.64 - 13 * 3.58) / 18
        days_before = 18
        days_after = 13
        expected_start_rate = (31 * 3.64 - days_after * 3.58) / days_before
        assert abs(start_rate - expected_start_rate) < 0.0001

    def test_combination_1_no_no_no(self):
        """
        GIVEN Combination 1: No meeting, No meeting, No meeting
        WHEN calculating meeting rate changes
        THEN no rate changes are returned
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[],
        )
        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == []

    def test_combination_2_no_no_yes(self):
        """
        GIVEN Combination 2: No meeting, No meeting, Meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": 3.593,
                "end_rate": 3.5,
                "rate_diff": -0.09299999999999997,
            }
        ]

    def test_combination_3_no_yes_no(self):
        """
        GIVEN Combination 3: No meeting, Meeting, No meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)],
        )

        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": 3.610333333333333,
                "end_rate": 3.545,
                "rate_diff": -0.06533333333333324,
            }
        ]

    def test_combination_4_no_yes_yes(self):
        """
        GIVEN Combination 4: No meeting, Meeting, Meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": 3.635,
                "end_rate": 3.516538461538462,
                "rate_diff": -0.11846153846153795,
            },
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": 3.593,
                "end_rate": 3.5,
                "rate_diff": -0.09299999999999997,
            },
        ]

    def test_combination_5_yes_no_no(self):
        """
        GIVEN Combination 5: Meeting, No meeting, No meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": 3.693666666666666,
                "end_rate": 3.58,
                "rate_diff": -0.11366666666666614,
            }
        ]

    def test_combination_6_yes_no_yes(self):
        """
        GIVEN Combination 6: Meeting, No meeting, Meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": 3.693666666666666,
                "end_rate": 3.58,
                "rate_diff": -0.11366666666666614,
            },
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": 3.593,
                "end_rate": 3.5,
                "rate_diff": -0.09299999999999997,
            },
        ]

    def test_combination_7_yes_yes_no(self):
        """
        GIVEN Combination 7: Meeting, Meeting, No meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": 3.64,
                "end_rate": 3.630312499999999,
                "rate_diff": -0.00968750000000096,
            },
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": 3.610333333333333,
                "end_rate": 3.545,
                "rate_diff": -0.06533333333333324,
            },
        ]

    def test_combination_8_yes_yes_yes(self):
        """
        GIVEN Combination 8: Meeting, Meeting, Meeting
        WHEN calculating meeting rate changes
        THEN rate_diff is calculated correctly for meetings with both rates
        Note: The middle meeting may not have both rates calculated if
        it's between two meetings in the same contract
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service._calculate_meeting_rate_changes()
        assert service.meeting_rate_info == [
            {
                "meeting_date": date(2026, 1, 15),
                "start_rate": 3.64,
                "end_rate": 3.630312499999999,
                "rate_diff": -0.00968750000000096,
            },
            {
                "meeting_date": date(2026, 2, 15),
                "start_rate": 3.5687333333333333,
                "end_rate": 3.593,
                "rate_diff": 0.02426666666666666,
            },
            {
                "meeting_date": date(2026, 3, 15),
                "start_rate": 3.593,
                "end_rate": 3.5,
                "rate_diff": -0.09299999999999997,
            },
        ]


class TestFRBStep3LinearInterpolation(TestProbabilityMatrixCalculationBaseTestCase):
    """
    Test FRB Step 3: Linear Interpolation
    Methodology: Section "Step 3: Linear Interpolation"
    This step returns a probability matrix before applying convolution.
    However, it is not used in the final probability matrix as convolution is vectorized;
    this step is only used for testing.
    """

    def test_linear_interpolation_initial_contract_exact_step(self):
        """
        GIVEN rate change that results in exact step
        WHEN applying linear interpolation for initial contract
        THEN probability is assigned to the exact step
        """
        # Price combination that produces ~+25 bps hike
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.055,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=95.935,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )

        service.generate_probability_matrix()
        assert service.probability_matrix == [
            {
                "expected_rate_step": 25,
                "probabilities": [99.2],
            }
        ]

    def test_linear_interpolation_initial_contract_fractional_step(self):
        """
        GIVEN rate change of 37.5 bps (1.5 steps)
        WHEN applying linear interpolation for initial contract
        THEN probabilities are distributed: p(+25) = 0.5, p(+50) = 0.5
        """
        # Price combination that produces ~+37.5 bps change
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=95.945,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=95.765,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )

        service.generate_probability_matrix()
        assert service.probability_matrix == [
            {
                "expected_rate_step": 25,
                "probabilities": [51.2],
            },
            {
                "expected_rate_step": 50,
                "probabilities": [48.8],
            },
        ]

    def test_linear_interpolation_no_rate_change(self):
        """
        GIVEN futures price that implies no rate change from base rate
        WHEN applying linear interpolation
        THEN probabilities are assigned to step 0 (no change)
        """
        # Price combination that produces 0 bps (no change)
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.300,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.300,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )

        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": 0,
                "probabilities": [100.0],
            }
        ]

    def test_linear_interpolation_negative_fractional_step(self):
        """
        GIVEN negative fractional step change (e.g., -37.5 bps)
        WHEN applying linear interpolation
        THEN probabilities are distributed between -25 and -50 bps
        """
        # Price combination that produces ~-37.5 bps cut
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.500,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.680,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )

        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -50,
                "probabilities": [48.8],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [51.2],
            },
        ]

    def test_linear_interpolation_subsequent_contract(self):
        """
        GIVEN two meetings where the second meeting's probabilities depend on the first
        WHEN applying linear interpolation WITHOUT convolution
        THEN probabilities are calculated independently based on futures prices

        This test verifies that when apply_convolution=False:
        - Meeting 1 probabilities are calculated from future_1 price
        - Meeting 2 probabilities are calculated from future_2 price
        - Probabilities are NOT convolved (each meeting's probabilities are independent)
        """
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.055,  # Produces probabilities for meeting 1
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.155,  # Produces probabilities for meeting 2 (relative to meeting 1's end rate)
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_3 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.test_date,
            price=96.455,  # Future after last meeting (required for validation)
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2, future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service.generate_probability_matrix(apply_convolution=False)
        result = service.probability_matrix

        # Verify structure: Each entry has probabilities for both meetings
        # meeting1_prob is at index 0, meeting2_prob is at index 1
        for entry in result:
            assert len(entry["probabilities"]) == 2, (
                f"Each entry should have probabilities for 2 meetings, "
                f"but found {len(entry['probabilities'])}"
            )

        # Verify the actual probabilities
        assert result == [
            {
                "expected_rate_step": -75,
                "probabilities": [0.0, 24.0],
            },
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 76.0],
            },
            {
                "expected_rate_step": 50,
                "probabilities": [63.63, 0.0],
            },
            {
                "expected_rate_step": 75,
                "probabilities": [36.37, 0.0],
            },
        ]

    def test_linear_interpolation_subsequent_exact_step(self):
        """
        GIVEN two meetings where both result in exact step changes (multiples of 25 bps)
        WHEN applying linear interpolation WITHOUT convolution
        THEN probabilities are assigned 100% to the exact step for each meeting

        This test verifies exact step handling for subsequent meetings:
        - Meeting 1: Exact step (+50 bps) → 100% probability at step +50
        - Meeting 2: Exact step (-25 bps) → 100% probability at step -25

        When rate changes are exact multiples of 25 bps, all probability is assigned
        to that single step (no distribution across adjacent steps).
        """
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.102,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.008,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_3 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.test_date,
            price=96.142,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2, future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [
                    0.0,
                    99.95,
                ],
            },
            {
                "expected_rate_step": 50,
                "probabilities": [
                    99.95,
                    0.0,
                ],
            },
        ]

    def test_linear_interpolation_subsequent_fractional_step(self):
        """
        GIVEN two meetings where both have fractional step changes
        WHEN applying linear interpolation WITHOUT convolution
        THEN probabilities are distributed across adjacent steps

        This test verifies fractional step handling for subsequent meetings:
        - Meeting 1: Fractional step distributed between +50 and +75 bps steps
        - Meeting 2: Fractional step with 50/50 distribution between -75 and -50 bps steps
          (probabilities: ~50% at -75, ~50% at -50)

        The probabilities for meeting 2 are calculated relative to meeting 1's end rate,
        not cumulative from the base rate. The 50/50 distribution demonstrates how
        fractional steps are evenly split between adjacent standard steps.
        """
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.000,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.000,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_3 = StirFuturesModel(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.test_date,
            price=96.335,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2, future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -75,
                "probabilities": [0.0, 50.13],
            },
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 49.87],
            },
            {
                "expected_rate_step": 50,
                "probabilities": [21.0, 0.0],
            },
            {
                "expected_rate_step": 75,
                "probabilities": [79.0, 0.0],
            },
        ]

    def test_combination_1_no_no_no(self):
        """
        GIVEN Combination 1: No meeting, No meeting, No meeting
        WHEN generating probability matrix
        THEN no probability matrix is generated (no meetings)
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == []

    def test_combination_2_no_no_yes(self):
        """
        GIVEN Combination 2: No meeting, No meeting, Meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for the meeting
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [37.2],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [62.8],
            },
        ]

    def test_combination_3_no_yes_no(self):
        """
        GIVEN Combination 3: No meeting, Meeting, No meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for the meeting
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [26.13],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [73.87],
            },
        ]

    def test_combination_4_no_yes_yes(self):
        """
        GIVEN Combination 4: No meeting, Meeting, Meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [47.38, 37.2],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [52.62, 62.8],
            },
        ]

    def test_combination_5_yes_no_no(self):
        """
        GIVEN Combination 5: Meeting, No meeting, No meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for the meeting
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [45.47],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [54.53],
            },
        ]

    def test_combination_6_yes_no_yes(self):
        """
        GIVEN Combination 6: Meeting, No meeting, Meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [45.47, 37.2],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [54.53, 62.8],
            },
        ]

    def test_combination_7_yes_yes_no(self):
        """
        GIVEN Combination 7: Meeting, Meeting, No meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [3.88, 26.13],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [96.12, 73.87],
            },
        ]

    def test_combination_8_yes_yes_yes(self):
        """
        GIVEN Combination 8: Meeting, Meeting, Meeting
        WHEN generating probability matrix
        THEN probability matrix is generated for all three meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=False)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [3.88, 0.0, 37.2],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [96.12, 90.29, 62.8],
            },
            {
                "expected_rate_step": 25,
                "probabilities": [0.0, 9.71, 0.0],
            },
        ]


class TestFRBStep4ProbabilityConvolution(TestProbabilityMatrixCalculationBaseTestCase):
    """
    Test FRB Step 4: Probability Convolution For Cumulative Probabilities
    Methodology: Section "Step 4: Probability Convolution For Cumulative Probabilities"
    """

    def test_convolution_formula_without_formatting(self):
        """
        GIVEN two meetings with specific probability distributions
        WHEN applying convolution formula p_total(k) = Σ p_prev(j) x p_new(k - j)
        THEN the convolved probabilities match explicit mathematical calculation

        This tests also allows to verify the rigidity constraints:
        convolutions of probabilities cannot be calculated based on meetings
        which has different direction of rate changes.
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=False)
        result_without_convolution = service.probability_matrix
        assert result_without_convolution == [
            {
                "expected_rate_step": -25,
                "probabilities": [3.88, 26.13],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [96.12, 73.87],
            },
        ]

        # Extract probabilities explicitly
        p_prev_unchanged = 0.9612499999999962
        p_prev_minus25 = 0.03875000000000384
        p_new_unchanged = 0.738666666666667
        p_new_minus25 = 0.261333333333333
        # Calculate convolution explicitly using formula:
        # p_total(k) = Σ p_prev(j) × p_new(k - j)
        # where k is the cumulative step and j is meeting 1's step
        # Meeting 2 probabilities are relative to meeting 1's end rate
        # If meeting 1 is +25 and meeting 2 is -50 relative, cumulative is -25
        # If meeting 1 is +25 and meeting 2 is -25 relative, cumulative is 0
        #
        # p_total(-50) = p_prev(-25) × p_new(-25) = 1.01%
        # p_total(-25) = p_prev(0) × p_new(-25) + p_prev(+25) × p_new(0) = 27.98%
        # p_total(0) = p_prev(+25) × p_new(-25) = 71.00%
        expected_p_total_minus50 = p_prev_minus25 * p_new_minus25
        expected_p_total_minus25 = (
            p_prev_unchanged * p_new_minus25 + p_prev_minus25 * p_new_unchanged
        )
        expected_p_total_0 = p_prev_unchanged * p_new_unchanged

        expected_probability_matrix = [
            {
                "expected_rate_step": -75,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, expected_p_total_minus50],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [
                    p_prev_minus25,
                    expected_p_total_minus25,
                ],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [
                    p_prev_unchanged,
                    expected_p_total_0,
                ],
            },
            {
                "expected_rate_step": 25,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 50,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 75,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": -100,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": -125,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": -150,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": -175,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": -200,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 100,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 125,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 150,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 175,
                "probabilities": [0.0, 0.0],
            },
            {
                "expected_rate_step": 200,
                "probabilities": [0.0, 0.0],
            },
        ]
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(
            apply_convolution=True, format_probabilities=False
        )
        result_with_convolution = service.probability_matrix
        assert result_with_convolution == expected_probability_matrix

    def test_convolution_formula_with_formatting(self):
        """
        GIVEN two meetings with specific probability distributions
        WHEN applying convolution formula p_total(k) = Σ p_prev(j) x p_new(k - j)
        THEN the convolved probabilities match explicit mathematical calculation

        This test also allows to verify the formatting of probabilities:
        1. Converts probabilities from decimals to percentages (multiply by 100)
        2. Rounds to 2 decimal places
        3. Filters out entries below PROBABILITY_THRESHOLD
        4. Ensures probabilities sum to 100% for each meeting
        """
        p_prev_unchanged = 0.9612499999999962
        p_prev_minus25 = 0.03875000000000384
        p_new_unchanged = 0.738666666666667
        p_new_minus25 = 0.261333333333333
        expected_p_total_minus50 = p_prev_minus25 * p_new_minus25
        expected_p_total_minus25 = (
            p_prev_unchanged * p_new_minus25 + p_prev_minus25 * p_new_unchanged
        )
        expected_p_total_0 = p_prev_unchanged * p_new_unchanged
        expected_probability_matrix = [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, round(expected_p_total_minus50 * 100, 2)],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [
                    round(p_prev_minus25 * 100, 2),
                    round(expected_p_total_minus25 * 100, 2),
                ],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [
                    round(p_prev_unchanged * 100, 2),
                    round(expected_p_total_0 * 100, 2),
                ],
            },
        ]

        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(
            apply_convolution=True, format_probabilities=True
        )
        result_with_convolution = service.probability_matrix
        assert result_with_convolution == expected_probability_matrix

    def test_combination_1_no_no_no(self):
        """
        GIVEN Combination 1: No meeting, No meeting, No meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is empty (no meetings)
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[],
        )
        service.generate_probability_matrix(apply_convolution=True)
        assert service.probability_matrix == []

    def test_combination_2_no_no_yes(self):
        """
        GIVEN Combination 2: No meeting, No meeting, Meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for the meeting
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service.generate_probability_matrix(apply_convolution=True)
        # Single meeting - same as Step 3 (no convolution effect)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [37.2],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [62.8],
            },
        ]

    def test_combination_3_no_yes_no(self):
        """
        GIVEN Combination 3: No meeting, Meeting, No meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for the meeting
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service.generate_probability_matrix(apply_convolution=True)
        # Single meeting - same as Step 3 (no convolution effect)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [26.13],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [73.87],
            },
        ]

    def test_combination_4_no_yes_yes(self):
        """
        GIVEN Combination 4: No meeting, Meeting, Meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=True)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 17.63],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [47.38, 49.33],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [52.62, 33.04],
            },
        ]

    def test_combination_5_yes_no_no(self):
        """
        GIVEN Combination 5: Meeting, No meeting, No meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for the meeting
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
        )
        service.generate_probability_matrix(apply_convolution=True)
        # Single meeting - same as Step 3 (no convolution effect)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [45.47],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [54.53],
            },
        ]

    def test_combination_6_yes_no_yes(self):
        """
        GIVEN Combination 6: Meeting, No meeting, Meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=True)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 16.91],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [45.47, 48.84],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [54.53, 34.25],
            },
        ]

    def test_combination_7_yes_yes_no(self):
        """
        GIVEN Combination 7: Meeting, Meeting, No meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for both meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=True)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 1.01],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [3.88, 27.98],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [96.12, 71.0],
            },
        ]

    def test_combination_8_yes_yes_yes(self):
        """
        GIVEN Combination 8: Meeting, Meeting, Meeting
        WHEN generating probability matrix with convolution
        THEN probability matrix is generated for all three meetings
        """
        service = FedFundsFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[self.future_1, self.future_2, self.future_3, self.future_4],
            meeting_dates=[
                datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )
        service.generate_probability_matrix(apply_convolution=True)
        assert service.probability_matrix == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 0.0, 1.3],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [3.88, 3.5, 34.62],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [96.12, 87.17, 58.21],
            },
            {
                "expected_rate_step": 25,
                "probabilities": [0.0, 9.33, 5.86],
            },
        ]
        assert service.probability_matrix == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 0.0, 1.3],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [3.88, 3.5, 34.62],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [96.12, 87.17, 58.21],
            },
            {
                "expected_rate_step": 25,
                "probabilities": [0.0, 9.33, 5.86],
            },
        ]
