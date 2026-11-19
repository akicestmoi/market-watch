"""Build central-bank recap payloads for the visualization UI."""

import logging
from datetime import date, datetime
from typing import TypedDict

import central_banks_overview.services.central_banks_inference as central_banks_inference
import central_banks_overview.services.central_banks_meetings as central_banks_meetings
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.services.central_banks_data import get_central_bank_data
from central_banks_overview.services.central_banks_inference import (
    CentralBankProbabilityMatrix,
)
from core.services.calendar import convert_to_display_timezone
from core.services.time_series_calculation import (
    ValueChangeType,
    calculate_value_change,
)
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
)
from economic_overview.services.economic_data import get_lookback_period_for_mode_change

logger = logging.getLogger(__name__)


class CentralBankRecapFigure(TypedDict):
    """Central bank data item."""

    label: str
    value: str


class _InflationRateValue(TypedDict):
    """Latest YoY inflation rate and the period it refers to."""

    yoy_pct: float
    period: date


def _format_inflation_rate_display(
    inflation_rate: _InflationRateValue | None,
) -> str:
    """Format YoY inflation as '0.9 % (Sep 26)', or '-' when unavailable."""
    if inflation_rate is None:
        return "-"
    period = inflation_rate["period"]
    return (
        f"{inflation_rate['yoy_pct']:.1f} % "
        f"({period.strftime('%b')} {period.strftime('%y')})"
    )


def _get_latest_yoy_inflation_rate(
    location: EconomicDataLocationChoices,
) -> _InflationRateValue | None:
    """Compute latest monthly YoY % from stored inflation index levels.

    Needs the latest value and the same calendar month one year earlier.
    """
    indicator = EconomicIndicatorInformationModel.objects.filter(
        location=location,
        category=EconomicDataCategoryChoices.HOUSEHOLD,
        subcategory=EconomicDataSubcategoryChoices.PRICES,
        series_label="Consumer Price Index",
    ).first()
    if indicator is None:
        return None
    if indicator.frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return None

    latest = (
        EconomicDataModel.objects.filter(
            indicator=indicator,
            period__isnull=False,
            data_value__isnull=False,
        )
        .order_by("-period")
        .first()
    )
    if latest is None or latest.period is None or latest.data_value is None:
        return None

    prior_period = get_lookback_period_for_mode_change(
        latest.period,
        EconomicPublicationFrequencyChoices.MONTHLY,
        IndicatorDisplayModeChoices.ANNUAL,
    )
    if prior_period is None:
        return None
    prior_economic_data = EconomicDataModel.objects.filter(
        indicator=indicator,
        period=prior_period,
        data_value__isnull=False,
    ).first()
    if prior_economic_data is None or prior_economic_data.data_value is None:
        return None

    yoy_pct = calculate_value_change(
        latest.data_value,
        prior_economic_data.data_value,
        ValueChangeType.PERCENT,
    )
    if yoy_pct is None:
        return None
    return _InflationRateValue(yoy_pct=yoy_pct, period=latest.period)


def _format_central_bank_next_meeting_figure_value(
    next_meeting_date: datetime | None,
) -> str:
    """Format the next meeting date for recap display, or 'N/A' when unknown."""
    if next_meeting_date is None:
        return "N/A"
    return convert_to_display_timezone(next_meeting_date).strftime("%Y-%m-%d")


def _list_central_bank_recap_inflation_figures(
    central_bank: CentralBankChoices,
) -> list[CentralBankRecapFigure]:
    """Return location-specific YoY inflation recap figures for one central bank."""
    inflation_figures: list[CentralBankRecapFigure]
    match central_bank:
        case CentralBankChoices.FRB:
            us_inflation = _format_inflation_rate_display(
                _get_latest_yoy_inflation_rate(EconomicDataLocationChoices.US)
            )
            inflation_figures = [
                CentralBankRecapFigure(label="US Inflation Rate", value=us_inflation),
            ]
        case CentralBankChoices.BOJ:
            japan_inflation = _format_inflation_rate_display(
                _get_latest_yoy_inflation_rate(EconomicDataLocationChoices.JP)
            )
            inflation_figures = [
                CentralBankRecapFigure(
                    label="Japan Inflation Rate", value=japan_inflation
                ),
            ]
        case CentralBankChoices.ECB:
            france_inflation = _format_inflation_rate_display(
                _get_latest_yoy_inflation_rate(EconomicDataLocationChoices.FR)
            )
            eurozone_inflation = _format_inflation_rate_display(
                _get_latest_yoy_inflation_rate(EconomicDataLocationChoices.EU)
            )
            inflation_figures = [
                CentralBankRecapFigure(
                    label="France Inflation Rate", value=france_inflation
                ),
                CentralBankRecapFigure(
                    label="Eurozone Inflation Rate", value=eurozone_inflation
                ),
            ]
    return inflation_figures


