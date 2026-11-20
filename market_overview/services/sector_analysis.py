"""Load the single-name catalog and ingest daily subsector weight / return moves."""

import json
import logging
from collections import defaultdict
from datetime import date
from typing import NamedTuple, TypedDict

from pydantic import TypeAdapter

from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.models.sector_analysis import IndexSubsectorDailyMoveModel
from market_overview.services.config import EQUITY_INDEX_BY_LOCATION, SINGLE_NAMES_JSON
from market_overview.services.scrapers.weights.cac import (
    get_cac_weights_from_whichindex,
)
from market_overview.services.scrapers.weights.ivv import get_spx_weights_from_ivv
from market_overview.services.scrapers.weights.nikkei import (
    get_nikkei_weights_from_official_csv,
)
from market_overview.services.scrapers.yahoo import (
    get_yahoo_finance_daily_returns_for_date_range,
)

logger = logging.getLogger(__name__)

# Usage of dict: equity index -> weight scraper returning ticker->weight percent.
WEIGHT_SCRAP_MAP = {
    EquityIndexChoices.SPX: get_spx_weights_from_ivv,
    EquityIndexChoices.CAC40: get_cac_weights_from_whichindex,
    EquityIndexChoices.NIKKEI225: get_nikkei_weights_from_official_csv,
}

_TOP_MOVER_COUNT = 3


def get_lock_key_for_sector_analysis_ingestion(
    start_date: date,
    end_date: date | None = None,
) -> str:
    """Return the Redis lock key for sector-analysis ingestion over a date window."""
    window_end = end_date or start_date
    return (
        "lock:sector_analysis_ingestion:"
        f"{start_date.isoformat()}:{window_end.isoformat()}"
    )


class SingleNameCatalogEntry(TypedDict):
    """One catalog entry from the single-name sector-analysis catalog."""

    company: str
    ticker: str
    sector: str
    subsector: str
    equity_index: EquityIndexChoices


def list_single_name_catalog_entries(
    equity_index: EquityIndexChoices | None = None,
) -> list[SingleNameCatalogEntry]:
    """Load single-name catalog entries, optionally filtered to one equity index."""
    with open(SINGLE_NAMES_JSON) as catalog_file:
        raw_catalog = json.load(catalog_file)
    catalog_entries = [
        SingleNameCatalogEntry(
            company=catalog_entry["company"],
            ticker=catalog_entry["ticker"],
            sector=catalog_entry["sector"],
            subsector=catalog_entry["subsector"],
            equity_index=EquityIndexChoices(catalog_entry["equity_index"]),
        )
        for catalog_entry in raw_catalog
    ]
    if equity_index is None:
        return catalog_entries
    return [
        catalog_entry
        for catalog_entry in catalog_entries
        if catalog_entry["equity_index"] == equity_index
    ]


class SubsectorTopMover(TypedDict):
    """One company among the top contributors inside a subsector day."""

    company: str
    ticker: str
    weight: float
    daily_return: float
    contribution: float


class _SingleNameDayInput(NamedTuple):
    """One name's weight and day return used when building a subsector bucket."""

    company: str
    ticker: str
    sector: str
    subsector: str
    weight: float
    daily_return: float


class _SingleNameDayJoinResult(NamedTuple):
    """Joined day inputs plus tickers that had no weight or no day return."""

    day_inputs: list[_SingleNameDayInput]
    names_missing_weight: list[str]
    names_missing_return: list[str]


class _SubsectorDayAggregate(NamedTuple):
    """Aggregated weight, return, contribution, and top names for one subsector."""

    sector: str
    subsector: str
    weight: float
    daily_return: float
    contribution: float
    top_movers: list[SubsectorTopMover]


class SectorAnalysisIngestionResult(TypedDict):
    """Summary of one scheduled or manual sector-analysis ingestion run."""

    date: str
    equity_index: EquityIndexChoices
    subsectors_upserted: int
    names_missing_weight: list[str]
    names_missing_return: list[str]


