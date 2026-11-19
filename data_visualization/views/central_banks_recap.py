"""Central banks recap page view."""

import json
from datetime import date
from typing import TypedDict

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import data_visualization.services.central_banks_recap as central_banks_recap
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.services.central_banks_inference import (
    CentralBankProbabilityMatrix,
)
from data_visualization.services.central_banks_recap import CentralBankRecapFigure
from data_visualization.views.common import (
    get_recap_dates_base_context,
    parse_recap_reference_and_previous_dates,
)


class _CentralBankRecapPagePayload(TypedDict):
    """One central bank block in the central banks recap template context."""

    display_name: str
    data: list[CentralBankRecapFigure]
    probability_matrix: CentralBankProbabilityMatrix | None
    probability_change_matrix: CentralBankProbabilityMatrix | None


def _get_central_bank_recap_payload(
    central_bank: CentralBankChoices,
    reference_date: date,
    previous_date: date,
    errors: dict[str, str],
) -> _CentralBankRecapPagePayload:
    """Load recap figures and probability matrices for one central bank."""
    central_bank_recap_figures = []
    probability_matrix = None
    probability_change_matrix = None

    try:
        central_bank_recap_figures = (
            central_banks_recap.list_central_bank_recap_figures(
                central_bank, reference_date
            )
        )
    except Exception as e:
        errors[f"{central_bank.value}_data_item"] = (
            f"Error getting central bank data item for {central_bank.label}: {e}"
        )

    try:
        probability_matrix = (
            central_banks_recap.get_formatted_probability_matrix_for_central_bank(
                central_bank, reference_date
            )
        )
    except Exception as e:
        errors[f"{central_bank.value}_probability_matrix"] = (
            f"Error getting probability matrix for {central_bank.label}: {e}"
        )

    try:
        previous_probability_matrix = (
            central_banks_recap.get_formatted_probability_matrix_for_central_bank(
                central_bank, previous_date
            )
        )
        probability_change_matrix = (
            central_banks_recap.get_formatted_probability_matrix_changes(
                probability_matrix,
                previous_probability_matrix,
                previous_date=previous_date,
            )
        )
    except Exception as e:
        errors[f"{central_bank.value}_probability_change_matrix"] = (
            f"Error getting probability change matrix for {central_bank.label}: {e}"
        )

    return _CentralBankRecapPagePayload(
        display_name=str(central_bank.label),
        data=central_bank_recap_figures,
        probability_matrix=probability_matrix,
        probability_change_matrix=probability_change_matrix,
    )


def central_banks_recap_view(request: HttpRequest) -> HttpResponse:
    """Central Banks Overview View."""
    recap_dates = parse_recap_reference_and_previous_dates(request)
    # Usage of dict: template error_messages keys by field name.
    errors: dict[str, str] = {}

    base_context = get_recap_dates_base_context(recap_dates)
    if recap_dates.reference_date >= date.today():
        errors["reference_date"] = (
            f"Reference date: {recap_dates.reference_date} must be before today: {date.today()}."
        )

    # Usage of dict: keys are CentralBankChoices; values are page payloads.
    central_banks_data: dict[CentralBankChoices, _CentralBankRecapPagePayload] = {}
    for central_bank in CentralBankChoices.ordered():
        central_banks_data[central_bank] = _get_central_bank_recap_payload(
            central_bank,
            recap_dates.reference_date,
            recap_dates.previous_date,
            errors,
        )

    # Usage of dict: Django template context for the central banks recap page.
    context = {
        **base_context,
        "central_banks_data": central_banks_data,
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/central_banks_recap.html", context)
