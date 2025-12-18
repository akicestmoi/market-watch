# class TestECBIntegrationScenarios(TestCase):
#     """
#     Integration tests for ECB probability matrix generation.
#     Tests all possible scenarios: single meeting, multiple meetings, etc.
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.test_date = date(2025, 12, 15)
#         self.base_rate = 4.0

#         # Create ESTR asset
#         self.estr_asset = AssetModel.objects.create(
#             short_name="ESTR",
#             full_name="Euro Short-Term Rate",
#             asset_id=8,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.EU,
#             ticker="ESTR",
#         )

#         # Create market price
#         MarketPriceModel.objects.create(
#             asset=self.estr_asset,
#             date=self.test_date,
#             price=self.base_rate,
#         )

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_ecb_scenario_1_single_meeting(self, mock_get_futures, mock_get_meetings):
#         """
#         Scenario 1: Single meeting in 3-month contract
#         Expected: Probabilities calculated using single meeting methodology
#         """
#         meeting_date = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.ECB,
#                 meeting_dates=[meeting_date],
#             )
#         ]

#         future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
#         )

#         assert len(result) == 1
#         assert result[0]["central_bank"] == CentralBankChoices.ECB
#         assert len(result[0]["meeting_dates"]) == 1
#         assert len(result[0]["probability_matrix"]) > 0
#         # Probabilities should sum to ~100%
#         total_prob = sum(
#             pm["probabilities"][0]
#             for pm in result[0]["probability_matrix"]
#             if len(pm["probabilities"]) > 0
#         )
#         assert abs(total_prob - 100.0) < 5.0

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_ecb_scenario_2_two_meetings(self, mock_get_futures, mock_get_meetings):
#         """
#         Scenario 2: Two meetings in 3-month contract
#         Expected: Probabilities calculated using n-meetings methodology
#         """
#         meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.ECB,
#                 meeting_dates=[meeting_date_1, meeting_date_2],
#             )
#         ]

#         future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
#         )

#         assert len(result) == 1
#         assert len(result[0]["meeting_dates"]) == 2
#         assert len(result[0]["probability_matrix"]) > 0
#         # Verify probabilities sum to ~100% for each meeting
#         for i in range(2):
#             total_prob = sum(
#                 pm["probabilities"][i]
#                 for pm in result[0]["probability_matrix"]
#                 if len(pm["probabilities"]) > i
#             )
#             assert abs(total_prob - 100.0) < 5.0

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_ecb_scenario_3_three_meetings(self, mock_get_futures, mock_get_meetings):
#         """
#         Scenario 3: Three meetings in 3-month contract
#         Expected: Probabilities calculated using n-meetings methodology
#         """
#         meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_3 = datetime(2026, 5, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.ECB,
#                 meeting_dates=[meeting_date_1, meeting_date_2, meeting_date_3],
#             )
#         ]

#         future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
#         )

