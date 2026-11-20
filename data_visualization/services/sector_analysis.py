"""Build sector-analysis page payloads from stored subsector moves and earnings."""

from collections import defaultdict
from datetime import date, timedelta
from typing import TypedDict

from pydantic import TypeAdapter

from data_visualization.services.cache import (
    get_cached_sector_analysis_page,
    set_cached_sector_analysis_page,
)
from data_visualization.services.config import SECTOR_ANALYSIS_HISTORY_CALENDAR_DAYS
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.services.config import EQUITY_INDEX_BY_LOCATION
from market_overview.services.earnings import (
    EarningsWatchlistCompany,
    list_earnings_watchlist_companies_for_location,
)
from market_overview.services.sector_analysis import (
    SubsectorDailyMove,
    SubsectorTopMover,
    list_subsector_daily_moves_for_equity_index_in_date_range,
    list_subsector_daily_moves_for_equity_index_on_date,
)


class _SectorDaySlice(TypedDict):
    """Hold one sector slice for the day pie, rolled up from subsector moves."""

    name: str
    weight: float
    daily_return: float
    contribution: float


class _SubsectorDaySlice(TypedDict):
    """Hold one subsector slice for the day pie, including top equity movers."""

    name: str
    sector: str
    weight: float
    daily_return: float
    contribution: float
    top_movers: list[SubsectorTopMover]


class _SectorHistoryPoint(TypedDict):
    """Hold one date's sector returns for the historical line chart."""

    date: str
    # Usage of dict: keys are sector names; values are that day's sector return %.
    returns_by_sector: dict[str, float]


class _SectorAnalysisPageData(TypedDict):
    """Hold the display payload for one region and date on the sector page."""

    location: LocationChoices
    equity_index: EquityIndexChoices
    as_of: str | None
    selected_sector: str | None
    selected_subsector: str | None
    sector_history: list[_SectorHistoryPoint]
    sector_day: list[_SectorDaySlice]
    subsector_day: list[_SubsectorDaySlice]
    earnings_card: list[EarningsWatchlistCompany]


_SECTOR_ANALYSIS_PAGE_ADAPTER: TypeAdapter[_SectorAnalysisPageData] = TypeAdapter(
    _SectorAnalysisPageData
)


def _get_sector_day_slices_from_subsector_moves(
    subsector_moves: list[SubsectorDailyMove],
) -> list[_SectorDaySlice]:
    """Roll subsector moves up into one weighted sector slice per sector."""
    # Usage of dict: keys are sector names; values are that sector's moves.
    moves_by_sector: dict[str, list[SubsectorDailyMove]] = defaultdict(list)
    for subsector_move in subsector_moves:
        moves_by_sector[subsector_move["sector"]].append(subsector_move)

    sector_day_slices: list[_SectorDaySlice] = []
    for sector_name in sorted(moves_by_sector):
        sector_moves = moves_by_sector[sector_name]
        weight = sum(subsector_move["weight"] for subsector_move in sector_moves)
        if weight == 0:
            raise ValueError(f"Sector {sector_name!r} has zero total weight.")
        weighted_return = sum(
            subsector_move["weight"] * subsector_move["daily_return"]
            for subsector_move in sector_moves
        )
        sector_day_slices.append(
            _SectorDaySlice(
                name=sector_name,
                weight=weight,
                daily_return=weighted_return / weight,
                contribution=sum(
                    subsector_move["contribution"] for subsector_move in sector_moves
                ),
            )
        )
    return sector_day_slices


def _list_subsector_day_slices(
    subsector_moves: list[SubsectorDailyMove],
) -> list[_SubsectorDaySlice]:
    """Return subsector pie slices with top movers from stored subsector moves."""
    return [
        _SubsectorDaySlice(
            name=subsector_move["subsector"],
            sector=subsector_move["sector"],
            weight=subsector_move["weight"],
            daily_return=subsector_move["daily_return"],
            contribution=subsector_move["contribution"],
            top_movers=list(subsector_move["top_movers"]),
        )
        for subsector_move in subsector_moves
    ]


