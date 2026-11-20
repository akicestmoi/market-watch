"""Tests for the sector-analysis page view."""

from django.test import Client, TestCase
from django.urls import resolve
from freezegun import freeze_time

from core.testing import read_file_content
from data_visualization.services.sector_analysis import _SectorAnalysisPageData
from data_visualization.views.sector_analysis import (
    _SectorAnalysisPageContext,
    sector_analysis_view,
)
from market_overview.models.common import EquityIndexChoices, LocationChoices

_EXPECTED_US_HTML = read_file_content(
    "data_visualization/tests/mock_web_data/sector_analysis/placeholder.html"
)
_EXPECTED_FR_HTML = read_file_content(
    "data_visualization/tests/mock_web_data/sector_analysis/france_on_date.html"
)


def _get_empty_page_context(
    location: LocationChoices,
    equity_index: EquityIndexChoices,
    reference_date: str,
    default_reference_date: str,
) -> _SectorAnalysisPageContext:
    """Return an empty sector-analysis page context for one region and date."""
    return _SectorAnalysisPageContext(
        region=location.value,
        reference_date=reference_date,
        default_reference_date=default_reference_date,
        page_data=_SectorAnalysisPageData(
            location=location,
            equity_index=equity_index,
            as_of=reference_date,
            selected_sector=None,
            selected_subsector=None,
            sector_history=[],
            sector_day=[],
            subsector_day=[],
            earnings_card=[],
        ),
    )


@freeze_time("2025-12-16")
class TestSectorAnalysisView(TestCase):
    """Test cases for 'sector_analysis_view'."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/sector-analysis/"

    def test_sector_analysis_view_success(self):
        """
        GIVEN the sector analysis page with no stored subsector moves
        WHEN accessing the view with defaults
        THEN the empty US page renders for the market-watch as-of date
        """
        response = self.client.get(self.base_url)

        assert resolve(self.base_url).func is sector_analysis_view
        assert response.status_code == 200
        assert {
            "region": response.context["region"],
            "reference_date": response.context["reference_date"],
            "default_reference_date": response.context["default_reference_date"],
            "page_data": response.context["page_data"],
        } == _get_empty_page_context(
            LocationChoices.US,
            EquityIndexChoices.SPX,
            "2025-12-15",
            "2025-12-15",
        )
        assert response.content == _EXPECTED_US_HTML

    def test_sector_analysis_view_region_and_date(self):
        """
        GIVEN a FR region and explicit target date with no stored moves
        WHEN accessing the view
        THEN the page context and HTML use that region and date
        """
        response = self.client.get(
            self.base_url,
            {"region": "FR", "reference_date": "2026-11-19"},
        )

        assert response.status_code == 200
        assert {
            "region": response.context["region"],
            "reference_date": response.context["reference_date"],
            "default_reference_date": response.context["default_reference_date"],
            "page_data": response.context["page_data"],
        } == _get_empty_page_context(
            LocationChoices.FR,
            EquityIndexChoices.CAC40,
            "2026-11-19",
            "2025-12-15",
        )
        assert response.content == _EXPECTED_FR_HTML