#         assert len(result) == 1
#         assert len(result[0]["meeting_dates"]) == 3
#         assert len(result[0]["probability_matrix"]) > 0
#         # Verify probabilities sum to ~100% for each meeting
#         for i in range(3):
#             total_prob = sum(
#                 pm["probabilities"][i]
#                 for pm in result[0]["probability_matrix"]
#                 if len(pm["probabilities"]) > i
#             )
#             assert abs(total_prob - 100.0) < 5.0

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_ecb_scenario_4_multiple_contracts_with_meetings(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         Scenario 4: Multiple 3-month contracts, each with meetings
#         Expected: Probabilities convolved across contracts
#         """
#         meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 6, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.ECB,
#                 meeting_dates=[meeting_date_1, meeting_date_2],
#             )
#         ]

#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         future_2 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="26.06",
#             first_accrual_date=date(2026, 6, 1),
#             last_accrual_date=date(2026, 8, 31),
#             date=self.test_date,
#             price=95.75,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1, future_2]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
#         )

#         assert len(result) == 1
#         assert len(result[0]["meeting_dates"]) == 2
#         assert len(result[0]["probability_matrix"]) > 0


# class TestBOJIntegrationScenarios(TestCase):
#     """
#     Integration tests for BOJ probability matrix generation.
#     Tests all possible scenarios: single meeting, multiple meetings, etc.
#     """

#     def setUp(self):
#         """Set up test fixtures."""
#         self.test_date = date(2025, 12, 15)
#         self.base_rate = 0.1

#         # Create MUTAN asset
#         self.mutan_asset = AssetModel.objects.create(
#             short_name="MUTAN",
#             full_name="Uncollateralized Overnight Call Rate",
#             asset_id=9,
#             asset_class=AssetClassChoices.RATES,
#             asset_type=AssetTypeChoices.INTERBANK_RATE,
#             location=LocationChoices.JP,
#             ticker="MUTAN",
#         )

#         # Create market price
#         MarketPriceModel.objects.create(
#             asset=self.mutan_asset,
#             date=self.test_date,
#             price=self.base_rate,
#         )

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_boj_scenario_1_single_meeting(self, mock_get_futures, mock_get_meetings):
#         """
#         Scenario 1: Single meeting in 3-month contract
#         Expected: Probabilities calculated using single meeting methodology
#         """
#         meeting_date = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.BOJ,
#                 meeting_dates=[meeting_date],
#             )
#         ]

#         future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=99.9,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
#         )

#         assert len(result) == 1
#         assert result[0]["central_bank"] == CentralBankChoices.BOJ
#         assert len(result[0]["meeting_dates"]) == 1
#         assert len(result[0]["probability_matrix"]) > 0
#         # Probabilities should sum to ~100%
#         total_prob = sum(
#             pm["probabilities"][0]
#             for pm in result[0]["probability_matrix"]
#             if len(pm["probabilities"]) > 0
#         )
#         assert abs(total_prob - 100.0) < 5.0

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_boj_scenario_2_two_meetings(self, mock_get_futures, mock_get_meetings):
#         """
#         Scenario 2: Two meetings in 3-month contract
#         Expected: Probabilities calculated using n-meetings methodology
#         """
#         meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.BOJ,
#                 meeting_dates=[meeting_date_1, meeting_date_2],
#             )
#         ]

#         future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=99.9,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
#         )

#         assert len(result) == 1
#         assert len(result[0]["meeting_dates"]) == 2
#         assert len(result[0]["probability_matrix"]) > 0
#         # Verify probabilities sum to ~100% for each meeting
#         for i in range(2):
#             total_prob = sum(
#                 pm["probabilities"][i]
#                 for pm in result[0]["probability_matrix"]
#                 if len(pm["probabilities"]) > i
#             )
#             assert abs(total_prob - 100.0) < 5.0

#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_boj_scenario_3_three_meetings(self, mock_get_futures, mock_get_meetings):
#         """
#         Scenario 3: Three meetings in 3-month contract
#         Expected: Probabilities calculated using n-meetings methodology
#         """
#         meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_3 = datetime(2026, 5, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.BOJ,
#                 meeting_dates=[meeting_date_1, meeting_date_2, meeting_date_3],
#             )
#         ]

#         future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=99.9,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
#         )

#         assert len(result) == 1
#         assert len(result[0]["meeting_dates"]) == 3
#         assert len(result[0]["probability_matrix"]) > 0
#         # Verify probabilities sum to ~100% for each meeting
#         for i in range(3):
#             total_prob = sum(
#                 pm["probabilities"][i]
#                 for pm in result[0]["probability_matrix"]
#                 if len(pm["probabilities"]) > i
#             )
#             assert abs(total_prob - 100.0) < 5.0


#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_get_central_bank_probability_matrices_one_central_bank_ok(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN meeting dates and futures prices for one central bank (FRB)
#         WHEN getting probability matrices
#         THEN a probability matrix is returned for the central bank
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
#     def test_get_central_bank_probability_matrices_success_multiple_banks(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN meeting dates and futures prices for multiple central banks
#         WHEN getting probability matrices
#         THEN probability matrices are returned for all banks
#         """
#         # Meeting dates within accrual periods
#         meeting_date_frb = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
#         meeting_date_ecb = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.FRB,
#                 meeting_dates=[meeting_date_frb],
#             ),
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.ECB,
#                 meeting_dates=[meeting_date_ecb],
#             ),
#         ]

#         # Create futures prices (covering meetings)
#         future_frb = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=94.75,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         MarketPriceModel.objects.create(
#             asset=self.estr_asset,
#             date=self.test_date,
#             price=4.0,
#         )
#         future_ecb = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="26.03",
#             first_accrual_date=date(2026, 3, 1),
#             last_accrual_date=date(2026, 5, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_frb, future_ecb]

#         # Call the function
#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date,
#             central_banks=[CentralBankChoices.FRB, CentralBankChoices.ECB],
#         )
#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "meeting_dates": [date(2026, 1, 15)],
#                 "probability_matrix": [
#                     {
#                         "expected_rate_step": 0,
#                         "probabilities": [100.0],
#                     },
#                 ],
#             },
#             {
#                 "central_bank": CentralBankChoices.ECB,
#                 "meeting_dates": [date(2026, 3, 15)],
#                 "probability_matrix": [
#                     {
#                         "expected_rate_step": -25,
#                         "probabilities": [9.6],
#                     },
#                     {
#                         "expected_rate_step": 0,
#                         "probabilities": [90.4],
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
#     def test_get_central_bank_probability_matrices_with_meeting_dates_override(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN meeting dates override is provided
#         WHEN getting probability matrices
#         THEN the override meeting dates are used instead of fetched ones
#         """
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.FRB,
#                 meeting_dates=[datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)],
#             )
#         ]

#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=94.75,
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
#             price=94.50,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1, future_2]

#         # Override meeting dates (within accrual periods)
#         override_meeting_dates = {
#             CentralBankChoices.FRB: [
#                 datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc),
#                 datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
#             ]
#         }

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date,
#             central_banks=[CentralBankChoices.FRB],
#             meeting_dates_override=override_meeting_dates,
#         )

#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "meeting_dates": [date(2026, 1, 15), date(2026, 2, 15)],
#                 "probability_matrix": [
#                     {
#                         "expected_rate_step": 0,
#                         "probabilities": [100.0, 0.0],
#                     },
#                     {
#                         "expected_rate_step": 50,
#                         "probabilities": [0.0, 84.62],
#                     },
#                     {
#                         "expected_rate_step": 75,
#                         "probabilities": [0.0, 15.38],
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
#     def test_get_central_bank_probability_matrices_no_meeting_dates_error(
#         self, mock_get_futures, mock_get_meetings
#     ):
#         """
#         GIVEN no meeting dates found for a central bank
#         WHEN getting probability matrices
#         THEN a ValueError is raised
#         """
#         mock_get_meetings.return_value = []

#         # Create futures prices (after test_date)
#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=94.75,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1]

#         with pytest.raises(ValueError) as exc_info:
#             get_central_bank_probability_matrices(
#                 target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
#             )
#         assert str(exc_info.value) == "No meeting dates found for FRB."

#     @patch(
#         "central_banks_overview.services.cb_inference_services.get_central_bank_effective_rate"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
#     )
#     @patch(
#         "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
#     )
#     def test_get_central_bank_probability_matrices_uses_fallback_rate(
#         self, mock_get_futures, mock_get_meetings, mock_get_effective_rate
#     ):
#         """
#         GIVEN no effective rate for target date but fallback rate exists
#         WHEN getting probability matrices
#         THEN fallback rate is used
#         """
#         meeting_date = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
#         mock_get_meetings.return_value = [
#             CentralBankMeetingDates(
#                 central_bank=CentralBankChoices.FRB,
#                 meeting_dates=[meeting_date],
#             )
#         ]

#         # Mock get_central_bank_effective_rate to return None
#         mock_get_effective_rate.return_value = None

#         # Create futures prices
#         future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="26.01",
#             first_accrual_date=date(2026, 1, 1),
#             last_accrual_date=date(2026, 1, 31),
#             date=self.test_date,
#             price=94.75,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )
#         mock_get_futures.return_value = [future_1]

#         result = get_central_bank_probability_matrices(
#             target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
#         )

#         assert result == [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "meeting_dates": [date(2026, 1, 15)],
#                 "probability_matrix": [
#                     {
#                         "expected_rate_step": 0,
#                         "probabilities": [100.0],
#                     },
#                 ],
#             },
#         ]
