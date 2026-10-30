"""Tests for FX heatmap and probability-matrix shift LLM context builders."""

from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankDataModel,
    CentralBankMeetingModel,
)
from data_visualization.services.config import FX_MATRIX_ORDER
from data_visualization.services.market_recap import FxMatrixRow
from market_analysis.services.llm_market_recap import (
    CentralBankContextRow,
    FxHeatmapContext,
    ProbabilityMatrixShiftContextRow,
    _CentralBankDecisionRateRow,
    _CentralBankFigureRow,
    _compute_fx_currency_strength,
    _ProbabilityStepRow,
    build_central_bank_context,
    build_fx_heatmap_context,
    build_probability_matrix_shift_context,
)


class TestFxHeatmapContext(TestCase):
    """Tests for FX heatmap LLM context."""

    def test_compute_fx_currency_strength_rms_off_diagonal(self):
        """
        GIVEN an FX matrix row with known pairwise DoD % changes
        WHEN computing currency strength
        THEN the RMS excludes the diagonal and matches sqrt(mean of squares)
        """
        matrix = [
            FxMatrixRow(
                currency="USD",
                EUR=1.0,
                USD=0.0,
                GBP=2.0,
                JPY=3.0,
                CHF=4.0,
                AUD=5.0,
                CNY=6.0,
            )
        ]
        # sqrt((1+4+9+16+25+36)/6) = sqrt(91/6)
        expected_rms = round((91 / 6) ** 0.5, 4)
        result = _compute_fx_currency_strength(matrix)
        assert result == [
            {
                "currency": "USD",
                "rms_change_pct": expected_rms,
            }
        ]

    def test_compute_fx_currency_strength_rms_ignores_sign_cancellation(self):
        """
        GIVEN equal-magnitude opposing pairwise moves
        WHEN computing currency strength
        THEN the RMS stays large instead of averaging to zero
        """
        matrix = [
            FxMatrixRow(
                currency="USD",
                EUR=3.0,
                USD=0.0,
                GBP=-3.0,
                JPY=3.0,
                CHF=-3.0,
                AUD=3.0,
                CNY=-3.0,
            )
        ]
        result = _compute_fx_currency_strength(matrix)
        assert result == [
            {
                "currency": "USD",
                "rms_change_pct": 3.0,
            }
        ]

    @patch("market_analysis.services.llm_market_recap.get_fx_prices_matrix")
    def test_build_fx_heatmap_context(self, mock_get_fx_prices_matrix):
        """
        GIVEN FX matrix rows for a reporting date
        WHEN building FX heatmap context
        THEN matrix, previous business day, and currency strength are returned
        """
        matrix = [
            FxMatrixRow(
                currency="EUR",
                EUR=0.0,
                USD=-0.5,
                GBP=0.0,
                JPY=0.0,
                CHF=0.0,
                AUD=0.0,
                CNY=0.0,
            ),
            FxMatrixRow(
                currency="USD",
                EUR=0.5,
                USD=0.0,
                GBP=0.5,
                JPY=0.5,
                CHF=0.5,
                AUD=0.5,
                CNY=0.5,
            ),
        ]
        mock_get_fx_prices_matrix.return_value = matrix
        as_of = date(2025, 12, 16)
        result = build_fx_heatmap_context(as_of)
        assert result == FxHeatmapContext(
            as_of="2025-12-16",
            previous_date="2025-12-15",
            currencies=list(FX_MATRIX_ORDER),
            matrix=matrix,
            currency_strength=[
                {"currency": "EUR", "rms_change_pct": round((0.25 / 6) ** 0.5, 4)},
                {"currency": "USD", "rms_change_pct": 0.5},
            ],
        )
        mock_get_fx_prices_matrix.assert_called_once_with(
            date(2025, 12, 16), date(2025, 12, 15)
        )


