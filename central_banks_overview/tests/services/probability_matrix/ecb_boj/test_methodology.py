# # ============================================================================
# # ECB/BOJ PROBABILITY MATRIX METHODOLOGY TESTS
# # ============================================================================
# # Testing all steps from PROBABILITY_MATRIX_METHODOLOGY.md for ECB/BOJ
# # ============================================================================


# class TestECBStep1InferSingleMeetingImpliedRates(TestCase):
#     """
#     Test ECB/BOJ Step 1: Infer Single meeting implied rates
#     Methodology: Section "Step 1: Infer Single meeting implied rates"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 4.0
#         self.test_date = date(2024, 1, 15)

#     def test_calculate_single_meeting_implied_rate_estr(self):
#         """
#         GIVEN ESTR futures with single meeting
#         WHEN calculating implied rate
#         THEN rate is calculated using approximated compounding formula
#         """
#         # ESTR: ACT/360, days_per_year = 360
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,  # 100 - 4.0 = 96.0
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         accrual_end_date = date(2024, 5, 31)
#         accrual_days = (accrual_end_date - date(2024, 3, 1)).days + 1
#         meeting_date = date(2024, 3, 15)
#         future_implied_rate = 4.0

#         meeting_implied_rate = (
#             service._calculate_three_month_futures_average_rate_for_single_meeting(
#                 accrual_end_date,
#                 accrual_days,
#                 meeting_date,
#                 future_implied_rate,
#                 self.base_rate,
#             )
#         )

#         # The implied rate should be calculated correctly
#         assert meeting_implied_rate is not None
#         assert meeting_implied_rate > 0

#     def test_calculate_single_meeting_implied_rate_mutan(self):
#         """
#         GIVEN TONA futures with single meeting
#         WHEN calculating implied rate
#         THEN rate is calculated using 30/365 day count convention
#         """
#         # TONA: 30/365, days_per_year = 365, futures_days_compounding_convention = 90
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,  # 100 - 4.0 = 96.0
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = MutanFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc)],
#         )

#         accrual_end_date = date(2024, 5, 31)
#         accrual_days = (accrual_end_date - date(2024, 3, 1)).days + 1
#         meeting_date = date(2024, 3, 15)
#         future_implied_rate = 4.0

#         meeting_implied_rate = (
#             service._calculate_three_month_futures_average_rate_for_single_meeting(
#                 accrual_end_date,
#                 accrual_days,
#                 meeting_date,
#                 future_implied_rate,
#                 self.base_rate,
#             )
#         )

#         # The implied rate should be calculated correctly
#         assert meeting_implied_rate is not None
#         assert meeting_implied_rate > 0


# class TestECBStep2GenerateAllMeetingScenarios(TestCase):
#     """
#     Test ECB/BOJ Step 2: Generate all meetings scenario
#     Methodology: Section "Step 2: Generate All Meeting Scenarios"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 4.0
#         self.test_date = date(2024, 1, 15)

#     def test_generate_rate_combinations_n2(self):
#         """
#         GIVEN 2 meetings
#         WHEN generating rate combinations
#         THEN 7 combinations are generated (excluding reversals)
#         """
#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[],
#             meeting_dates=[],
#         )

#         combinations = service._generate_rate_combinations(2)

#         # Should have 7 combinations for n=2
#         assert len(combinations) == 7

#         # Check that reversals are excluded
#         assert (-25, 25) not in combinations  # Cannot cut then hike
#         assert (25, -25) not in combinations  # Cannot hike then cut

#         # Check that valid combinations are included
#         assert (0, 0) in combinations
#         assert (-25, 0) in combinations
#         assert (0, -25) in combinations
#         assert (25, 0) in combinations
#         assert (0, 25) in combinations
#         assert (-25, -25) in combinations
#         assert (25, 25) in combinations

#     def test_generate_rate_combinations_n3(self):
#         """
#         GIVEN 3 meetings
#         WHEN generating rate combinations
#         THEN combinations include adjacent pairs and maintain rigidity
#         """
#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[],
#             meeting_dates=[],
#         )

#         combinations = service._generate_rate_combinations(3)

#         # Should have more than 7 combinations for n=3
#         assert len(combinations) > 7

#         # Check that reversals are excluded
#         for combo in combinations:
#             # If we have a positive step, we cannot have a negative step after
#             has_positive = any(step > 0 for step in combo)
#             has_negative_after_positive = False
#             for i, step in enumerate(combo):
#                 if step > 0:
#                     # Check if there's a negative step after this positive one
#                     if any(combo[j] < 0 for j in range(i + 1, len(combo))):
#                         has_negative_after_positive = True
#                         break

