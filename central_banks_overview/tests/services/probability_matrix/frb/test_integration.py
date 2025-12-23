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


class TestFRBIntegrationScenarios(TestCase):
    """
    Integration tests for FRB probability matrix generation.

    These tests verify end-to-end integration with mocked external services
    (meeting dates and futures prices). They focus on:
    - Real-world scenarios (rate hikes, cuts, mixed paths)
    - Integration with the full service stack

    Note: Detailed methodology tests (all combinations, exact steps, fractional steps,
    convolution formulas) are covered in test_methodology.py
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
    def test_single_meeting_rate_cut(self, mock_get_futures, mock_get_meetings):
        """
        GIVEN a single meeting with futures prices implying a rate cut
        WHEN generating probability matrix
        THEN probabilities reflect the expected rate cut

        This tests the basic end-to-end flow for a single meeting scenario.
        """
        meeting_date = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date],
            )
        ]

        # Futures prices imply a small rate cut
        future_1 = StirFuturesModel.objects.create(
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
        future_2 = StirFuturesModel.objects.create(
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
        mock_get_futures.return_value = [future_1, future_2]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [
                    date(2026, 1, 15),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": -25,
                        "probabilities": [
                            45.47,
                        ],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [
                            54.53,
                        ],
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
    def test_two_meetings_consecutive_rate_cuts(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN two consecutive meetings with futures prices implying rate cuts
        WHEN generating probability matrix
        THEN probabilities reflect cumulative rate cuts with convolution

        This tests the convolution logic in a real-world scenario.
        """
        meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        # Futures prices imply consecutive rate cuts
        future_1 = StirFuturesModel.objects.create(
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
        future_2 = StirFuturesModel.objects.create(
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
        future_3 = StirFuturesModel.objects.create(
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
        mock_get_futures.return_value = [future_1, future_2, future_3]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [
                    date(2026, 1, 15),
                    date(2026, 2, 15),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": -50,
                        "probabilities": [
                            0.0,
                            1.01,
                        ],
                    },
                    {
                        "expected_rate_step": -25,
                        "probabilities": [
                            3.88,
                            27.98,
                        ],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [
                            96.12,
                            71.0,
                        ],
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
    def test_three_meetings_mixed_rate_path(self, mock_get_futures, mock_get_meetings):
        """
        GIVEN three meetings with futures prices implying a mixed rate path
        WHEN generating probability matrix
        THEN probabilities reflect cumulative changes with proper convolution

        This tests a complex real-world scenario with multiple meetings.
        Note that although this could happen in the real world, the probability
        calculation rigidity assumption explicity excludes mixed rate paths,
        hence the probabilities are calculated without any consideration of this scenario.
        """
        meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_3 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date_1, meeting_date_2, meeting_date_3],
            )
        ]

        # Futures prices imply a mixed path (cut, then cut, then cut)
        future_1 = StirFuturesModel.objects.create(
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
        future_2 = StirFuturesModel.objects.create(
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
        future_3 = StirFuturesModel.objects.create(
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
        future_4 = StirFuturesModel.objects.create(
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
        mock_get_futures.return_value = [future_1, future_2, future_3, future_4]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [
                    date(2026, 1, 15),
                    date(2026, 2, 15),
                    date(2026, 3, 15),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": -50,
                        "probabilities": [
                            0.0,
                            0.0,
                            1.3,
                        ],
                    },
                    {
                        "expected_rate_step": -25,
                        "probabilities": [
                            3.88,
                            3.5,
                            34.62,
                        ],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [
                            96.12,
                            87.17,
                            58.21,
                        ],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [
                            0.0,
                            9.33,
                            5.86,
                        ],
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
    def test_no_meetings_raises_error(self, mock_get_futures, mock_get_meetings):
        """
        GIVEN no meetings scheduled
        WHEN generating probability matrix
        THEN ValueError is raised

        This tests the edge case where there are no meetings.
        The function should raise an error as meetings are required.
        """
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[],
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
            price=96.365,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        mock_get_futures.return_value = [future_1]

        with pytest.raises(ValueError) as exc_info:
            get_central_bank_probability_matrices(
                target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
            )
        assert "No meeting dates found for FRB" in str(exc_info.value)

    @patch(
        "central_banks_overview.services.cb_inference_services.cb_meetings_services.get_central_bank_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_inference_services.stir_prices_services.get_futures_prices"
    )
    def test_meeting_with_intervening_contract(
        self, mock_get_futures, mock_get_meetings
    ):
        """
        GIVEN a meeting with a contract without a meeting in between
        WHEN generating probability matrix
        THEN probabilities are calculated correctly using inferred rates

        This tests the rate inference logic for periods without meetings.
        """
        meeting_date_1 = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)
        meeting_date_2 = datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc)
        mock_get_meetings.return_value = [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[meeting_date_1, meeting_date_2],
            )
        ]

        # First contract has meeting, second has no meeting, third has meeting
        future_1 = StirFuturesModel.objects.create(
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
        future_2 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.test_date,
            price=96.42,  # Implied rate = 3.58% (no meeting in this contract)
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
            price=96.455,  # Implied rate = 3.545%
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        future_4 = StirFuturesModel.objects.create(
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
        mock_get_futures.return_value = [future_1, future_2, future_3, future_4]

        result = get_central_bank_probability_matrices(
            target_date=self.test_date, central_banks=[CentralBankChoices.FRB]
        )
        assert result == [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [
                    date(2026, 1, 15),
                    date(2026, 3, 15),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": -50,
                        "probabilities": [
                            0.0,
                            16.91,
                        ],
                    },
                    {
                        "expected_rate_step": -25,
                        "probabilities": [
                            45.47,
                            48.84,
                        ],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [
                            54.53,
                            34.25,
                        ],
                    },
                ],
            },
        ]
