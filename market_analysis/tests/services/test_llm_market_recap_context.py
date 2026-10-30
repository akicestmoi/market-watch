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
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorBaseUnitChoices,
    IndicatorDisplayModeChoices,
    PublicationScheduleModel,
)
from market_analysis.services.llm_market_recap import (
    CentralBankContextRow,
    EconomicContextRow,
    FxHeatmapContext,
    ProbabilityMatrixShiftContextRow,
    _CentralBankDecisionRateRow,
    _CentralBankFigureRow,
    _EconomicContextModeValues,
    _compute_fx_currency_strength,
    _ProbabilityStepRow,
    build_central_bank_context,
    build_economic_context,
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


class TestEconomicContext(TestCase):
    """Tests for scheduled economic-release LLM context."""

    def test_build_economic_context_includes_all_display_modes(self):
        """
        GIVEN a quarterly GDP indicator scheduled on the reporting date
        WHEN building economic context
        THEN values_by_mode includes Abs / QoQ / QoQy / YoY with is_default on the seeded main mode
        """
        as_of = date(2025, 12, 16)
        publication_datetime = datetime(2025, 12, 16, 13, 30, 0, tzinfo=timezone.utc)
        indicator = EconomicIndicatorInformationModel.objects.create(
            id=9001,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP",
            name="US GDP",
            technical_name="us_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GDP",
            base_unit=IndicatorBaseUnitChoices.B,
            base_currency="USD",
            default_mode=IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
        )
        PublicationScheduleModel.objects.create(
            indicator=indicator,
            current_publication_date=publication_datetime,
        )
        for period, data_value in (
            (date(2025, 10, 1), 110.0),
            (date(2025, 7, 1), 100.0),
            (date(2025, 4, 1), 95.0),
            (date(2025, 1, 1), 90.0),
            (date(2024, 10, 1), 85.0),
            (date(2024, 7, 1), 80.0),
        ):
            EconomicDataModel.objects.create(
                indicator=indicator,
                period=period,
                data_value=data_value,
            )

        result = build_economic_context(as_of)
        assert result == [
            EconomicContextRow(
                name="US GDP",
                location=EconomicDataLocationChoices.US,
                category=EconomicDataCategoryChoices.GROWTH,
                frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
                period="2025-10-01",
                period_display="25Q4",
                default_mode="Annualized Quarter",
                default_mode_label="QoQy",
                base_unit="B",
                base_currency="USD",
                raw_current_value=110.0,
                raw_previous_value=100.0,
                values_by_mode=[
                    _EconomicContextModeValues(
                        mode="Raw",
                        mode_label="Abs",
                        is_default=False,
                        current_value=110.0,
                        previous_value=100.0,
                        change_value=10.0,
                        display_current_value="110.00 (bUSD)",
                        display_previous_value="100.00 (bUSD)",
                        display_change_value="10.00 (bUSD)",
                    ),
                    _EconomicContextModeValues(
                        mode="Quarter",
                        mode_label="QoQ",
                        is_default=False,
                        current_value=10.0,
                        previous_value=5.263157894736842,
                        change_value=4.736842105263158,
                        display_current_value="10.00 %",
                        display_previous_value="5.26 %",
                        display_change_value="4.74 %",
                    ),
                    _EconomicContextModeValues(
                        mode="Annualized Quarter",
                        mode_label="QoQy",
                        is_default=True,
                        current_value=46.41000000000004,
                        previous_value=22.77376631548251,
                        change_value=23.636233684517528,
                        display_current_value="46.41 %",
                        display_previous_value="22.77 %",
                        display_change_value="23.64 %",
                    ),
                    _EconomicContextModeValues(
                        mode="Annual",
                        mode_label="YoY",
                        is_default=False,
                        current_value=29.411764705882355,
                        previous_value=25.0,
                        change_value=4.411764705882355,
                        display_current_value="29.41 %",
                        display_previous_value="25.00 %",
                        display_change_value="4.41 %",
                    ),
                ],
                comment=None,
                publication_date=publication_datetime.isoformat(),
                kind="scheduled_release",
            )
        ]


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