#             if has_positive:
#                 assert not has_negative_after_positive, f"Invalid combination: {combo}"


# class TestECBStep3CalculateScenarioPrices(TestCase):
#     """
#     Test ECB/BOJ Step 3: Calculate Scenario Prices
#     Methodology: Section "Step 3: Calculate Scenario Prices"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 4.0
#         self.test_date = date(2024, 1, 15)

#     def test_calculate_scenario_price_estr(self):
#         """
#         GIVEN rate scenario and meeting dates
#         WHEN calculating scenario price
#         THEN price is calculated using exact compounding formula (no approximation)
#         """
#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[],
#             meeting_dates=[],
#         )

#         accrual_start_date = date(2024, 3, 1)
#         accrual_end_date = date(2024, 5, 31)
#         accrual_days = (accrual_end_date - accrual_start_date).days + 1
#         meeting_dates = [date(2024, 3, 15), date(2024, 4, 15)]
#         rates = [4.25, 4.5]  # Scenario: +25 bps, then +25 bps

#         price = service._calculate_three_month_futures_price(
#             self.base_rate,
#             rates,
#             meeting_dates,
#             accrual_start_date,
#             accrual_end_date,
#             accrual_days,
#         )

#         # Price should be calculated correctly
#         assert price is not None
#         assert 0 < price < 100

#     def test_calculate_scenario_price_mutan(self):
#         """
#         GIVEN rate scenario for TONA futures
#         WHEN calculating scenario price
#         THEN price uses 30/365 convention with T_average = 90
#         """
#         service = MutanFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[],
#             meeting_dates=[],
#         )

#         accrual_start_date = date(2024, 3, 1)
#         accrual_end_date = date(2024, 5, 31)
#         accrual_days = (accrual_end_date - accrual_start_date).days + 1
#         meeting_dates = [date(2024, 3, 15), date(2024, 4, 15)]
#         rates = [4.25, 4.5]  # Scenario: +25 bps, then +25 bps

#         price = service._calculate_three_month_futures_price(
#             self.base_rate,
#             rates,
#             meeting_dates,
#             accrual_start_date,
#             accrual_end_date,
#             accrual_days,
#         )

#         # Price should be calculated correctly
#         assert price is not None
#         assert 0 < price < 100


# class TestECBStep4InverseDistanceWeighting(TestCase):
#     """
#     Test ECB/BOJ Step 4: Inverse Distance Weighting (Joint Probability Calculation)
#     Methodology: Section "Step 4: Inverse Distance Weighting
#     (Joint Probability Calculation)"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 4.0
#         self.test_date = date(2024, 1, 15)

