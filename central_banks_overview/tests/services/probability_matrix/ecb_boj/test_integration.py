from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest  # type: ignore[reportMissingImports]
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


class TestECBIntegrationScenarios(TestCase):
    """
    Integration tests for ECB probability matrix generation.
    Tests all possible scenarios: single meeting, multiple meetings, etc.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = date(2025, 12, 15)
        self.base_rate = 4.0

        # Create ESTR asset
        self.estr_asset = AssetModel.objects.create(
            short_name="ESTR",
            full_name="Euro Short-Term Rate",
            asset_id=8,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.EU,
            ticker="ESTR",
        )

        # Create market price
        MarketPriceModel.objects.create(
            asset=self.estr_asset,
            date=self.test_date,
            price=self.base_rate,
        )

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_ecb_scenario_1_single_meeting(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 1: Single meeting in 3-month contract
        Expected: Probabilities calculated using single meeting methodology
        """
        meeting_date = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [9.6],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [90.4],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_ecb_scenario_2_two_meetings(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 2: Two meetings in 3-month contract
        Expected: Probabilities calculated using n-meetings methodology
        """
        meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15), date(2026, 4, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [45.68, 44.6],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [47.93, 49.7],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [6.39, 5.7],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_ecb_scenario_3_three_meetings(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 3: Three meetings in 3-month contract
        Expected: Probabilities calculated using n-meetings methodology
        """
        meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_3 = datetime(2026, 5, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date_1, meeting_date_2, meeting_date_3],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [
                    date(2026, 3, 15),
                    date(2026, 4, 15),
                    date(2026, 5, 15),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [43.19, 70.02, 40.59],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [51.33, 22.53, 53.21],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [5.48, 7.45, 6.2],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_ecb_scenario_4_multiple_contracts_with_meetings(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        Scenario 4: Multiple 3-month contracts, each with meetings
        Expected: Probabilities convolved across contracts
        """
        meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 6, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.06",
            first_accrual_date=date(2026, 6, 1),
            last_accrual_date=date(2026, 8, 31),
            date=self.test_date,
            price=95.75,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future_1, future_2]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15), date(2026, 6, 15)],
                "probability_matrix": [
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
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_one_central_bank_ok(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN meeting dates and futures prices for one central bank (ECB)
        WHEN getting probability matrices
        THEN a probability matrix is returned for the central bank
        """
        # Create meeting dates
        meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        # Create futures prices (covering both meetings)
        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15), date(2026, 4, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [45.68, 44.6],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [47.93, 49.7],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [6.39, 5.7],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_success_multiple_banks(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN meeting dates and futures prices for multiple central banks (ECB and BOJ)
        WHEN getting probability matrices
        THEN probability matrices are returned for all banks
        """
        # Meeting dates within accrual periods
        meeting_date_ecb = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_boj = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date_ecb],
            ),
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.BOJ,
                meeting_dates=[meeting_date_boj],
            ),
        ]

        # Create futures prices (covering meetings)
        future_ecb = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        # Create BOJ asset for the test
        boj_asset = AssetModel.objects.create(
            short_name="MUTAN",
            full_name="Uncollateralized Overnight Call Rate",
            asset_id=9,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.JP,
            ticker="MUTAN",
        )
        MarketPriceModel.objects.create(
            asset=boj_asset,
            date=self.test_date,
            price=0.1,
        )
        future_boj = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future_ecb, future_boj]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date,
            central_banks=[CentralBankChoices.ECB, CentralBankChoices.BOJ],
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [9.6],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [90.4],
                    },
                ],
                    },
            {
                "central_bank": CentralBankChoices.BOJ,
                "meeting_dates": [date(2026, 3, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [99.99],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_no_meeting_dates_error(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN no meeting dates found for a central bank (ECB)
        WHEN getting probability matrices
        THEN a ValueError is raised
        """
        mock_get_meetings.return_value = []

        # Create futures prices (after test_date)
        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        with pytest.raises(ValueError) as exc_info:
            get_central_bank_probability_matrices(
                target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
            )
        assert str(exc_info.value) == "No meeting dates found for ECB."

    @patch(
        "central_banks_overview.services.cb_inference_services.get_central_bank_effective_rate"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_uses_fallback_rate(
        self, mock_get_futures, mock_get_meetings, mock_get_effective_rate
    ):
        """
        GIVEN no effective rate for target date but fallback rate exists for ECB
        WHEN getting probability matrices
        THEN fallback rate is used
        """
        meeting_date = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[meeting_date],
            )
        ]

        # Mock get_central_bank_effective_rate to return None
        mock_get_effective_rate.return_value = None

        # Create fallback rate (before target date)
        MarketPriceModel.objects.create(
            asset=self.estr_asset,
            date=date(2025, 12, 10),
            price=4.0,
            )

        # Create futures prices
        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.ECB]
        )

        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [9.6],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [90.4],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_with_meeting_dates_override(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN meeting dates override is provided for ECB
        WHEN getting probability matrices
        THEN the override meeting dates are used instead of fetched ones
        """
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        # Override meeting dates (within accrual periods)
        override_meeting_dates = {
            CentralBankChoices.ECB: [
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc),
            ]
        }

        result = get_central_bank_probability_matrices(
            target_date=self.test_date,
            central_banks=[CentralBankChoices.ECB],
            meeting_dates_override=override_meeting_dates,
        )

        assert result == [
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2026, 3, 15), date(2026, 4, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [45.68, 44.6],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [47.93, 49.7],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [6.39, 5.7],
                    },
                ],
            },
        ]


class TestBOJIntegrationScenarios(TestCase):
    """
    Integration tests for BOJ probability matrix generation.
    Tests all possible scenarios: single meeting, multiple meetings, etc.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = date(2025, 12, 15)
        self.base_rate = 0.1

        # Create MUTAN asset
        self.mutan_asset = AssetModel.objects.create(
            short_name="MUTAN",
            full_name="Uncollateralized Overnight Call Rate",
            asset_id=9,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.JP,
            ticker="MUTAN",
        )

        # Create market price
        MarketPriceModel.objects.create(
            asset=self.mutan_asset,
            date=self.test_date,
            price=self.base_rate,
        )

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_boj_scenario_1_single_meeting(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 1: Single meeting in 3-month contract
        Expected: Probabilities calculated using single meeting methodology
        """
        meeting_date = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.BOJ,
                meeting_dates=[meeting_date],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.BOJ,
                "meeting_dates": [date(2026, 3, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [99.99],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_boj_scenario_2_two_meetings(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 2: Two meetings in 3-month contract
        Expected: Probabilities calculated using n-meetings methodology
        """
        meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.BOJ,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.BOJ,
                "meeting_dates": [date(2026, 3, 15), date(2026, 4, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [6.08, 4.64],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [88.33, 90.99],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [5.59, 4.37],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_boj_scenario_3_three_meetings(self, mock_get_futures, mock_get_meetings):
        """
        Scenario 3: Three meetings in 3-month contract
        Expected: Probabilities calculated using n-meetings methodology
        """
        meeting_date_1 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_3 = datetime(2026, 5, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.BOJ,
                meeting_dates=[meeting_date_1, meeting_date_2, meeting_date_3],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.BOJ,
                "meeting_dates": [
                    date(2026, 3, 15),
                    date(2026, 4, 15),
                    date(2026, 5, 15),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [7.41, 10.12, 11.99],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [85.84, 80.66, 77.96],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [6.75, 9.22, 10.04],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_no_meeting_dates_error(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN no meeting dates found for a central bank (BOJ)
        WHEN getting probability matrices
        THEN a ValueError is raised
        """
        mock_get_meetings.return_value = []

        # Create futures prices (after test_date)
        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        with pytest.raises(ValueError) as exc_info:
            get_central_bank_probability_matrices(
                target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
            )
        assert str(exc_info.value) == "No meeting dates found for BOJ."

    @patch(
        "central_banks_overview.services.cb_inference_services.get_central_bank_effective_rate"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_uses_fallback_rate(
        self, mock_get_futures, mock_get_meetings, mock_get_effective_rate
    ):
        """
        GIVEN no effective rate for target date but fallback rate exists for BOJ
        WHEN getting probability matrices
        THEN fallback rate is used
        """
        meeting_date = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.BOJ,
                meeting_dates=[meeting_date],
            )
        ]

        # Mock get_central_bank_effective_rate to return None
        mock_get_effective_rate.return_value = None

        # Create fallback rate (before target date)
        MarketPriceModel.objects.create(
            asset=self.mutan_asset,
            date=date(2025, 12, 10),
            price=0.1,
        )

        # Create futures prices
        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.BOJ]
        )

        assert result == [
            {
                "central_bank": CentralBankChoices.BOJ,
                "meeting_dates": [date(2026, 3, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [99.99],
                    },
                ],
            },
        ]

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_get_central_bank_probability_matrices_with_meeting_dates_override(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN meeting dates override is provided for BOJ
        WHEN getting probability matrices
        THEN the override meeting dates are used instead of fetched ones
        """
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.BOJ,
                meeting_dates=[datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)],
            )
        ]

        future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 5, 31),
            date=self.test_date,
            price=99.9,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        mock_get_futures.return_value = [future]

        # Override meeting dates (within accrual periods)
        override_meeting_dates = {
            CentralBankChoices.BOJ: [
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc),
            ]
        }

        result = get_central_bank_probability_matrices(
            target_date=self.test_date,
            central_banks=[CentralBankChoices.BOJ],
            meeting_dates_override=override_meeting_dates,
        )

        assert result == [
            {
                "central_bank": CentralBankChoices.BOJ,
                "meeting_dates": [date(2026, 3, 15), date(2026, 4, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [6.08, 4.64],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [88.33, 90.99],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [5.59, 4.37],
                    },
                ],
            },
        ]