def _list_single_name_day_inputs(
    catalog_entries: list[SingleNameCatalogEntry],
    weights_by_ticker: dict[str, float],
    daily_returns_by_ticker: dict[str, float],
) -> _SingleNameDayJoinResult:
    """Join catalog entries with weights and returns, and report missing tickers."""
    # Usage of dict: ticker keys in the weight and day-return maps passed in.
    day_inputs: list[_SingleNameDayInput] = []
    names_missing_weight: list[str] = []
    names_missing_return: list[str] = []
    for catalog_entry in catalog_entries:
        ticker = catalog_entry["ticker"]
        weight = weights_by_ticker.get(ticker)
        if weight is None:
            names_missing_weight.append(ticker)
            continue
        daily_return = daily_returns_by_ticker.get(ticker)
        if daily_return is None:
            names_missing_return.append(ticker)
            continue
        day_inputs.append(
            _SingleNameDayInput(
                company=catalog_entry["company"],
                ticker=ticker,
                sector=catalog_entry["sector"],
                subsector=catalog_entry["subsector"],
                weight=weight,
                daily_return=daily_return,
            )
        )
    return _SingleNameDayJoinResult(
        day_inputs=day_inputs,
        names_missing_weight=names_missing_weight,
        names_missing_return=names_missing_return,
    )


def _list_top_movers_for_bucket(
    bucket_inputs: list[_SingleNameDayInput],
) -> list[SubsectorTopMover]:
    """Return up to three names with the largest absolute index contribution."""
    top_movers = [
        SubsectorTopMover(
            company=day_input.company,
            ticker=day_input.ticker,
            weight=day_input.weight,
            daily_return=day_input.daily_return,
            contribution=(day_input.weight / 100.0) * day_input.daily_return,
        )
        for day_input in bucket_inputs
    ]
    top_movers.sort(
        key=lambda top_mover: (-abs(top_mover["contribution"]), top_mover["company"]),
    )
    # Sorted by absolute contribution, so the first entries are the top movers.
    return top_movers[:_TOP_MOVER_COUNT]


def _aggregate_subsector_day_moves(
    day_inputs: list[_SingleNameDayInput],
) -> list[_SubsectorDayAggregate]:
    """
    Aggregate single-name day inputs into subsector weight, return, and
    contribution.
    """
    # Usage of dict: keys are (sector, subsector); values are name inputs in that bucket.
    # Usage of tuple: each key is the sector name and subsector name for that bucket.
    inputs_by_bucket: dict[tuple[str, str], list[_SingleNameDayInput]] = defaultdict(
        list
    )
    for day_input in day_inputs:
        inputs_by_bucket[(day_input.sector, day_input.subsector)].append(day_input)

    aggregates: list[_SubsectorDayAggregate] = []
    for (sector, subsector), bucket_inputs in sorted(inputs_by_bucket.items()):
        weight = sum(day_input.weight for day_input in bucket_inputs)
        if weight == 0:
            raise ValueError(
                f"Subsector {sector!r}/{subsector!r} has zero total weight."
            )
        weighted_return_sum = sum(
            day_input.weight * day_input.daily_return for day_input in bucket_inputs
        )
        daily_return = weighted_return_sum / weight
        contribution = sum(
            (day_input.weight / 100.0) * day_input.daily_return
            for day_input in bucket_inputs
        )
        aggregates.append(
            _SubsectorDayAggregate(
                sector=sector,
                subsector=subsector,
                weight=weight,
                daily_return=daily_return,
                contribution=contribution,
                top_movers=_list_top_movers_for_bucket(bucket_inputs),
            )
        )
    return aggregates


def _save_subsector_day_aggregates(
    equity_index: EquityIndexChoices,
    target_date: date,
    aggregates: list[_SubsectorDayAggregate],
) -> int:
    """Save subsector day moves for one equity index and date."""
    subsector_moves = [
        IndexSubsectorDailyMoveModel(
            date=target_date,
            equity_index=equity_index.value,
            sector=aggregate.sector,
            subsector=aggregate.subsector,
            weight=aggregate.weight,
            daily_return=aggregate.daily_return,
            contribution=aggregate.contribution,
            top_movers=aggregate.top_movers,
        )
        for aggregate in aggregates
    ]
    IndexSubsectorDailyMoveModel.objects.bulk_create(
        subsector_moves,
        update_conflicts=True,
        unique_fields=["equity_index", "date", "sector", "subsector"],
        update_fields=["weight", "daily_return", "contribution", "top_movers"],
    )
    return len(subsector_moves)