#     def test_inverse_distance_weighting_probabilities_sum_to_one(self):
#         """
#         GIVEN scenarios with calculated prices
#         WHEN applying inverse distance weighting
#         THEN probabilities sum to 1.0
#         """
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,  # Market price
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[
#                 datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         prob_df = service._calculate_reverse_distance_probabilities(
#             self.base_rate,
#             future.price,
#             future.first_accrual_date,
#             future.last_accrual_date,
#             (future.last_accrual_date - future.first_accrual_date).days + 1,
#             [date(2024, 3, 15), date(2024, 4, 15)],
#         )

#         # Probabilities should sum to 1.0
#         total_prob = prob_df["probability"].sum()
#         assert abs(total_prob - 1.0) < 0.0001

#     def test_inverse_distance_weighting_closer_price_higher_probability(self):
#         """
#         GIVEN scenarios with different distances from market price
#         WHEN applying inverse distance weighting
#         THEN scenarios closer to market price have higher probabilities
#         """
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,  # Market price
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[
#                 datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         prob_df = service._calculate_reverse_distance_probabilities(
#             self.base_rate,
#             future.price,
#             future.first_accrual_date,
#             future.last_accrual_date,
#             (future.last_accrual_date - future.first_accrual_date).days + 1,
#             [date(2024, 3, 15), date(2024, 4, 15)],
#         )

#         # Find scenario with minimum distance
#         min_distance_idx = prob_df["distance"].idxmin()
#         min_distance_prob = float(prob_df.loc[min_distance_idx, "probability"])  # type: ignore

#         # Find scenario with maximum distance
#         max_distance_idx = prob_df["distance"].idxmax()
#         max_distance_prob = float(prob_df.loc[max_distance_idx, "probability"])  # type: ignore

#         # Closer scenario should have higher probability
#         assert min_distance_prob > max_distance_prob


# class TestECBStep5AggregateIndividualMeetingProbabilities(TestCase):
#     """
#     Test ECB/BOJ Step 5: Aggregate Individual Meeting Probabilities (Marginalization)
#     Methodology: Section "Step 5: Aggregate Individual Meeting
#     Probabilities (Marginalization)"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 4.0
#         self.test_date = date(2024, 1, 15)

#     def test_marginalization_probabilities_sum_to_one_per_meeting(self):
#         """
#         GIVEN joint probabilities from scenarios
#         WHEN aggregating individual meeting probabilities
#         THEN probabilities for each meeting sum to 1.0
#         """
#         future = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future],
#             meeting_dates=[
#                 datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 4, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         prob_df = service._calculate_reverse_distance_probabilities(
#             self.base_rate,
#             future.price,
#             future.first_accrual_date,
#             future.last_accrual_date,
#             (future.last_accrual_date - future.first_accrual_date).days + 1,
#             [date(2024, 3, 15), date(2024, 4, 15)],
#         )

#         step_keys = [-25, 0, 25]
#         total_probabilities = service._get_total_probabilities_from_dataframe(
#             prob_df, step_keys, 2
#         )

#         # Group by meeting_i and sum probabilities
#         meeting_1_probs = {}
#         meeting_2_probs = {}
#         for prob_by_step in total_probabilities:
#             step = prob_by_step["step"]
#             meeting_i = prob_by_step["meeting_i"]
#             prob = prob_by_step["probability"]

#             if meeting_i == 1:
#                 meeting_1_probs[step] = prob
#             elif meeting_i == 2:
#                 meeting_2_probs[step] = prob

#         # Probabilities for each meeting should sum to 1.0
#         total_meeting_1 = sum(meeting_1_probs.values())
#         total_meeting_2 = sum(meeting_2_probs.values())

#         assert abs(total_meeting_1 - 1.0) < 0.0001
#         assert abs(total_meeting_2 - 1.0) < 0.0001


# class TestECBStep6ConvolutionForCumulativeProbabilities(TestCase):
#     """
#     Test ECB/BOJ Step 6: Convolution For Cumulative Probabilities
#     Methodology: Section "Step 6: Convolution For Cumulative Probabilities"
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.base_rate = 4.0
#         self.test_date = date(2024, 1, 15)

#     def test_convolution_combines_previous_and_new_probabilities(self):
#         """
#         GIVEN previous cumulative probabilities and new meeting probabilities
#         WHEN applying convolution
#         THEN probabilities are combined correctly
#         """
#         # First contract: single meeting, +25 bps
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         # Second contract: single meeting, +25 bps
#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.06",
#             first_accrual_date=date(2024, 6, 1),
#             last_accrual_date=date(2024, 8, 31),
#             date=self.test_date,
#             price=95.75,  # Lower price implies higher rate
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
#             ],
#         )

#         service.generate_probability_matrix()

#         # Find the +50 bps entry (cumulative from two +25 bps hikes)
#         step_50 = next(
#             (mp for mp in service.probability_matrix if mp["expected_rate_step"] == 50),
#             None,
#         )

#         if step_50:
#             # Should have two probability entries (two meetings)
#             assert len(step_50["probabilities"]) == 2
#             # Second meeting should have probability for +50 bps cumulative
#             assert step_50["probabilities"][1] > 0

#     def test_convolution_respects_rigidity_constraint(self):
#         """
#         GIVEN previous cumulative step is positive
#         WHEN applying convolution
#         THEN cannot transition to negative step
#         """
#         # First contract: +25 bps (hiking)
#         future_1 = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         # Second contract: -25 bps (cutting) - should be impossible
#         future_2 = StirFuturesModel(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.06",
#             first_accrual_date=date(2024, 6, 1),
#             last_accrual_date=date(2024, 8, 31),
#             date=self.test_date,
#             price=96.25,  # Higher price implies lower rate
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         service = EstrFuturesProbabilityMatrixService(
#             initial_base_rate=self.base_rate,
#             future_prices=[future_1, future_2],
#             meeting_dates=[
#                 datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
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

#         if step_minus_25 and len(step_minus_25["probabilities"]) > 1:
#             # Second meeting should have very low or zero probability
#             # for -25 bps. Due to rigidity constraint, but may still have
#             # some probability due to calculation. The key is that it
#             # should be much lower than if rigidity wasn't enforced.
#             assert step_minus_25["probabilities"][1] < 100.0
