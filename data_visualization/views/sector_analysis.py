"""Render the sector-analysis page for one region and target date."""

from datetime import date, datetime
from typing import NamedTuple, TypedDict

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import market_overview.services.sector_analysis as sector_analysis
from core.services.calendar import get_market_watch_as_of_date
from data_visualization.services.sector_analysis import (
    _SectorAnalysisPageData,
    get_sector_analysis_page_data,
)
from market_overview.models.common import LocationChoices

_SECTOR_ANALYSIS_REGIONS = frozenset(
    {
        LocationChoices.US,
        LocationChoices.FR,
        LocationChoices.JP,
    }
)


class _SectorAnalysisPageContext(TypedDict):
    """Hold the template context for one sector-analysis page."""

    region: str
    reference_date: str
    default_reference_date: str
    page_data: _SectorAnalysisPageData


class _SectorAnalysisPageSelection(NamedTuple):
    """Hold the region and target date chosen for the sector-analysis page."""

    location: LocationChoices
    reference_date: date
    default_reference_date: date


def _get_sector_analysis_page_selection(
    request: HttpRequest,
) -> _SectorAnalysisPageSelection:
    """Parse the region and target date from the sector-analysis query string."""
    region_param = request.GET.get("region", LocationChoices.US.value)
    try:
        location = LocationChoices(region_param)
    except ValueError:
        location = LocationChoices.US
    if location not in _SECTOR_ANALYSIS_REGIONS:
        location = LocationChoices.US

    market_watch_as_of = get_market_watch_as_of_date()
    latest_with_data = sector_analysis.get_latest_sector_analysis_date(location)
    default_reference_date = latest_with_data or market_watch_as_of

    reference_date_raw = request.GET.get("reference_date")
    if reference_date_raw:
        reference_date = datetime.fromisoformat(reference_date_raw).date()
    else:
        reference_date = default_reference_date

    return _SectorAnalysisPageSelection(
        location=location,
        reference_date=reference_date,
        default_reference_date=default_reference_date,
    )


def sector_analysis_view(request: HttpRequest) -> HttpResponse:
    """Render the sector-analysis page for one region and target date."""
    selection = _get_sector_analysis_page_selection(request)
    page_context = _SectorAnalysisPageContext(
        region=selection.location.value,
        reference_date=selection.reference_date.isoformat(),
        default_reference_date=selection.default_reference_date.isoformat(),
        page_data=get_sector_analysis_page_data(
            selection.location,
            selection.reference_date,
        ),
    )
    return render(
        request,
        "data_visualization/sector_analysis.html",
        page_context,
    )