def _ingest_equity_index_subsector_daily_moves_from_inputs(
    equity_index: EquityIndexChoices,
    target_date: date,
    catalog_entries: list[SingleNameCatalogEntry],
    weights_by_ticker: dict[str, float],
    daily_returns_by_ticker: dict[str, float],
) -> SectorAnalysisIngestionResult | None:
    """
    Aggregate and save one equity-index day from already scraped weights and
    returns.
    """
    join_result = _list_single_name_day_inputs(
        catalog_entries,
        weights_by_ticker,
        daily_returns_by_ticker,
    )
    if not join_result.day_inputs:
        return None
    aggregates = _aggregate_subsector_day_moves(join_result.day_inputs)
    subsectors_saved = _save_subsector_day_aggregates(
        equity_index,
        target_date,
        aggregates,
    )
    return SectorAnalysisIngestionResult(
        date=target_date.isoformat(),
        equity_index=equity_index,
        subsectors_upserted=subsectors_saved,
        names_missing_weight=join_result.names_missing_weight,
        names_missing_return=join_result.names_missing_return,
    )


def ingest_equity_index_subsector_daily_moves(
    equity_index: EquityIndexChoices,
    target_date: date,
) -> SectorAnalysisIngestionResult:
    """Scrape weights and returns, aggregate subsectors, and save one equity index."""
    results = ingest_equity_index_subsector_daily_moves_for_date_range(
        equity_index,
        target_date,
        target_date,
    )
    if not results:
        raise ValueError(
            f"No usable single-name day inputs for {equity_index.value} "
            f"on {target_date.isoformat()}."
        )
    # A one-day window keeps at most one result for this equity index.
    return results[0]


def ingest_equity_index_subsector_daily_moves_for_date_range(
    equity_index: EquityIndexChoices,
    start_date: date,
    end_date: date,
) -> list[SectorAnalysisIngestionResult]:
    """
    Ingest subsector day moves for one equity index across a date window.

    Weights are scraped once for the whole window. Days with no usable Yahoo
    returns are skipped.
    """
    if end_date < start_date:
        raise ValueError(
            "end_date must be greater than or equal to start_date "
            f"(got {start_date.isoformat()} .. {end_date.isoformat()})."
        )
    catalog_entries = list_single_name_catalog_entries(equity_index)
    if not catalog_entries:
        raise ValueError(f"No single-name catalog entries for {equity_index.value}.")
    weight_scraper = WEIGHT_SCRAP_MAP[equity_index]
    weights_by_ticker = weight_scraper()
    tickers = [catalog_entry["ticker"] for catalog_entry in catalog_entries]
    returns_by_date = get_yahoo_finance_daily_returns_for_date_range(
        tickers,
        start_date,
        end_date,
    )
    results: list[SectorAnalysisIngestionResult] = []
    for trading_date in sorted(returns_by_date):
        result = _ingest_equity_index_subsector_daily_moves_from_inputs(
            equity_index,
            trading_date,
            catalog_entries,
            weights_by_ticker,
            returns_by_date[trading_date],
        )
        if result is not None:
            results.append(result)
    return results


def ingest_all_equity_index_subsector_daily_moves(
    target_date: date,
) -> list[SectorAnalysisIngestionResult]:
    """Ingest subsector day moves for every supported equity index on one date."""
    return ingest_all_equity_index_subsector_daily_moves_for_date_range(
        target_date,
        target_date,
    )


