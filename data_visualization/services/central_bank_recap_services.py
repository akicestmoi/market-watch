from datetime import date, datetime
from typing import List, Optional, TypedDict

import central_banks_overview.services.cb_inference_services as cb_inference_services
import central_banks_overview.services.cb_meetings_services as cb_meetings_services
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.services.cb_data_services import get_central_bank_data
from central_banks_overview.services.cb_inference_services import (
    CentralBankProbabilityMatrix,
)
from core.services import logger


class CentralBankDataItem(TypedDict):
    """Central bank data item."""

    label: str
    value: str


def get_central_bank_data_item(
    central_bank: CentralBankChoices, reference_date: date
) -> List[CentralBankDataItem]:
    """Get central bank data item."""
    effective_rate = cb_inference_services.get_central_bank_effective_rate(
        central_bank, reference_date
    )
    if not effective_rate:
        logger.warning(
            f"No effective rate found for {central_bank} on {reference_date}. Using fall back rate."
        )
        effective_rate = cb_inference_services.get_fall_back_rate(
            central_bank, reference_date
        )
    next_meeting_date = cb_meetings_services.get_central_bank_next_meeting_date(
        central_bank
    )
    next_meeting_date = (
        next_meeting_date.strftime("%Y-%m-%d") if next_meeting_date else "N/A"
    )
    data_items = [
        CentralBankDataItem(
            label=item.full_name, value=f"{item.value} %" if item.value else "N/A"
        )
        for item in get_central_bank_data(central_banks=[central_bank], last_value=True)
    ]

    base_data = [
        CentralBankDataItem(
            label="Effective Rate",
            value=f"{effective_rate} %" if effective_rate else "N/A",
        ),
        *data_items,
        CentralBankDataItem(label="Next Meeting", value=next_meeting_date),
    ]
    match central_bank:
        case CentralBankChoices.FRB:
            additional_data = [
                CentralBankDataItem(label="US Inflation Rate", value="3.0 %"),
            ]
        case CentralBankChoices.BOJ:
            additional_data = [
                CentralBankDataItem(label="Japan Inflation Rate", value="2.9 %"),
            ]
        case CentralBankChoices.ECB:
            additional_data = [
                CentralBankDataItem(label="France Inflation Rate", value="0.9 %"),
                CentralBankDataItem(label="Eurozone Inflation Rate", value="2.1 %"),
            ]
    return base_data + additional_data


def get_central_bank_formatted_probability_matrix(
    central_bank: CentralBankChoices,
    reference_date: date,
    meeting_dates_override: List[datetime] = [],
) -> Optional[CentralBankProbabilityMatrix]:
    """Get formatted probability matrix for a central bank."""
    meeting_dates_override_dict = (
        {central_bank: meeting_dates_override} if meeting_dates_override else {}
    )

    cb_probability_matrices = (
        cb_inference_services.get_central_bank_probability_matrices(
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
                return {
                    "central_bank": prob_matrix["central_bank"],
                    "meeting_dates": prob_matrix["meeting_dates"],
                    "probability_matrix": [],
                }
            sorted_probability_matrix = sorted(
                probability_matrix,
                key=lambda x: x["expected_rate_step"],
            )
            return {
                "central_bank": prob_matrix["central_bank"],
                "meeting_dates": prob_matrix["meeting_dates"],
                "probability_matrix": sorted_probability_matrix,
            }


def _recalculate_previous_probability_matrix(
    central_bank: CentralBankChoices,
    previous_date: date,
    meeting_dates_override: List[date],
) -> Optional[CentralBankProbabilityMatrix]:
    """Recalculate previous probability matrix using meeting dates override."""
    meeting_dates_as_datetime: List[datetime] = [
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
    probability_matrix: Optional[CentralBankProbabilityMatrix],
    previous_probability_matrix: Optional[CentralBankProbabilityMatrix],
    previous_date: Optional[date] = None,
) -> Optional[CentralBankProbabilityMatrix]:
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
        return {
            "central_bank": probability_matrix["central_bank"],
            "meeting_dates": probability_matrix["meeting_dates"],
            "probability_matrix": [],
        }

    probability_change_matrix = cb_inference_services.calculate_probability_changes(
        probability_matrix, previous_probability_matrix
    )
    # Sort by expected_rate_step in ascending order
    sorted_probability_change_matrix = sorted(
        probability_change_matrix["probability_matrix"],
        key=lambda x: x["expected_rate_step"],
    )
    return {
        "central_bank": probability_change_matrix["central_bank"],
        "meeting_dates": probability_change_matrix["meeting_dates"],
        "probability_matrix": sorted_probability_change_matrix,
    }
