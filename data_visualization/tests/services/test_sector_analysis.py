"""Tests for sector-analysis page payload assembly."""

from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from data_visualization.services.sector_analysis import (
    _get_sector_day_slices_from_subsector_moves,
    _SectorAnalysisPageData,
    get_sector_analysis_page_data,
)
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.models.sector_analysis import IndexSubsectorDailyMoveModel
from market_overview.services.sector_analysis import (
    SubsectorDailyMove,
    SubsectorTopMover,
)


def _get_oil_top_mover() -> SubsectorTopMover:
    """Return the stored top mover for the oil subsector fixture."""
    return SubsectorTopMover(
        company="Oil Co",
        ticker="OIL",
        weight=10.0,
        daily_return=-3.0,
        contribution=-0.3,
    )


def _get_software_top_mover() -> SubsectorTopMover:
    """Return the stored top mover for the software subsector fixture."""
    return SubsectorTopMover(
        company="Soft Co",
        ticker="SOFT",
        weight=40.0,
        daily_return=1.5,
        contribution=0.6,
    )


def _get_technology_and_energy_subsector_moves() -> list[SubsectorDailyMove]:
    """Return two subsector moves used to roll a sector slice up."""
    return [
        SubsectorDailyMove(
            date="2026-11-18",
            equity_index=EquityIndexChoices.SPX,
            sector="Technology",
            subsector="Software",
            weight=40.0,
            daily_return=-0.25,
            contribution=-0.1,
            top_movers=[],
        ),
        SubsectorDailyMove(
            date="2026-11-18",
            equity_index=EquityIndexChoices.SPX,
            sector="Technology",
            subsector="Hardware",
            weight=10.0,
            daily_return=2.0,
            contribution=0.2,
            top_movers=[],
        ),
    ]


def _create_technology_and_energy_moves() -> None:
    """Store oil and software subsector moves for the US page fixture."""
    IndexSubsectorDailyMoveModel.objects.bulk_create(
        [
            IndexSubsectorDailyMoveModel(
                date=date(2026, 11, 19),
                equity_index=EquityIndexChoices.SPX.value,
                sector="Technology",
                subsector="Software",
                weight=40.0,
                daily_return=1.5,
                contribution=0.6,
                top_movers=[_get_software_top_mover()],
            ),
            IndexSubsectorDailyMoveModel(
                date=date(2026, 11, 19),
                equity_index=EquityIndexChoices.SPX.value,
                sector="Energy",
                subsector="Oil",
                weight=10.0,
                daily_return=-3.0,
                contribution=-0.3,
                top_movers=[_get_oil_top_mover()],
            ),
        ]
    )


def _get_expected_page_with_biggest_contributor() -> _SectorAnalysisPageData:
    """Return the page payload that selects software as the biggest contributor."""
    return _SectorAnalysisPageData(
        location=LocationChoices.US,
        equity_index=EquityIndexChoices.SPX,
        as_of="2026-11-19",
        selected_sector="Technology",
        selected_subsector="Software",
        sector_history=[
            {
                "date": "2026-11-19",
                "returns_by_sector": {"Energy": -3.0, "Technology": 1.5},
            }
        ],
        sector_day=[
            {
                "name": "Energy",
                "weight": 10.0,
                "daily_return": -3.0,
                "contribution": -0.3,
            },
            {
                "name": "Technology",
                "weight": 40.0,
                "daily_return": 1.5,
                "contribution": 0.6,
            },
        ],
        subsector_day=[
            {
                "name": "Oil",
                "sector": "Energy",
                "weight": 10.0,
                "daily_return": -3.0,
                "contribution": -0.3,
                "top_movers": [_get_oil_top_mover()],
            },
            {
                "name": "Software",
                "sector": "Technology",
                "weight": 40.0,
                "daily_return": 1.5,
                "contribution": 0.6,
                "top_movers": [_get_software_top_mover()],
            },
        ],
        earnings_card=[],
    )


class TestSectorDaySlices(TestCase):
    """Test cases for deriving sector slices from subsector moves."""

    def test_get_sector_day_slices_from_subsector_moves(self):
        """
        GIVEN two subsector moves in the same sector
        WHEN sector slices are derived
        THEN the sector weight, return, and contribution are set
        """
        result = _get_sector_day_slices_from_subsector_moves(
            _get_technology_and_energy_subsector_moves()
        )

        assert result == [
            {
                "name": "Technology",
                "weight": 50.0,
                "daily_return": 0.2,
                "contribution": 0.1,
            }
        ]


class TestGetSectorAnalysisPageData(TestCase):
    """Test cases for 'get_sector_analysis_page_data'."""

    @patch(
        "data_visualization.services.sector_analysis.set_cached_sector_analysis_page"
    )
    @patch(
        "data_visualization.services.sector_analysis.get_cached_sector_analysis_page"
    )
    def test_get_sector_analysis_page_data_empty(
        self,
        mock_get_cached_sector_analysis_page: Mock,
        mock_set_cached_sector_analysis_page: Mock,
    ):
        """
        GIVEN no stored subsector moves for the target date
        WHEN get_sector_analysis_page_data is called
        THEN an empty page payload is returned for that region and date
        """
        mock_get_cached_sector_analysis_page.return_value = None

        result = get_sector_analysis_page_data(
            LocationChoices.US,
            date(2026, 11, 19),
        )

        assert result == _SectorAnalysisPageData(
            location=LocationChoices.US,
            equity_index=EquityIndexChoices.SPX,
            as_of="2026-11-19",
            selected_sector=None,
            selected_subsector=None,
            sector_history=[],
            sector_day=[],
            subsector_day=[],
            earnings_card=[],
        )
        mock_set_cached_sector_analysis_page.assert_called_once_with(
            LocationChoices.US,
            date(2026, 11, 19),
            result,
        )

    @patch(
        "data_visualization.services.sector_analysis.set_cached_sector_analysis_page"
    )
    @patch(
        "data_visualization.services.sector_analysis.get_cached_sector_analysis_page"
    )
    def test_get_sector_analysis_page_data_selects_biggest_contributor(
        self,
        mock_get_cached_sector_analysis_page: Mock,
        mock_set_cached_sector_analysis_page: Mock,
    ):
        """
        GIVEN two subsectors with different absolute contributions
        WHEN get_sector_analysis_page_data is called
        THEN selected sector and subsector follow the biggest contributor
        """
        mock_get_cached_sector_analysis_page.return_value = None
        _create_technology_and_energy_moves()

        result = get_sector_analysis_page_data(
            LocationChoices.US,
            date(2026, 11, 19),
        )

        assert result == _get_expected_page_with_biggest_contributor()
        mock_set_cached_sector_analysis_page.assert_called_once_with(
            LocationChoices.US,
            date(2026, 11, 19),
            result,
        )
