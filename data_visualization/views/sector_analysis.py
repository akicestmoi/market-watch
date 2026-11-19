"""Sector analysis page view."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def sector_analysis_view(request: HttpRequest) -> HttpResponse:
    """Sector analysis view."""
    return render(request, "data_visualization/sector_analysis.html")
