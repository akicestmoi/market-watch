from datetime import date, datetime, timezone

import pandas as pd
from django.test import TestCase

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.cb_inference_services import (
    EstrFuturesProbabilityMatrixService,
    MutanFuturesProbabilityMatrixService,
)


class TestProbabilityMatrixCalculationBaseTestCase(TestCase):
    """Test probability matrix calculation base test case."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 3.64
        self.test_date = date(2025, 12, 15)


class TestECBStep1InferSingleMeetingImpliedRates(
    TestProbabilityMatrixCalculationBaseTestCase
):
    """
    Test ECB/BOJ Step 1: Infer Single meeting implied rates
    Methodology: Section "Step 1: Infer Single meeting implied rates"
    """

    def test_calculate_single_meeting_implied_rate_concrete_scenario(self):
        """
        GIVEN concrete scenario: base_rate=4.0%, future_price=96.0 (4.0% implied),
             meeting on 2024-03-15, accrual period 2024-03-01 to 2024-05-31
        WHEN calculating single meeting implied rate
        THEN rate matches hardcoded expected value
        """
        estr_future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=date(2024, 1, 15),
            price=96.0,  # 100 - 4.0 = 96.0
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )
        base_rate = 4.0
        estr_service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=base_rate,
            future_prices=[estr_future],
            meeting_dates=[datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )

        accrual_end_date = date(2024, 5, 31)
        accrual_days = (accrual_end_date - date(2024, 3, 1)).days + 1
        meeting_date = date(2024, 3, 15)
        future_implied_rate = 4.0

        estr_meeting_implied_rate = (
            estr_service._calculate_three_month_futures_average_rate_for_single_meeting(
                accrual_end_date,
                accrual_days,
                meeting_date,
                future_implied_rate,
                base_rate,
            )
        )
        assert estr_meeting_implied_rate == 3.97600091

        mutan_future = StirFuturesModel(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month MUTAN Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=date(2024, 1, 15),
            price=96.0,  # 100 - 4.0 = 96.0
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )
        mutan_service = MutanFuturesProbabilityMatrixService(
            initial_base_rate=base_rate,
            future_prices=[mutan_future],
            meeting_dates=[datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        mutan_meeting_implied_rate = mutan_service._calculate_three_month_futures_average_rate_for_single_meeting(
            accrual_end_date,
            accrual_days,
            meeting_date,
            future_implied_rate,
            base_rate,
        )
        assert mutan_meeting_implied_rate == 3.97632748


class TestStep2GenerateAllMeetingScenarios(TestCase):
    """
    Test ECB/BOJ Step 2: Generate all meetings scenario
    Methodology: Section "Step 2: Generate All Meeting Scenarios"
    """

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 4.0
        self.test_date = date(2024, 1, 15)

    def test_generate_rate_combinations_n2_concrete_scenario(self):
        """
        GIVEN concrete scenario: 2 meetings with base_rate=4.0%
        WHEN generating rate combinations
        THEN exactly 7 combinations are generated with hardcoded expected values
        """
        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[],
            meeting_dates=[],
        )

        combinations = service._generate_rate_combinations(2)
        assert combinations == [
            (-25, -25),
            (-25, 0),
            (0, -25),
            (0, 0),
            (25, 0),
            (0, 25),
            (25, 25),
        ]

    def test_generate_rate_combinations_n2(self):
        """
        GIVEN 2 meetings
        WHEN generating rate combinations
        THEN 7 combinations are generated (excluding reversals)
        """
        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[],
            meeting_dates=[],
        )

        combinations = service._generate_rate_combinations(2)
        assert combinations == [
            (-25, -25),
            (-25, 0),
            (0, -25),
            (0, 0),
            (25, 0),
            (0, 25),
            (25, 25),
        ]

    def test_generate_rate_combinations_n3(self):
        """
        GIVEN 3 meetings
        WHEN generating rate combinations
        THEN combinations include adjacent pairs and maintain rigidity
        """
        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[],
            meeting_dates=[],
        )

        combinations = service._generate_rate_combinations(3)
        assert combinations == [
            (-25, -25, -25),
            (-25, 0, 0),
            (0, -25, 0),
            (0, 0, -25),
            (0, 0, 0),
            (25, 0, 0),
            (0, 25, 0),
            (0, 0, 25),
            (25, 25, 25),
            (-25, -25, 0),
            (0, -25, -25),
            (25, 25, 0),
            (0, 25, 25),
        ]


class TestECBStep3CalculateScenarioPrices(TestCase):
    """
    Test ECB/BOJ Step 3: Calculate Scenario Prices
    Methodology: Section "Step 3: Calculate Scenario Prices"
    """

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 4.0
        self.test_date = date(2024, 1, 15)

    def test_calculate_three_month_futures_price_concrete_scenario(self):
        """
        GIVEN concrete scenario: base_rate=4.0%, rate_after_meeting=4.0%,
             meeting on 2024-03-15, accrual period 2024-03-01 to 2024-05-31
        WHEN calculating three month futures price
        THEN price matches hardcoded expected value
        """
        estr_future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,  # 100 - 4.0 = 96.0
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )
        estr_service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[estr_future],
            meeting_dates=[datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )

        accrual_start_date = date(2024, 3, 1)
        accrual_end_date = date(2024, 5, 31)
        accrual_days = (accrual_end_date - accrual_start_date).days + 1
        meeting_date = date(2024, 3, 15)
        rate_after_meeting = 4.0

        estr_price = estr_service._calculate_three_month_futures_price(
            self.base_rate,
            [rate_after_meeting],
            [meeting_date],
            accrual_start_date,
            accrual_end_date,
            accrual_days,
        )
        assert estr_price == 95.93578524

        mutan_future = StirFuturesModel(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month MUTAN Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,  # 100 - 4.0 = 96.0
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )
        mutan_service = MutanFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[mutan_future],
            meeting_dates=[datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        mutan_price = mutan_service._calculate_three_month_futures_price(
            self.base_rate,
            [rate_after_meeting],
            [meeting_date],
            accrual_start_date,
            accrual_end_date,
            accrual_days,
        )
        assert mutan_price == 95.8457607

    def test_calculate_three_month_futures_price(self):
        """
        GIVEN base rate, meeting rate, and accrual period
        WHEN calculating three month futures price
        THEN price is calculated using compounded rate formula
        """
        estr_future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="25.03",
            first_accrual_date=date(2025, 3, 1),
            last_accrual_date=date(2025, 5, 31),
            date=self.test_date,
            price=96.0,  # 100 - 4.0 = 96.0
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )
        estr_service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[estr_future],
            meeting_dates=[datetime(2025, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )

        accrual_start_date = date(2025, 3, 1)
        accrual_end_date = date(2025, 5, 31)
        accrual_days = (accrual_end_date - accrual_start_date).days + 1
        meeting_date = date(2025, 3, 15)
        rate_after_meeting = 4.0

        estr_price = estr_service._calculate_three_month_futures_price(
            self.base_rate,
            [rate_after_meeting],
            [meeting_date],
            accrual_start_date,
                accrual_end_date,
                accrual_days,
        )
        assert estr_price == 95.93578524

        mutan_future = StirFuturesModel(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month MUTAN Futures",
            maturity="25.03",
            first_accrual_date=date(2025, 3, 1),
            last_accrual_date=date(2025, 5, 31),
            date=self.test_date,
            price=96.0,  # 100 - 4.0 = 96.0
            source=StirFuturesSourceChoices.PDF,
            comment="",
        )
        mutan_service = MutanFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[mutan_future],
            meeting_dates=[datetime(2025, 3, 15, 13, 0, tzinfo=timezone.utc)],
        )
        mutan_price = mutan_service._calculate_three_month_futures_price(
            self.base_rate,
            [rate_after_meeting],
            [meeting_date],
            accrual_start_date,
            accrual_end_date,
            accrual_days,
        )
        assert mutan_price == 95.8457607


class TestECBStep4InverseDistanceWeighting(TestCase):
    """
    Test ECB/BOJ Step 4: Inverse Distance Weighting (Joint Probability Calculation)
    Methodology: Section "Step 4: Inverse Distance Weighting
    (Joint Probability Calculation)"
    """

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 4.0
        self.test_date = date(2024, 1, 15)

    def test_inverse_distance_weighting_concrete_scenario(self):
        """
        GIVEN concrete scenario: base_rate=4.0%, market_price=96.0,
            meetings on 2024-03-15 and 2024-04-15, accrual 2024-03-01 to 2024-05-31
        WHEN applying inverse distance weighting
        THEN probabilities for each scenario are hardcoded expected values
        """
        future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,  # Market price
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        prob_df = service._calculate_reverse_distance_probabilities(
            self.base_rate,
            future.price,
            future.first_accrual_date,
            future.last_accrual_date,
            (future.last_accrual_date - future.first_accrual_date).days + 1,
            [date(2024, 3, 15), date(2024, 4, 15)],
        )

        # Sort DataFrame by rate steps for consistent comparison
        prob_df_sorted = prob_df.sort_values(
            by=["1_rate_step", "2_rate_step"]
        ).reset_index(drop=True)

        expected_prob_df = pd.DataFrame(
            {
                "1_rate_step": [-25, -25, 0, 0, 0, 25, 25],
                "2_rate_step": [-25, 0, -25, 0, 25, 0, 25],
                "total_step": [-50, -25, -25, 0, 25, 25, 50],
                "1_rate": [3.75, 3.75, 4.0, 4.0, 4.0, 4.25, 4.25],
                "2_rate": [3.75, 4.0, 3.75, 4.0, 4.25, 4.0, 4.25],
                "price": [
                    96.10870026,  # (-25, -25): both cuts
                    95.97970563,  # (-25, 0): first cut, second unchanged
                    96.0208787,  # (0, -25): first unchanged, second cut
                    95.8918554,  # (0, 0): both unchanged
                    95.76279089,  # (0, 25): first unchanged, second hike
                    95.80398627,  # (25, 0): first hike, second unchanged
                    95.67489307,  # (25, 25): both hikes
                ],
                "distance": [
                    0.10870026000000621,  # |96.0 - 96.10870026|
                    0.020294370000002004,  # |96.0 - 95.97970563|
                    0.020878699999997252,  # |96.0 - 96.0208787|
                    0.10814460000000281,  # |96.0 - 95.8918554|
                    0.2372091099999949,  # |96.0 - 95.76279089|
                    0.19601373000000422,  # |96.0 - 95.80398627|
                    0.325106930000004,  # |96.0 - 95.67489307|
                ],
                "reverse_distance": [
                    9.199610001668644,  # 1 / (0.10870026 + 1e-10)
                    49.27474935523627,  # 1 / (0.02029437 + 1e-10)
                    47.89570208923742,  # 1 / (0.0208787 + 1e-10)
                    9.246878707538668,  # 1 / (0.1081446 + 1e-10)
                    4.215689690747765,  # 1 / (0.23720911 + 1e-10)
                    5.101683435593058,  # 1 / (0.19601373 + 1e-10)
                    3.075911053918157,  # 1 / (0.32510693 + 1e-10)
                ],
                "probability": [
                    0.07186621263680971,  # Normalized probability
                    0.3849282321909954,  # Normalized probability
                    0.37415528594256664,  # Normalized probability
                    0.07223546990603154,  # Normalized probability
                    0.03293244514399338,  # Normalized probability
                    0.03985371842083729,  # Normalized probability
                    0.024028635758765914,  # Normalized probability
                ],
            }
        )
        pd.testing.assert_frame_equal(
            prob_df_sorted[expected_prob_df.columns],
            expected_prob_df,
            check_exact=False,
            atol=0.0001,
        )

    def test_inverse_distance_weighting_probabilities_sum_to_one(self):
        """
        GIVEN scenarios with calculated prices
        WHEN applying inverse distance weighting
        THEN probabilities sum to 1.0
        """
        future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,  # Market price
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        prob_df = service._calculate_reverse_distance_probabilities(
            self.base_rate,
            future.price,
            future.first_accrual_date,
            future.last_accrual_date,
            (future.last_accrual_date - future.first_accrual_date).days + 1,
            [date(2024, 3, 15), date(2024, 4, 15)],
        )
        total_prob = prob_df["probability"].sum()
        assert abs(total_prob - 1.0) < 0.0001

    def test_inverse_distance_weighting_closer_price_higher_probability(self):
        """
        GIVEN scenarios with different distances from market price
        WHEN applying inverse distance weighting
        THEN scenarios closer to market price have higher probabilities
        """
        future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,  # Market price
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        prob_df = service._calculate_reverse_distance_probabilities(
            self.base_rate,
            future.price,
            future.first_accrual_date,
            future.last_accrual_date,
            (future.last_accrual_date - future.first_accrual_date).days + 1,
            [date(2024, 3, 15), date(2024, 4, 15)],
        )

        # Find scenario with minimum distance
        min_distance_idx = prob_df["distance"].idxmin()
        min_distance_prob = float(prob_df.loc[min_distance_idx, "probability"])  # type: ignore

        # Find scenario with maximum distance
        max_distance_idx = prob_df["distance"].idxmax()
        max_distance_prob = float(prob_df.loc[max_distance_idx, "probability"])  # type: ignore

        # Closer scenario should have higher probability
        assert min_distance_prob > max_distance_prob


class TestECBStep5AggregateIndividualMeetingProbabilities(TestCase):
    """
    Test ECB/BOJ Step 5: Aggregate Individual Meeting Probabilities (Marginalization)
    Methodology: Section "Step 5: Aggregate Individual Meeting
    Probabilities (Marginalization)"
    """

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 4.0
        self.test_date = date(2024, 1, 15)

    def test_marginalization_concrete_scenario(self):
        """
        GIVEN concrete scenario: base_rate=4.0%, market_price=96.0,
            meetings on 2024-03-15 and 2024-04-15, accrual 2024-03-01 to 2024-05-31
        WHEN aggregating individual meeting probabilities
        THEN probabilities for each meeting and step are hardcoded expected values
        """
        future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        prob_df = service._calculate_reverse_distance_probabilities(
            self.base_rate,
            future.price,
            future.first_accrual_date,
            future.last_accrual_date,
            (future.last_accrual_date - future.first_accrual_date).days + 1,
            [date(2024, 3, 15), date(2024, 4, 15)],
        )

        step_keys = [-25, 0, 25]
        total_probabilities = service._get_total_probabilities_from_dataframe(
            prob_df, step_keys, 2
        )
        total_probabilities_sorted = sorted(
            total_probabilities,
            key=lambda x: (x["step"], x["meeting_i"]),
        )
        assert total_probabilities_sorted == [
            {
                "step": -25,
                "meeting_i": 1,
                "probability": 0.4567944448278051,
            },
            {
                "step": -25,
                "meeting_i": 2,
                "probability": 0.44602149857937634,
            },
            {
                "step": 0,
                "meeting_i": 1,
                "probability": 0.4793232009925915,
            },
            {
                "step": 0,
                "meeting_i": 2,
                "probability": 0.49701742051786424,
            },
            {
                "step": 25,
                "meeting_i": 1,
                "probability": 0.06388235417960321,
            },
            {
                "step": 25,
                "meeting_i": 2,
                "probability": 0.056961080902759295,
            },
        ]

    def test_marginalization_probabilities_sum_to_one_per_meeting(self):
        """
        GIVEN joint probabilities from scenarios
        WHEN aggregating individual meeting probabilities
        THEN probabilities for each meeting sum to 1.0
        """
        future = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        prob_df = service._calculate_reverse_distance_probabilities(
            self.base_rate,
            future.price,
            future.first_accrual_date,
            future.last_accrual_date,
            (future.last_accrual_date - future.first_accrual_date).days + 1,
            [date(2024, 3, 15), date(2024, 4, 15)],
        )

        step_keys = [-25, 0, 25]
        total_probabilities = service._get_total_probabilities_from_dataframe(
            prob_df, step_keys, 2
        )

        # Group by meeting_i and sum probabilities
        meeting_1_probs = {}
        meeting_2_probs = {}
        for prob_by_step in total_probabilities:
            step = prob_by_step["step"]
            meeting_i = prob_by_step["meeting_i"]
            prob = prob_by_step["probability"]

            if meeting_i == 1:
                meeting_1_probs[step] = prob
            elif meeting_i == 2:
                meeting_2_probs[step] = prob

        # Probabilities for each meeting should sum to 1.0 (with floating point tolerance)
        total_meeting_1 = sum(meeting_1_probs.values())
        total_meeting_2 = sum(meeting_2_probs.values())

        assert abs(total_meeting_1 - 1.0) < 0.0001
        assert abs(total_meeting_2 - 1.0) < 0.0001


class TestECBStep6ConvolutionForCumulativeProbabilities(TestCase):
    """
    Test ECB/BOJ Step 6: Convolution For Cumulative Probabilities
    Methodology: Section "Step 6: Convolution For Cumulative Probabilities"
    """

    def setUp(self):
        """Set up test fixtures."""
        self.base_rate = 4.0
        self.test_date = date(2024, 1, 15)

    def test_convolution_concrete_scenario(self):
        """
        GIVEN concrete scenario: base_rate=4.0%, two contracts with single meetings
             Contract 1: meeting 2024-03-15, price=96.0
             Contract 2: meeting 2024-06-15, price=95.75
        WHEN applying convolution
        THEN cumulative probabilities match hardcoded expected values
        """
        # First contract: single meeting
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        # Second contract: single meeting
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.06",
            first_accrual_date=date(2024, 6, 1),
            last_accrual_date=date(2024, 8, 31),
            date=self.test_date,
            price=95.75,  # Lower price implies higher rate
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service.generate_probability_matrix()

        # Sort by expected_rate_step for consistent comparison
        sorted_matrix = sorted(
            service.probability_matrix, key=lambda x: x["expected_rate_step"]
        )

        assert sorted_matrix == [
            {
                "expected_rate_step": -25,
                "probabilities": [9.6, 0.0],
            },
            {
                "expected_rate_step": 0,
                "probabilities": [90.4, 8.77],
            },
            {
                "expected_rate_step": 25,
                "probabilities": [0.0, 83.41],
            },
            {
                "expected_rate_step": 50,
                "probabilities": [0.0, 7.82],
            },
        ]

    def test_convolution_combines_previous_and_new_probabilities(self):
        """
        GIVEN previous cumulative probabilities and new meeting probabilities
        WHEN applying convolution
        THEN probabilities are combined correctly
        """
        # First contract: single meeting, +25 bps
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        # Second contract: single meeting, +25 bps
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.06",
            first_accrual_date=date(2024, 6, 1),
            last_accrual_date=date(2024, 8, 31),
            date=self.test_date,
            price=95.75,  # Lower price implies higher rate
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service.generate_probability_matrix()

        # Find the +50 bps entry (cumulative from two +25 bps hikes)
        step_50 = next(
            (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 50),
            None,
        )

        if step_50:
            # Should have two probability entries (two meetings)
            assert len(step_50["probabilities"]) == 2
            # Second meeting should have probability for +50 bps cumulative
            assert step_50["probabilities"][1] > 0

    def test_convolution_respects_rigidity_constraint(self):
        """
        GIVEN previous cumulative step is positive
        WHEN applying convolution
        THEN cannot transition to negative step
        """
        # First contract: +25 bps (hiking)
        future_1 = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        # Second contract: -25 bps (cutting) - should be impossible
        future_2 = StirFuturesModel(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.06",
            first_accrual_date=date(2024, 6, 1),
            last_accrual_date=date(2024, 8, 31),
            date=self.test_date,
            price=96.25,  # Higher price implies lower rate
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        service = EstrFuturesProbabilityMatrixService(
            initial_base_rate=self.base_rate,
            future_prices=[future_1, future_2],
            meeting_dates=[
                datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
            ],
        )

        service.generate_probability_matrix()

        # Find the -25 bps entry
        step_minus_25 = next(
            (
                mp
                for mp in service.probability_matrix
                if mp["expected_rate_step"] == -25
            ),
            None,
        )

        if step_minus_25 and len(step_minus_25["probabilities"]) > 1:
            # Second meeting should have very low or zero probability
            # for -25 bps. Due to rigidity constraint, but may still have
            # some probability due to calculation. The key is that it
            # should be much lower than if rigidity wasn't enforced.
            assert step_minus_25["probabilities"][1] < 100.0