class TestProbabilityMatrixShiftContext(TestCase):
    """Tests for probability-matrix shift LLM context."""

    @patch(
        "market_analysis.services.llm_market_recap.get_formatted_probability_matrix_changes"
    )
    @patch(
        "market_analysis.services.llm_market_recap.get_central_bank_formatted_probability_matrix"
    )
    def test_build_probability_matrix_shift_context(
        self, mock_get_matrix, mock_get_changes
    ):
        """
        GIVEN current and previous probability matrices for FRB / ECB / BOJ
        WHEN building probability-matrix shift context
        THEN current probabilities and DoD shifts are included per bank
        """
        current = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2026, 1, 28)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.6]},
                {"expected_rate_step": -25, "probabilities": [0.4]},
            ],
        }
        previous = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2026, 1, 28)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.5]},
                {"expected_rate_step": -25, "probabilities": [0.5]},
            ],
        }
        changes = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2026, 1, 28)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.1]},
                {"expected_rate_step": -25, "probabilities": [-0.1]},
            ],
        }

        def _matrix_side_effect(
            central_bank, reference_date, meeting_dates_override=[]
        ):
            if central_bank != CentralBankChoices.FRB:
                return None
            if reference_date == date(2025, 12, 16):
                return current
            return previous

        mock_get_matrix.side_effect = _matrix_side_effect
        mock_get_changes.return_value = changes

        result = build_probability_matrix_shift_context(date(2025, 12, 16))
        assert result == [
            ProbabilityMatrixShiftContextRow(
                central_bank=CentralBankChoices.FRB,
                as_of="2025-12-16",
                previous_date="2025-12-15",
                meeting_dates=["2026-01-28"],
                current_probabilities=[
                    _ProbabilityStepRow(expected_rate_step=0, probabilities=[0.6]),
                    _ProbabilityStepRow(expected_rate_step=-25, probabilities=[0.4]),
                ],
                probability_changes=[
                    _ProbabilityStepRow(expected_rate_step=0, probabilities=[0.1]),
                    _ProbabilityStepRow(expected_rate_step=-25, probabilities=[-0.1]),
                ],
            )
        ]

    @patch(
        "market_analysis.services.llm_market_recap.get_central_bank_formatted_probability_matrix"
    )
    def test_build_probability_matrix_shift_context_skips_failures(
        self, mock_get_matrix
    ):
        """
        GIVEN probability-matrix calculation raises for every bank
        WHEN building probability-matrix shift context
        THEN an empty list is returned without propagating the error
        """
        mock_get_matrix.side_effect = ValueError("missing futures")
        result = build_probability_matrix_shift_context(date(2025, 12, 16))
        assert result == []


class TestCentralBankContext(TestCase):
    """Tests for central-bank LLM context including decision-day rates."""

    @patch("market_analysis.services.llm_market_recap.get_central_bank_data_item")
    def test_build_central_bank_context_includes_decision_rates(
        self, mock_get_central_bank_data_item
    ):
        """
        GIVEN an ECB meeting and key-rate prints on the reporting date
        WHEN building central-bank context
        THEN ECB is_decision_day with decision_rates current/previous/change
        """
        as_of = date(2025, 12, 15)
        mock_get_central_bank_data_item.return_value = [
            {"label": "Effective Rate", "value": "2.00 %"},
        ]
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=datetime(2025, 12, 15, 12, 15, 0, tzinfo=timezone.utc),
        )
        CentralBankDataModel.objects.create(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=date(2025, 10, 30),
            value=2.0,
        )
        CentralBankDataModel.objects.create(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=as_of,
            value=1.75,
        )

        result = build_central_bank_context(as_of)
        assert result == [
            CentralBankContextRow(
                central_bank=CentralBankChoices.FRB,
                reference_date="2025-12-15",
                is_decision_day=False,
                decision_rates=[],
                figures=[
                    _CentralBankFigureRow(label="Effective Rate", value="2.00 %"),
                ],
            ),
            CentralBankContextRow(
                central_bank=CentralBankChoices.ECB,
                reference_date="2025-12-15",
                is_decision_day=True,
                decision_rates=[
                    _CentralBankDecisionRateRow(
                        name="ECB Deposit Facility Rate",
                        current_value=1.75,
                        previous_value=2.0,
                        change_value=-0.25,
                        display_current_value="1.75 %",
                        display_previous_value="2.00 %",
                        display_change_value="-0.25 %",
                    )
                ],
                figures=[
                    _CentralBankFigureRow(label="Effective Rate", value="2.00 %"),
                ],
            ),
            CentralBankContextRow(
                central_bank=CentralBankChoices.BOJ,
                reference_date="2025-12-15",
                is_decision_day=False,
                decision_rates=[],
                figures=[
                    _CentralBankFigureRow(label="Effective Rate", value="2.00 %"),
                ],
            ),
        ]
