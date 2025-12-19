from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.cb_inference_services import (
    get_central_bank_probability_matrices,
)
from central_banks_overview.services.cb_meetings_services import CentralBankMeetingDates
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)


class TestFRBIntegrationScenarios(TestCase):
    """
    Integration tests for FRB probability matrix generation.
    Tests all possible scenarios: first contract with/without meeting,
    multiple meetings, rate hikes/cuts, etc.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = date(2025, 12, 15)
        self.base_rate = 3.64

        # Create EFFR asset
        self.effr_asset = AssetModel.objects.create(
            short_name="EFFR",
            full_name="Effective Fed Funds Rate",
            asset_id=7,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.US,
            ticker="500",
        )

        # Create market price
        MarketPriceModel.objects.create(
            asset=self.effr_asset,
            date=self.test_date,
            price=self.base_rate,
        )

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_frb_scenario_1_first_contract_with_meeting_single_meeting(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        Scenario 1: First contract has meeting, single meeting total
        Expected: start_rate = base_rate, probabilities calculated correctly
        """
        meeting_date = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date],
            )
        ]
        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.36,  # Implied rate = 3.64%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 57.6],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [0.0, 42.39],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_frb_scenario_2_first_contract_without_meeting_then_meeting(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        Scenario 2: First contract has no meeting, second has meeting
        Expected: start_rate for meeting = first contract's implied_rate
        """
        meeting_date = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date],
            )
        ]
        future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.36,  # Implied rate = 3.64%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.425,  # Implied rate = 3.575%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        mock_get_futures.return_value = [future_1, future_2]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 57.6],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [0.0, 42.39],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_frb_scenario_3_multiple_meetings_with_intervening_contracts(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        Scenario 3: Multiple meetings with contracts without meetings in between
        Expected: Each meeting gets correct start_rate and end_rate
        """
        meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]
        future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.36,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.425,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_3 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.test_date,
            price=96.455,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        mock_get_futures.return_value = [future_1, future_2, future_3]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 57.6],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [0.0, 42.39],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_frb_scenario_4_rate_hike_path(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 4: Multiple meetings showing rate hike path
        Expected: Probabilities reflect cumulative hikes
        """
        meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        # Prices imply rate hikes
        future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.25,  # Implies rate hike
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.0,  # Implies further rate hike
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        mock_get_futures.return_value = [future_1, future_2]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 57.6],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [0.0, 42.39],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_frb_scenario_5_rate_cut_path(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 5: Multiple meetings showing rate cut path
        Expected: Probabilities reflect cumulative cuts
        """
        meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        # Prices imply rate cuts
        future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.test_date,
            price=96.75,  # Implies rate cut
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=97.0,  # Implies further rate cut
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        mock_get_futures.return_value = [future_1, future_2]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "expected_rate_step": -50,
                "probabilities": [0.0, 57.6],
            },
            {
                "expected_rate_step": -25,
                "probabilities": [0.0, 42.39],
            },
        ]
