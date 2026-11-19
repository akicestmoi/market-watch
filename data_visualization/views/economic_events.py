"""Economic events calendar page view."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import data_visualization.services.economic_events as economic_events


def economic_events_view(request: HttpRequest) -> HttpResponse:
    """Economic events calendar view."""
    upcoming_weeks = economic_events.group_upcoming_events_by_week()
    # Usage of dict: Django template context for the economic events page.
    context = {
        "upcoming_weeks": upcoming_weeks,
    }
    return render(request, "data_visualization/economic_events.html", context)
