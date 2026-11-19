"""Economic recap page view."""

import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from data_visualization.services.config import (
    ECONOMIC_RECAP_AS_OF_MONTH_LABELS,
    ECONOMIC_RECAP_LOCATIONS,
    ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER,
)
from data_visualization.services.economic_recap import (
    final_data as economic_recap_final_data,
)
from data_visualization.services.economic_recap import (
    table_filter as economic_recap_table_filter,
)
from data_visualization.services.economic_recap.table_content import EconomicRecapItem
from data_visualization.services.economic_recap.table_filter import (
    EconomicRecapAsOfAvailability,
    EconomicRecapAsOfSelection,
    EconomicRecapComparisonChoices,
)
from data_visualization.services.economic_recap.table_structure import (
    EconomicRecapCategoryGroup,
)


def _build_economic_recap_as_of_json(
    as_of_selection: EconomicRecapAsOfSelection,
    as_of_month_display: int | None,
    comparison: EconomicRecapComparisonChoices,
    as_of_availability: EconomicRecapAsOfAvailability,
) -> str:
    """Serialize as-of state for the economic recap front-end script."""
    return json.dumps(
        {
            "year": as_of_selection.year,
            "quarter": as_of_selection.quarter,
            "month": as_of_selection.month,
            "month_display": as_of_month_display,
            "end_date": (
                as_of_selection.end_date.isoformat()
                if as_of_selection.end_date is not None
                else None
            ),
            "comparison": comparison.value,
            "available_years": sorted(as_of_availability.years),
            "available_quarters": sorted(as_of_availability.quarters),
            "available_months": sorted(as_of_availability.months),
            "quarter_end_month_by_quarter": ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER,
        }
    )


# Usage of dict: Django template context for the economic recap page.
def _build_economic_recap_template_context(
    selected_region: str,
    economic_data: list[EconomicRecapCategoryGroup],
    nominal_gdp_items: list[EconomicRecapItem],
    as_of_selection: EconomicRecapAsOfSelection,
    comparison: EconomicRecapComparisonChoices,
    as_of_availability: EconomicRecapAsOfAvailability,
    as_of_years: list[int],
    as_of_query: str,
) -> dict:
    """Assemble template context for the economic recap page."""
    # Month dropdown only reflects an explicit month As-of (not quarter/year shortcuts).
    as_of_month_display = as_of_selection.month
    location_codes = [selected_region]
    # Usage of dict: Django template context for the economic recap page.
    return {
        "regions": [location.value for location in ECONOMIC_RECAP_LOCATIONS],
        "selected_region": selected_region,
        "locations": location_codes,
        "economic_data": economic_data,
        "economic_data_json": json.dumps(economic_data, default=str),
        "nominal_gdp_json": json.dumps(nominal_gdp_items, default=str),
        "locations_json": json.dumps(location_codes),
        "as_of_years": as_of_years,
        "as_of_year": as_of_selection.year,
        "as_of_quarter": as_of_selection.quarter,
        "as_of_month": as_of_selection.month,
        "as_of_month_display": as_of_month_display,
        "as_of_month_choices": [
            {"value": month, "label": ECONOMIC_RECAP_AS_OF_MONTH_LABELS[month]}
            for month in range(1, 13)
        ],
        "as_of_end_date": (
            as_of_selection.end_date.isoformat()
            if as_of_selection.end_date is not None
            else None
        ),
        "as_of_query": as_of_query,
        "as_of_available_years": sorted(as_of_availability.years),
        "as_of_available_quarters": sorted(as_of_availability.quarters),
        "as_of_available_months": sorted(as_of_availability.months),
        "comparison": comparison.value,
        "as_of_json": _build_economic_recap_as_of_json(
            as_of_selection,
            as_of_month_display,
            comparison,
            as_of_availability,
        ),
    }


def economic_recap_view(request: HttpRequest) -> HttpResponse:
    """Economic Overview View."""
    selected = economic_recap_table_filter.get_selected_location_for_economic_recap(
        request.GET.get("region")
    )
    economic_data = economic_recap_final_data.get_economic_recap_data(
        [selected.selected_location]
    )
    nominal_gdp_items = economic_recap_final_data.get_nominal_gdp_recap_items(
        [selected.selected_location]
    )
    as_of_selection = economic_recap_table_filter.parse_economic_recap_as_of(
        as_of_year=request.GET.get("as_of_year"),
        as_of_quarter=request.GET.get("as_of_quarter"),
        as_of_month=request.GET.get("as_of_month"),
    )
    comparison = economic_recap_table_filter.parse_economic_recap_comparison(
        request.GET.get("comparison"),
        year=as_of_selection.year,
        quarter=as_of_selection.quarter,
        month=as_of_selection.month,
    )
    as_of_availability = (
        economic_recap_table_filter.get_as_of_availability_for_economic_recap(
            economic_data, year=as_of_selection.year
        )
    )
    context = _build_economic_recap_template_context(
        selected.selected_region,
        economic_data,
        nominal_gdp_items,
        as_of_selection,
        comparison,
        as_of_availability,
        economic_recap_table_filter.list_as_of_years_for_economic_recap(),
        economic_recap_table_filter.build_economic_recap_as_of_query_string(
            as_of_selection,
            comparison=comparison,
        ),
    )
    return render(request, "data_visualization/economic_recap.html", context)
