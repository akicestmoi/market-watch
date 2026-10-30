"""Build central-bank recap payloads for the visualization UI."""

from datetime import date, datetime
from typing import TypedDict

import central_banks_overview.services.central_banks_inference as central_banks_inference
import central_banks_overview.services.central_banks_meetings as central_banks_meetings
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.services.central_banks_data import get_central_bank_data
from central_banks_overview.services.central_banks_inference import (
    CentralBankProbabilityMatrix,
)
from core.services import (
    ValueChangeType,
    calculate_value_change,
    convert_to_display_timezone,
    logger,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


class _CentralBankDataItem(TypedDict):
    """Central bank data item."""

    label: str
    value: str


class _InflationRateObservation(TypedDict):
    """Latest YoY inflation rate and the observation period it refers to."""

    yoy_pct: float
    period: date


def _format_inflation_rate_display(
    observation: _InflationRateObservation | None,
) -> str:
    """Format YoY inflation as ``0.9 % (Sep 26)``, or ``-`` when unavailable."""
    if observation is None:
        return "-"
    period = observation["period"]
    return (
        f"{observation['yoy_pct']:.1f} % "
        f"({period.strftime('%b')} {period.strftime('%y')})"
    )


def _get_latest_yoy_inflation_rate(
    location: EconomicDataLocationChoices,
) -> _InflationRateObservation | None:
    """Compute latest monthly YoY % from stored inflation index levels.

    Needs the latest observation and the same calendar month one year earlier.
    """
    indicator = EconomicIndicatorInformationModel.objects.filter(
        location=location,
        category=EconomicDataCategoryChoices.INFLATION,
        type="Consumer Price Index",
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

    prior_period = date(latest.period.year - 1, latest.period.month, 1)
    prior_row = EconomicDataModel.objects.filter(
        indicator=indicator,
        period=prior_period,
        data_value__isnull=False,
    ).first()
    if prior_row is None or prior_row.data_value is None:
        return None

    yoy_pct = calculate_value_change(
        latest.data_value,
        prior_row.data_value,
        ValueChangeType.PERCENT,
    )
    if yoy_pct is None:
        return None
    return _InflationRateObservation(yoy_pct=yoy_pct, period=latest.period)


def get_central_bank_data_item(
    central_bank: CentralBankChoices, reference_date: date
) -> list[_CentralBankDataItem]:
    """Build rate / next-meeting summary rows for one central bank.

    ``Next Meeting`` always uses the Market Watch as-of date.
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
    next_meeting_date = central_banks_meetings.get_central_bank_next_meeting_date(
        central_bank
    )
    next_meeting_date = (
        convert_to_display_timezone(next_meeting_date).strftime("%Y-%m-%d")
        if next_meeting_date
        else "N/A"
    )
    data_items = [
        _CentralBankDataItem(
            label=item.full_name, value=f"{item.value} %" if item.value else "N/A"
        )
        for item in get_central_bank_data(central_banks=[central_bank], last_value=True)
    ]

    base_data = [
        _CentralBankDataItem(
            label="Effective Rate",
            value=f"{effective_rate} %" if effective_rate else "N/A",
        ),
        *data_items,
        _CentralBankDataItem(label="Next Meeting", value=next_meeting_date),
    ]
    match central_bank:
        case CentralBankChoices.FRB:
            us_inflation = _format_inflation_rate_display(
                _get_latest_yoy_inflation_rate(EconomicDataLocationChoices.US)
            )
            additional_data = [
                _CentralBankDataItem(label="US Inflation Rate", value=us_inflation),
            ]
        case CentralBankChoices.BOJ:
            japan_inflation = _format_inflation_rate_display(
                _get_latest_yoy_inflation_rate(EconomicDataLocationChoices.JP)
            )
            additional_data = [
                _CentralBankDataItem(
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
            additional_data = [
                _CentralBankDataItem(
                    label="France Inflation Rate", value=france_inflation
                ),
                _CentralBankDataItem(
                    label="Eurozone Inflation Rate", value=eurozone_inflation
                ),
            ]
    return base_data + additional_data


def get_central_bank_formatted_probability_matrix(
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
    return get_central_bank_formatted_probability_matrix(
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