def list_central_bank_recap_figures(
    central_bank: CentralBankChoices, reference_date: date
) -> list[CentralBankRecapFigure]:
    """Return rate / next-meeting summary figures for one central bank.

    'Next Meeting' always uses the Market Watch as-of date.
    """
    effective_rate = central_banks_inference.get_central_bank_effective_rate(
        central_bank, reference_date
    )
    if not effective_rate:
        logger.warning(
            f"No effective rate found for {central_bank} on {reference_date}. Using fall back rate."
        )
        effective_rate = central_banks_inference.get_fall_back_rate(
            central_bank, reference_date
        )
    next_meeting_figure_value = _format_central_bank_next_meeting_figure_value(
        central_banks_meetings.get_central_bank_next_meeting_date(central_bank)
    )
    key_rate_figures = [
        CentralBankRecapFigure(
            label=key_rate.full_name,
            value=f"{key_rate.value} %" if key_rate.value else "N/A",
        )
        for key_rate in get_central_bank_data(
            central_banks=[central_bank], last_value=True
        )
    ]

    base_data = [
        CentralBankRecapFigure(
            label="Effective Rate",
            value=f"{effective_rate} %" if effective_rate else "N/A",
        ),
        *key_rate_figures,
        CentralBankRecapFigure(label="Next Meeting", value=next_meeting_figure_value),
    ]
    return base_data + _list_central_bank_recap_inflation_figures(central_bank)


def get_formatted_probability_matrix_for_central_bank(
    central_bank: CentralBankChoices,
    reference_date: date,
    meeting_dates_override: list[datetime] = [],
) -> CentralBankProbabilityMatrix | None:
    """Get formatted probability matrix for a central bank."""
    meeting_dates_override_dict = (
        {central_bank: meeting_dates_override} if meeting_dates_override else {}
    )

    cb_probability_matrices = (
        central_banks_inference.get_central_bank_probability_matrices(
            reference_date,
            [central_bank],
            meeting_dates_override=meeting_dates_override_dict,
        )
    )
    for prob_matrix in cb_probability_matrices:
        if prob_matrix["central_bank"] == central_bank:
            probability_matrix = prob_matrix["probability_matrix"]
            is_empty = not probability_matrix or all(
                not entry.get("probabilities", []) for entry in probability_matrix
            )
            if is_empty:
                return CentralBankProbabilityMatrix(
                    central_bank=prob_matrix["central_bank"],
                    meeting_dates=prob_matrix["meeting_dates"],
                    probability_matrix=[],
                )
            sorted_probability_matrix = sorted(
                probability_matrix,
                key=lambda x: x["expected_rate_step"],
            )
            return CentralBankProbabilityMatrix(
                central_bank=prob_matrix["central_bank"],
                meeting_dates=prob_matrix["meeting_dates"],
                probability_matrix=sorted_probability_matrix,
            )


def _recalculate_previous_probability_matrix(
    central_bank: CentralBankChoices,
    previous_date: date,
    meeting_dates_override: list[date],
) -> CentralBankProbabilityMatrix | None:
    """Recalculate previous probability matrix using meeting dates override."""
    meeting_dates_as_datetime: list[datetime] = [
        (
            datetime.combine(md, datetime.min.time())
            if isinstance(md, date) and not isinstance(md, datetime)
            else md
        )
        for md in meeting_dates_override
    ]
    return get_formatted_probability_matrix_for_central_bank(
        central_bank,
        previous_date,
        meeting_dates_override=meeting_dates_as_datetime,
    )


def get_formatted_probability_matrix_changes(
    probability_matrix: CentralBankProbabilityMatrix | None,
    previous_probability_matrix: CentralBankProbabilityMatrix | None,
    previous_date: date | None = None,
) -> CentralBankProbabilityMatrix | None:
    """Get formatted probability change matrix.

    When comparing matrices, the previous probability matrix is recalculated
    using the current meeting dates to ensure proper alignment, especially
    when a meeting has occurred and the meeting dates list has changed.

    The 'previous_probability_matrix' may have old meeting dates,
    in which case we need to recalculate it using the 'previous_date'.
    """
    if not probability_matrix or not previous_probability_matrix:
        return None

    current_is_empty = (
        not probability_matrix.get("probability_matrix")
        or len(probability_matrix.get("probability_matrix", [])) == 0
    )
    previous_is_empty = (
        not previous_probability_matrix.get("probability_matrix")
        or len(previous_probability_matrix.get("probability_matrix", [])) == 0
    )

    # Recalculate previous matrix using current meeting dates to ensure alignment
    # This handles cases where meeting dates change after a meeting occurs
    current_meeting_dates = probability_matrix["meeting_dates"]
    central_bank = probability_matrix["central_bank"]
    if previous_date and current_meeting_dates:
        previous_probability_matrix = _recalculate_previous_probability_matrix(
            central_bank, previous_date, current_meeting_dates
        )

    if not previous_probability_matrix:
        return None

    if current_is_empty or previous_is_empty:
        return CentralBankProbabilityMatrix(
            central_bank=probability_matrix["central_bank"],
            meeting_dates=probability_matrix["meeting_dates"],
            probability_matrix=[],
        )

    probability_change_matrix = central_banks_inference.calculate_probability_changes(
        probability_matrix, previous_probability_matrix
    )
    # Sort by expected_rate_step in ascending order
    sorted_probability_change_matrix = sorted(
        probability_change_matrix["probability_matrix"],
        key=lambda x: x["expected_rate_step"],
    )
    return CentralBankProbabilityMatrix(
        central_bank=probability_change_matrix["central_bank"],
        meeting_dates=probability_change_matrix["meeting_dates"],
        probability_matrix=sorted_probability_change_matrix,
    )