def ingest_all_equity_index_subsector_daily_moves_for_date_range(
    start_date: date,
    end_date: date,
) -> list[SectorAnalysisIngestionResult]:
    """Ingest subsector day moves for every supported equity index in a window."""
    results: list[SectorAnalysisIngestionResult] = []
    for equity_index in EquityIndexChoices:
        logger.info(
            "Ingesting sector analysis for %s from %s to %s.",
            equity_index.value,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        results.extend(
            ingest_equity_index_subsector_daily_moves_for_date_range(
                equity_index,
                start_date,
                end_date,
            )
        )
    return results


def get_latest_sector_analysis_date(
    location: LocationChoices,
) -> date | None:
    """Return the latest stored subsector move date for this location's equity index."""
    equity_index = EQUITY_INDEX_BY_LOCATION.get(location)
    if equity_index is None:
        raise ValueError(f"No equity index mapped for location {location.value}.")
    latest_move_date = (
        IndexSubsectorDailyMoveModel.objects.filter(equity_index=equity_index.value)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    return latest_move_date


class SubsectorDailyMove(TypedDict):
    """One stored subsector day move returned by the lookup helpers."""

    date: str
    equity_index: EquityIndexChoices
    sector: str
    subsector: str
    weight: float
    daily_return: float
    contribution: float
    top_movers: list[SubsectorTopMover]


class SubsectorDailyMovesForLocation(TypedDict):
    """Stored subsector day moves for one location on one trading day."""

    location: LocationChoices
    date: str
    equity_index: EquityIndexChoices
    subsectors: list[SubsectorDailyMove]


def _list_validated_subsector_top_movers(
    subsector_move: IndexSubsectorDailyMoveModel,
) -> list[SubsectorTopMover]:
    """Validate the stored 'top_movers' JSON on one subsector move."""
    raw_top_movers = subsector_move.top_movers
    if raw_top_movers is None:
        raise ValueError(
            "Stored top movers are missing for "
            f"{subsector_move.equity_index} "
            f"{subsector_move.sector}/{subsector_move.subsector} "
            f"on {subsector_move.date.isoformat()}."
        )
    validated_top_movers = TypeAdapter(list[SubsectorTopMover]).validate_python(
        raw_top_movers
    )
    return [
        SubsectorTopMover(
            company=top_mover["company"],
            ticker=top_mover["ticker"],
            weight=top_mover["weight"],
            daily_return=top_mover["daily_return"],
            contribution=top_mover["contribution"],
        )
        for top_mover in validated_top_movers
    ]


def _get_subsector_daily_move(
    subsector_move: IndexSubsectorDailyMoveModel,
) -> SubsectorDailyMove:
    """Map one stored subsector move into the lookup payload."""
    return SubsectorDailyMove(
        date=subsector_move.date.isoformat(),
        equity_index=EquityIndexChoices(subsector_move.equity_index),
        sector=subsector_move.sector,
        subsector=subsector_move.subsector,
        weight=subsector_move.weight,
        daily_return=subsector_move.daily_return,
        contribution=subsector_move.contribution,
        top_movers=_list_validated_subsector_top_movers(subsector_move),
    )


def _list_stored_subsector_daily_moves(
    equity_index: EquityIndexChoices,
    start_date: date,
    end_date: date,
) -> list[SubsectorDailyMove]:
    """Map stored subsector moves for one equity index across an inclusive date window."""
    subsector_moves = IndexSubsectorDailyMoveModel.objects.filter(
        equity_index=equity_index.value,
        date__gte=start_date,
        date__lte=end_date,
    ).order_by("date", "sector", "subsector")
    return [
        _get_subsector_daily_move(subsector_move) for subsector_move in subsector_moves
    ]


def list_subsector_daily_moves_for_equity_index_on_date(
    equity_index: EquityIndexChoices,
    target_date: date,
) -> list[SubsectorDailyMove]:
    """Return stored subsector day moves for one equity index on one date."""
    return _list_stored_subsector_daily_moves(equity_index, target_date, target_date)


def list_subsector_daily_moves_for_equity_index_in_date_range(
    equity_index: EquityIndexChoices,
    start_date: date,
    end_date: date,
) -> list[SubsectorDailyMove]:
    """
    Return stored subsector day moves for one equity index from start through end
    inclusive.
    """
    return _list_stored_subsector_daily_moves(equity_index, start_date, end_date)


def list_subsector_daily_moves_for_location_on_date(
    location: LocationChoices,
    target_date: date,
) -> SubsectorDailyMovesForLocation:
    """Return stored subsector day moves for one location's equity index on one date."""
    equity_index = EQUITY_INDEX_BY_LOCATION.get(location)
    if equity_index is None:
        raise ValueError(f"No equity index mapped for location {location.value}.")
    return SubsectorDailyMovesForLocation(
        location=location,
        date=target_date.isoformat(),
        equity_index=equity_index,
        subsectors=list_subsector_daily_moves_for_equity_index_on_date(
            equity_index,
            target_date,
        ),
    )