def _list_sector_history_points(
    equity_index: EquityIndexChoices,
    as_of: date,
) -> list[_SectorHistoryPoint]:
    """Return sector daily-return history ending on 'as_of' for the line chart."""
    history_start = as_of - timedelta(days=SECTOR_ANALYSIS_HISTORY_CALENDAR_DAYS)
    subsector_moves = list_subsector_daily_moves_for_equity_index_in_date_range(
        equity_index,
        history_start,
        as_of,
    )
    # Usage of dict: keys are ISO dates; values are that day's subsector moves.
    moves_by_date: dict[str, list[SubsectorDailyMove]] = defaultdict(list)
    for subsector_move in subsector_moves:
        moves_by_date[subsector_move["date"]].append(subsector_move)

    history_points: list[_SectorHistoryPoint] = []
    for history_date in sorted(moves_by_date):
        sector_slices = _get_sector_day_slices_from_subsector_moves(
            moves_by_date[history_date]
        )
        history_points.append(
            _SectorHistoryPoint(
                date=history_date,
                returns_by_sector={
                    sector_slice["name"]: sector_slice["daily_return"]
                    for sector_slice in sector_slices
                },
            )
        )
    return history_points


def _get_subsector_with_biggest_contribution(
    subsector_day: list[_SubsectorDaySlice],
) -> _SubsectorDaySlice | None:
    """Return the subsector slice with the largest absolute index contribution."""
    if not subsector_day:
        return None
    # Biggest contributor wins; ties break on absolute return, then name.
    return max(
        subsector_day,
        key=lambda subsector_slice: (
            abs(subsector_slice["contribution"]),
            abs(subsector_slice["daily_return"]),
            subsector_slice["name"],
        ),
    )


def _get_equity_index_for_location(location: LocationChoices) -> EquityIndexChoices:
    """Return the equity index mapped to one sector-analysis location."""
    equity_index = EQUITY_INDEX_BY_LOCATION.get(location)
    if equity_index is None:
        raise ValueError(f"No equity index mapped for location {location.value}.")
    return equity_index


def _get_empty_sector_analysis_page_data(
    location: LocationChoices,
    equity_index: EquityIndexChoices,
    as_of: date,
    earnings_card: list[EarningsWatchlistCompany],
) -> _SectorAnalysisPageData:
    """Return a page payload with no sector moves for the target date."""
    return _SectorAnalysisPageData(
        location=location,
        equity_index=equity_index,
        as_of=as_of.isoformat(),
        selected_sector=None,
        selected_subsector=None,
        sector_history=[],
        sector_day=[],
        subsector_day=[],
        earnings_card=earnings_card,
    )


def _get_populated_sector_analysis_page_data(
    location: LocationChoices,
    equity_index: EquityIndexChoices,
    as_of: date,
    earnings_card: list[EarningsWatchlistCompany],
    subsector_moves: list[SubsectorDailyMove],
) -> _SectorAnalysisPageData:
    """Return a page payload from the subsector moves stored on the target date."""
    sector_day = _get_sector_day_slices_from_subsector_moves(subsector_moves)
    subsector_day = _list_subsector_day_slices(subsector_moves)
    selected_subsector_slice = _get_subsector_with_biggest_contribution(subsector_day)
    selected_sector = None
    selected_subsector = None
    if selected_subsector_slice is not None:
        selected_sector = selected_subsector_slice["sector"]
        selected_subsector = selected_subsector_slice["name"]
    return _SectorAnalysisPageData(
        location=location,
        equity_index=equity_index,
        as_of=as_of.isoformat(),
        selected_sector=selected_sector,
        selected_subsector=selected_subsector,
        sector_history=_list_sector_history_points(equity_index, as_of),
        sector_day=sector_day,
        subsector_day=subsector_day,
        earnings_card=earnings_card,
    )


def get_sector_analysis_page_data(
    location: LocationChoices,
    as_of: date,
) -> _SectorAnalysisPageData:
    """Return the sector-analysis page payload for one region and target date.

    Results are Redis-cached and versioned by subsector-move and earnings state.
    """
    cached = get_cached_sector_analysis_page(
        location,
        as_of,
        _SECTOR_ANALYSIS_PAGE_ADAPTER,
    )
    if cached is not None:
        return cached

    equity_index = _get_equity_index_for_location(location)
    earnings_card = list_earnings_watchlist_companies_for_location(location)
    subsector_moves = list_subsector_daily_moves_for_equity_index_on_date(
        equity_index,
        as_of,
    )
    if not subsector_moves:
        page_data = _get_empty_sector_analysis_page_data(
            location,
            equity_index,
            as_of,
            earnings_card,
        )
    else:
        page_data = _get_populated_sector_analysis_page_data(
            location,
            equity_index,
            as_of,
            earnings_card,
            subsector_moves,
        )
    set_cached_sector_analysis_page(location, as_of, page_data)
    return page_data
