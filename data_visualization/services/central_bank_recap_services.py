from datetime import date
from typing import List, Optional, TypedDict

import central_banks_overview.services.cb_inference_services as cb_inference_services
import central_banks_overview.services.cb_meetings_services as cb_meetings_services
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.services.cb_data_services import get_central_bank_data
from central_banks_overview.services.cb_inference_services import (
    CentralBankProbabilityMatrix,
)


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
) -> Optional[CentralBankProbabilityMatrix]:
    """Get formatted probability matrix for a central bank."""
    cb_probability_matrices = (
        cb_inference_services.get_central_bank_probability_matrices(
            reference_date, [central_bank]
        )
    )
    for prob_matrix in cb_probability_matrices:
        if prob_matrix["central_bank"] == central_bank:
            sorted_probability_matrix = sorted(
                prob_matrix["probability_matrix"],
                key=lambda x: x["expected_rate_step"],
            )
            return {
                "central_bank": prob_matrix["central_bank"],
                "meeting_dates": prob_matrix["meeting_dates"],
                "probability_matrix": sorted_probability_matrix,
            }


def get_formatted_probability_matrix_changes(
    probability_matrix: Optional[CentralBankProbabilityMatrix],
    previous_probability_matrix: Optional[CentralBankProbabilityMatrix],
) -> Optional[CentralBankProbabilityMatrix]:
    """Get formatted probability change matrix."""
    if not probability_matrix or not previous_probability_matrix:
        return None

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
