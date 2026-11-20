"""Ingest or refresh the earnings watchlist (Yahoo updates, weights, optional roll)."""

import json
import logging
from datetime import date, datetime
from enum import Enum
from typing import NamedTuple, NotRequired, TypedDict

from django.db.models import Q
from pydantic import TypeAdapter

from core.services.calendar import get_market_watch_as_of_date
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel
from market_overview.services.cache import (
    get_cached_earnings_watchlist_companies,
    set_cached_earnings_watchlist_companies,
)
from market_overview.services.config import (
    EARNINGS_WATCHLIST_JSON,
    EQUITY_INDEX_BY_LOCATION,
    LOCATION_BY_EQUITY_INDEX,
)
from market_overview.services.scrapers.yahoo import (
    YahooEarningsInformation,
    YahooEarningsSnapshot,
    get_yahoo_finance_earnings_snapshot,
)
from market_overview.services.sector_analysis import WEIGHT_SCRAP_MAP

logger = logging.getLogger(__name__)

# Usage of tuple: ordered stems for current_/previous_ reported-result fields.
_REPORTED_FIELD_NAMES = (
    "reporting_period_end",
    "eps",
    "eps_expected",
    "revenue_expected",
    "revenue",
    "operating_income",
    "gross_profit",
    "ebitda",
)


def get_lock_key_for_earnings_watchlist_ingestion() -> str:
    """Return the Redis lock key for earnings watchlist ingest (update, weights, roll)."""
    return "lock:earnings_watchlist_ingestion"


def get_lock_key_for_earnings_watchlist_refresh() -> str:
    """Return the Redis lock key for earnings watchlist refresh (update and weights)."""
    return "lock:earnings_watchlist_refresh"


class EarningsWatchlistCatalogEntry(TypedDict):
    """One company in the static earnings watchlist catalog."""

    company: str
    ticker: str
    equity_index: EquityIndexChoices


def list_earnings_watchlist_catalog_entries(
    equity_index: EquityIndexChoices | None = None,
) -> list[EarningsWatchlistCatalogEntry]:
    """Load earnings watchlist catalog entries, optionally for one equity index."""
    with open(EARNINGS_WATCHLIST_JSON) as catalog_file:
        raw = json.load(catalog_file)
    entries = [
        EarningsWatchlistCatalogEntry(
            company=catalog_entry["company"],
            ticker=catalog_entry["ticker"],
            equity_index=EquityIndexChoices(catalog_entry["equity_index"]),
        )
        for catalog_entry in raw
    ]
    if equity_index is None:
        return entries
    return [entry for entry in entries if entry["equity_index"] == equity_index]


def list_earnings_watchlist_models_for_location(
    location: LocationChoices,
) -> list[EarningsWatchlistModel]:
    """Return stored earnings watchlists for one region, heaviest index weight first."""
    equity_index = EQUITY_INDEX_BY_LOCATION.get(location)
    if equity_index is None:
        raise ValueError(f"No equity index mapped for location {location.value}.")
    earnings_watchlists = list(
        EarningsWatchlistModel.objects.filter(equity_index=equity_index.value)
    )
    earnings_watchlists.sort(
        key=lambda earnings_watchlist: (
            earnings_watchlist.weight_pct is None,
            -(earnings_watchlist.weight_pct or 0.0),
            earnings_watchlist.company,
        )
    )
    return earnings_watchlists


def list_earnings_watchlist_models_for_announcement_window(
    start_utc: datetime,
    end_utc: datetime,
) -> list[EarningsWatchlistModel]:
    """Return earnings watchlists whose upcoming announcement falls in a window."""
    return list(
        EarningsWatchlistModel.objects.filter(
            Q(
                upcoming_announcement_datetime__gte=start_utc,
                upcoming_announcement_datetime__lte=end_utc,
            )
        )
    )


def get_location_for_earnings_watchlist(
    earnings_watchlist: EarningsWatchlistModel,
) -> LocationChoices:
    """Return the market location for one earnings watchlist's equity index."""
    equity_index = EquityIndexChoices(earnings_watchlist.equity_index)
    location = LOCATION_BY_EQUITY_INDEX.get(equity_index)
    if location is None:
        raise ValueError(
            f"No location mapped for equity index {earnings_watchlist.equity_index!r}."
        )
    return location


class EarningsUpcomingInformation(TypedDict):
    """Stored upcoming schedule for one watchlist company on the GET API."""

    announcement_datetime: str | None
    reporting_period_end: str | None
    eps_expected: float | None
    revenue_expected: float | None


class EarningsReportedInformation(TypedDict):
    """Stored reported results for one watchlist company on the GET API."""

    reporting_period_end: str | None
    eps: float | None
    eps_expected: float | None
    revenue_expected: float | None
    revenue: float | None
    operating_income: float | None
    gross_profit: float | None
    ebitda: float | None


class EarningsWatchlistCompany(TypedDict):
    """One stored earnings watchlist company for GET / domain lookup."""

    company: str
    ticker: str
    equity_index: EquityIndexChoices
    weight_pct: float | None
    upcoming: EarningsUpcomingInformation
    current: EarningsReportedInformation
    previous: EarningsReportedInformation


_EARNINGS_WATCHLIST_COMPANIES_ADAPTER: TypeAdapter[list[EarningsWatchlistCompany]] = (
    TypeAdapter(list[EarningsWatchlistCompany])
)


def _get_upcoming_information_payload_from_earnings_watchlist(
    earnings_watchlist: EarningsWatchlistModel,
) -> EarningsUpcomingInformation:
    """Build JSON-ready upcoming fields from one stored earnings watchlist."""
    announcement_datetime = earnings_watchlist.upcoming_announcement_datetime
    reporting_period_end = earnings_watchlist.upcoming_reporting_period_end
    return EarningsUpcomingInformation(
        announcement_datetime=(
            announcement_datetime.isoformat() if announcement_datetime else None
        ),
        reporting_period_end=(
            reporting_period_end.isoformat() if reporting_period_end else None
        ),
        eps_expected=earnings_watchlist.upcoming_eps_expected,
        revenue_expected=earnings_watchlist.upcoming_revenue_expected,
    )


def _get_reported_information_payload_from_earnings_watchlist(
    earnings_watchlist: EarningsWatchlistModel,
    prefix: str,
) -> EarningsReportedInformation:
    """Build JSON-ready 'current_*' or 'previous_*' fields from one earnings watchlist."""
    reporting_period_end = getattr(earnings_watchlist, f"{prefix}reporting_period_end")
    return EarningsReportedInformation(
        reporting_period_end=(
            reporting_period_end.isoformat() if reporting_period_end else None
        ),
        eps=getattr(earnings_watchlist, f"{prefix}eps"),
        eps_expected=getattr(earnings_watchlist, f"{prefix}eps_expected"),
        revenue_expected=getattr(earnings_watchlist, f"{prefix}revenue_expected"),
        revenue=getattr(earnings_watchlist, f"{prefix}revenue"),
        operating_income=getattr(earnings_watchlist, f"{prefix}operating_income"),
        gross_profit=getattr(earnings_watchlist, f"{prefix}gross_profit"),
        ebitda=getattr(earnings_watchlist, f"{prefix}ebitda"),
    )


def _get_company_from_earnings_watchlist(
    earnings_watchlist: EarningsWatchlistModel,
) -> EarningsWatchlistCompany:
    """Map one stored earnings watchlist to the GET company payload."""
    return EarningsWatchlistCompany(
        company=earnings_watchlist.company,
        ticker=earnings_watchlist.ticker,
        equity_index=EquityIndexChoices(earnings_watchlist.equity_index),
        weight_pct=earnings_watchlist.weight_pct,
        upcoming=_get_upcoming_information_payload_from_earnings_watchlist(
            earnings_watchlist
        ),
        current=_get_reported_information_payload_from_earnings_watchlist(
            earnings_watchlist, "current_"
        ),
        previous=_get_reported_information_payload_from_earnings_watchlist(
            earnings_watchlist, "previous_"
        ),
    )


def list_earnings_watchlist_companies_for_location(
    location: LocationChoices,
) -> list[EarningsWatchlistCompany]:
    """Return stored watchlist companies for one region (GET / domain lookup).

    Results are Redis-cached and versioned by earnings-watchlist table state.
    """
    cached = get_cached_earnings_watchlist_companies(
        location,
        _EARNINGS_WATCHLIST_COMPANIES_ADAPTER,
    )
    if cached is not None:
        return cached
    companies = [
        _get_company_from_earnings_watchlist(earnings_watchlist)
        for earnings_watchlist in list_earnings_watchlist_models_for_location(location)
    ]
    set_cached_earnings_watchlist_companies(location, companies)
    return companies


class EarningsIngestionResult(TypedDict):
    """Summary of one earnings watchlist ingest or refresh run for one index."""

    equity_index: EquityIndexChoices
    companies_updated: int
    tickers_failed: list[str]
    as_of: NotRequired[str]


class EarningsWatchlistRunResult(TypedDict):
    """Earnings update and weight outcomes from one ingest or refresh run."""

    as_of: str
    earnings_results: list[EarningsIngestionResult]
    weight_results: list[EarningsIngestionResult]
    tickers_failed: list[str]


_EarningsWatchlistFieldValue = datetime | date | float | str | None


class _EarningsUpcomingFieldUpdates(TypedDict):
    """ORM values for the upcoming earnings schedule on one watchlist company."""

    upcoming_announcement_datetime: datetime | None
    upcoming_reporting_period_end: date | None
    upcoming_eps_expected: float | None
    upcoming_revenue_expected: float | None


class _UpcomingCurrentAndPreviousForIngest(NamedTuple):
    """Upcoming, current, and previous earnings information written on ingest."""

    upcoming: YahooEarningsInformation | None
    current: YahooEarningsInformation | None
    previous: YahooEarningsInformation | None


def _get_upcoming_field_updates(
    information: YahooEarningsInformation | None,
) -> _EarningsUpcomingFieldUpdates:
    """Build ORM updates for the 'upcoming_*' schedule fields."""
    if information is None:
        return _EarningsUpcomingFieldUpdates(
            upcoming_announcement_datetime=None,
            upcoming_reporting_period_end=None,
            upcoming_eps_expected=None,
            upcoming_revenue_expected=None,
        )
    return _EarningsUpcomingFieldUpdates(
        upcoming_announcement_datetime=information.announcement_datetime,
        upcoming_reporting_period_end=information.reporting_period_end,
        upcoming_eps_expected=information.eps_expected,
        upcoming_revenue_expected=information.revenue_expected,
    )


def _get_reported_field_updates(
    prefix: str,
    information: YahooEarningsInformation | None,
) -> dict[str, _EarningsWatchlistFieldValue]:
    """Build ORM updates for 'current_*' or 'previous_*' reported fields."""
    # Usage of dict: keys are EarningsWatchlistModel field names.
    if information is None:
        return {f"{prefix}{field_name}": None for field_name in _REPORTED_FIELD_NAMES}
    return {
        f"{prefix}reporting_period_end": information.reporting_period_end,
        f"{prefix}eps": information.eps_actual,
        f"{prefix}eps_expected": information.eps_expected,
        f"{prefix}revenue_expected": information.revenue_expected,
        f"{prefix}revenue": information.revenue,
        f"{prefix}operating_income": information.operating_income,
        f"{prefix}gross_profit": information.gross_profit,
        f"{prefix}ebitda": information.ebitda,
    }


def _get_reported_information_from_earnings_watchlist(
    earnings_watchlist: EarningsWatchlistModel,
    prefix: str,
) -> YahooEarningsInformation | None:
    """Rebuild reported Yahoo information from 'current_*' or 'previous_*' fields."""
    reporting_period_end = getattr(earnings_watchlist, f"{prefix}reporting_period_end")
    eps_actual = getattr(earnings_watchlist, f"{prefix}eps")
    eps_expected = getattr(earnings_watchlist, f"{prefix}eps_expected")
    revenue_expected = getattr(earnings_watchlist, f"{prefix}revenue_expected")
    revenue = getattr(earnings_watchlist, f"{prefix}revenue")
    operating_income = getattr(earnings_watchlist, f"{prefix}operating_income")
    gross_profit = getattr(earnings_watchlist, f"{prefix}gross_profit")
    ebitda = getattr(earnings_watchlist, f"{prefix}ebitda")
    if (
        reporting_period_end is None
        and eps_actual is None
        and eps_expected is None
        and revenue_expected is None
        and revenue is None
        and operating_income is None
        and gross_profit is None
        and ebitda is None
    ):
        return None
    return YahooEarningsInformation(
        announcement_datetime=None,
        reporting_period_end=reporting_period_end,
        is_reported=True,
        eps_actual=eps_actual,
        eps_expected=eps_expected,
        revenue_expected=revenue_expected,
        revenue=revenue,
        operating_income=operating_income,
        gross_profit=gross_profit,
        ebitda=ebitda,
    )


def _get_upcoming_information_from_earnings_watchlist(
    earnings_watchlist: EarningsWatchlistModel,
) -> YahooEarningsInformation | None:
    """Rebuild upcoming Yahoo-shaped information from the 'upcoming_*' fields."""
    announcement_datetime = earnings_watchlist.upcoming_announcement_datetime
    reporting_period_end = earnings_watchlist.upcoming_reporting_period_end
    eps_expected = earnings_watchlist.upcoming_eps_expected
    revenue_expected = earnings_watchlist.upcoming_revenue_expected
    if (
        announcement_datetime is None
        and reporting_period_end is None
        and eps_expected is None
        and revenue_expected is None
    ):
        return None
    return YahooEarningsInformation(
        announcement_datetime=announcement_datetime,
        reporting_period_end=reporting_period_end,
        is_reported=False,
        eps_actual=None,
        eps_expected=eps_expected,
        revenue_expected=revenue_expected,
        revenue=None,
        operating_income=None,
        gross_profit=None,
        ebitda=None,
    )


def _get_reported_information_from_upcoming(
    upcoming: YahooEarningsInformation,
) -> YahooEarningsInformation:
    """Map a rolled upcoming schedule into the latest reported-results shape."""
    return YahooEarningsInformation(
        announcement_datetime=None,
        reporting_period_end=upcoming.reporting_period_end,
        is_reported=True,
        eps_actual=None,
        eps_expected=upcoming.eps_expected,
        revenue_expected=upcoming.revenue_expected,
        revenue=None,
        operating_income=None,
        gross_profit=None,
        ebitda=None,
    )


def _merge_reported_actuals(
    shell: YahooEarningsInformation,
    reported: YahooEarningsInformation | None,
) -> YahooEarningsInformation:
    """Fill a rolled latest release with Yahoo actuals when the period matches."""
    if reported is None:
        return shell
    if (
        shell.reporting_period_end is not None
        and reported.reporting_period_end is not None
        and shell.reporting_period_end != reported.reporting_period_end
    ):
        return shell
    return YahooEarningsInformation(
        announcement_datetime=None,
        reporting_period_end=(
            reported.reporting_period_end or shell.reporting_period_end
        ),
        is_reported=True,
        eps_actual=reported.eps_actual,
        eps_expected=(
            reported.eps_expected
            if reported.eps_expected is not None
            else shell.eps_expected
        ),
        revenue_expected=(
            reported.revenue_expected
            if reported.revenue_expected is not None
            else shell.revenue_expected
        ),
        revenue=reported.revenue,
        operating_income=reported.operating_income,
        gross_profit=reported.gross_profit,
        ebitda=reported.ebitda,
    )


def _should_roll_on_as_of(
    upcoming: YahooEarningsInformation | None,
    as_of: date,
) -> bool:
    """Return whether 'as_of' is the Market Watch T+1 morning for the upcoming call."""
    if upcoming is None or upcoming.announcement_datetime is None:
        return False
    return upcoming.announcement_datetime.date() == as_of


def _get_upcoming_current_and_previous_for_ingest(
    existing_earnings_watchlist: EarningsWatchlistModel | None,
    *,
    snapshot: YahooEarningsSnapshot,
    as_of: date,
) -> _UpcomingCurrentAndPreviousForIngest:
    """Choose upcoming, current, and previous information, including the T+1 roll."""
    yahoo_upcoming = snapshot.upcoming
    yahoo_current = snapshot.current
    yahoo_previous = snapshot.previous
    if existing_earnings_watchlist is None:
        return _UpcomingCurrentAndPreviousForIngest(
            upcoming=yahoo_upcoming,
            current=yahoo_current,
            previous=yahoo_previous,
        )

    stored_upcoming = _get_upcoming_information_from_earnings_watchlist(
        existing_earnings_watchlist
    )
    stored_current = _get_reported_information_from_earnings_watchlist(
        existing_earnings_watchlist, "current_"
    )
    stored_previous = _get_reported_information_from_earnings_watchlist(
        existing_earnings_watchlist, "previous_"
    )

    if _should_roll_on_as_of(stored_upcoming, as_of) and stored_upcoming is not None:
        rolled_current = _merge_reported_actuals(
            _get_reported_information_from_upcoming(stored_upcoming),
            yahoo_current,
        )
        return _UpcomingCurrentAndPreviousForIngest(
            upcoming=yahoo_upcoming,
            current=rolled_current,
            previous=stored_current,
        )

    # Everyday update refreshes the upcoming schedule and leaves reported results stored.
    refreshed_upcoming = (
        yahoo_upcoming if yahoo_upcoming is not None else stored_upcoming
    )
    return _UpcomingCurrentAndPreviousForIngest(
        upcoming=refreshed_upcoming,
        current=stored_current,
        previous=stored_previous,
    )


class _EarningsWatchlistUpdateMode(str, Enum):
    """Whether a Yahoo watchlist pass may apply the T+1 roll."""

    INGEST = "ingest"
    REFRESH = "refresh"


def _get_company_and_upcoming_field_defaults(
    catalog_entry: EarningsWatchlistCatalogEntry,
    upcoming: YahooEarningsInformation | None,
) -> dict[str, _EarningsWatchlistFieldValue]:
    """Build company / index / 'upcoming_*' defaults for one watchlist upsert."""
    # Usage of dict: keys are EarningsWatchlistModel field names.
    upcoming_updates = _get_upcoming_field_updates(upcoming)
    return {
        "company": catalog_entry["company"],
        "equity_index": catalog_entry["equity_index"],
        "upcoming_announcement_datetime": upcoming_updates[
            "upcoming_announcement_datetime"
        ],
        "upcoming_reporting_period_end": upcoming_updates[
            "upcoming_reporting_period_end"
        ],
        "upcoming_eps_expected": upcoming_updates["upcoming_eps_expected"],
        "upcoming_revenue_expected": upcoming_updates["upcoming_revenue_expected"],
    }


def _get_ingest_field_defaults(
    catalog_entry: EarningsWatchlistCatalogEntry,
    *,
    snapshot: YahooEarningsSnapshot,
    as_of: date,
    existing_earnings_watchlist: EarningsWatchlistModel | None,
) -> dict[str, _EarningsWatchlistFieldValue]:
    """Build ingest defaults, including reported results on first populate or T+1."""
    earnings_information = _get_upcoming_current_and_previous_for_ingest(
        existing_earnings_watchlist,
        snapshot=snapshot,
        as_of=as_of,
    )
    stored_upcoming = (
        _get_upcoming_information_from_earnings_watchlist(existing_earnings_watchlist)
        if existing_earnings_watchlist is not None
        else None
    )
    # Usage of dict: keys are EarningsWatchlistModel field names.
    defaults = _get_company_and_upcoming_field_defaults(
        catalog_entry,
        earnings_information.upcoming,
    )
    # First populate and the T+1 roll write reported results. Everyday updates do not.
    if existing_earnings_watchlist is None or _should_roll_on_as_of(
        stored_upcoming, as_of
    ):
        defaults.update(
            _get_reported_field_updates("current_", earnings_information.current)
        )
        defaults.update(
            _get_reported_field_updates("previous_", earnings_information.previous)
        )
    return defaults


def _upsert_earnings_watchlist_company_from_catalog_entry(
    catalog_entry: EarningsWatchlistCatalogEntry,
    *,
    snapshot: YahooEarningsSnapshot,
    as_of: date,
    update_mode: _EarningsWatchlistUpdateMode,
) -> None:
    """Create or update one watchlist company from Yahoo for ingest or refresh."""
    if update_mode is _EarningsWatchlistUpdateMode.REFRESH:
        defaults = _get_company_and_upcoming_field_defaults(
            catalog_entry,
            snapshot.upcoming,
        )
    else:
        existing_earnings_watchlist = EarningsWatchlistModel.objects.filter(
            ticker=catalog_entry["ticker"]
        ).first()
        defaults = _get_ingest_field_defaults(
            catalog_entry,
            snapshot=snapshot,
            as_of=as_of,
            existing_earnings_watchlist=existing_earnings_watchlist,
        )
    EarningsWatchlistModel.objects.update_or_create(
        ticker=catalog_entry["ticker"],
        defaults=defaults,
    )


def _update_one_earnings_watchlist_catalog_entry(
    catalog_entry: EarningsWatchlistCatalogEntry,
    as_of: date,
    update_mode: _EarningsWatchlistUpdateMode,
) -> None:
    """Scrape Yahoo and upsert one company for the chosen update mode."""
    snapshot = get_yahoo_finance_earnings_snapshot(catalog_entry["ticker"])
    _upsert_earnings_watchlist_company_from_catalog_entry(
        catalog_entry,
        snapshot=snapshot,
        as_of=as_of,
        update_mode=update_mode,
    )


def _get_empty_earnings_ingestion_result(
    equity_index: EquityIndexChoices,
    as_of: date,
) -> EarningsIngestionResult:
    """Return a zeroed per-index tally for an earnings update pass."""
    return EarningsIngestionResult(
        equity_index=equity_index,
        companies_updated=0,
        tickers_failed=[],
        as_of=as_of.isoformat(),
    )


def _update_earnings_watchlist_companies_from_yahoo(
    as_of: date,
    equity_index: EquityIndexChoices | None,
    update_mode: _EarningsWatchlistUpdateMode,
) -> list[EarningsIngestionResult]:
    """Scrape Yahoo and upsert catalog companies for ingest or refresh."""
    catalog_entries = list_earnings_watchlist_catalog_entries(equity_index)
    # Usage of dict: keys are equity indexes; values are running update tallies.
    results_by_index: dict[EquityIndexChoices, EarningsIngestionResult] = {}
    for catalog_entry in catalog_entries:
        catalog_equity_index = catalog_entry["equity_index"]
        if catalog_equity_index not in results_by_index:
            results_by_index[catalog_equity_index] = (
                _get_empty_earnings_ingestion_result(
                    catalog_equity_index,
                    as_of,
                )
            )
        try:
            _update_one_earnings_watchlist_catalog_entry(
                catalog_entry,
                as_of,
                update_mode,
            )
            results_by_index[catalog_equity_index]["companies_updated"] += 1
        except Exception:
            logger.exception(
                "Failed to update earnings for ticker %s",
                catalog_entry["ticker"],
            )
            results_by_index[catalog_equity_index]["tickers_failed"].append(
                catalog_entry["ticker"]
            )
    return list(results_by_index.values())


def _ensure_watchlist_companies_exist_for_catalog(
    catalog_entries: list[EarningsWatchlistCatalogEntry],
) -> None:
    """Create empty watchlist companies for catalog tickers that are not stored yet."""
    existing_tickers = set(
        EarningsWatchlistModel.objects.filter(
            ticker__in=[entry["ticker"] for entry in catalog_entries]
        ).values_list("ticker", flat=True)
    )
    missing_earnings_watchlists = [
        EarningsWatchlistModel(
            company=entry["company"],
            ticker=entry["ticker"],
            equity_index=entry["equity_index"],
        )
        for entry in catalog_entries
        if entry["ticker"] not in existing_tickers
    ]
    if missing_earnings_watchlists:
        EarningsWatchlistModel.objects.bulk_create(missing_earnings_watchlists)


def _refresh_earnings_watchlist_weights(
    as_of: date,
    equity_index: EquityIndexChoices | None = None,
) -> list[EarningsIngestionResult]:
    """Refresh latest index weights on watchlist companies from weight scrapers."""
    indexes = [equity_index] if equity_index is not None else list(EquityIndexChoices)
    results: list[EarningsIngestionResult] = []
    for index in indexes:
        catalog_entries = list_earnings_watchlist_catalog_entries(index)
        _ensure_watchlist_companies_exist_for_catalog(catalog_entries)
        weight_by_ticker = WEIGHT_SCRAP_MAP[index]()
        companies_updated = 0
        tickers_failed: list[str] = []
        for catalog_entry in catalog_entries:
            ticker = catalog_entry["ticker"]
            weight_pct = weight_by_ticker.get(ticker)
            if weight_pct is None:
                tickers_failed.append(ticker)
                continue
            updated = EarningsWatchlistModel.objects.filter(ticker=ticker).update(
                company=catalog_entry["company"],
                equity_index=catalog_entry["equity_index"],
                weight_pct=float(weight_pct),
            )
            if updated:
                companies_updated += 1
        results.append(
            EarningsIngestionResult(
                equity_index=index,
                companies_updated=companies_updated,
                tickers_failed=tickers_failed,
                as_of=as_of.isoformat(),
            )
        )
    return results


def _list_failed_tickers_from_earnings_results(
    results: list[EarningsIngestionResult],
) -> list[str]:
    """Flatten failed tickers from earnings ingest or refresh results."""
    return [ticker for result in results for ticker in result["tickers_failed"]]


def _get_earnings_watchlist_run_result(
    as_of: date,
    earnings_results: list[EarningsIngestionResult],
    weight_results: list[EarningsIngestionResult],
) -> EarningsWatchlistRunResult:
    """Build the shared ingest / refresh return payload."""
    return EarningsWatchlistRunResult(
        as_of=as_of.isoformat(),
        earnings_results=earnings_results,
        weight_results=weight_results,
        tickers_failed=_list_failed_tickers_from_earnings_results(
            earnings_results + weight_results
        ),
    )


def _run_earnings_watchlist_update(
    as_of: date | None,
    equity_index: EquityIndexChoices | None,
    update_mode: _EarningsWatchlistUpdateMode,
) -> EarningsWatchlistRunResult:
    """Run a Yahoo earnings pass and a weight refresh for one update mode."""
    effective_as_of = as_of or get_market_watch_as_of_date()
    return _get_earnings_watchlist_run_result(
        effective_as_of,
        _update_earnings_watchlist_companies_from_yahoo(
            effective_as_of,
            equity_index,
            update_mode,
        ),
        _refresh_earnings_watchlist_weights(effective_as_of, equity_index),
    )


def refresh_earnings_watchlist(
    as_of: date | None = None,
    equity_index: EquityIndexChoices | None = None,
) -> EarningsWatchlistRunResult:
    """Update upcoming estimates and index weights, leaving reported results stored."""
    return _run_earnings_watchlist_update(
        as_of,
        equity_index,
        _EarningsWatchlistUpdateMode.REFRESH,
    )


def ingest_earnings_watchlist(
    as_of: date | None = None,
    equity_index: EquityIndexChoices | None = None,
) -> EarningsWatchlistRunResult:
    """Update earnings with the T+1 roll, then refresh index weights.

    The first populate and T+1 mornings write 'current_*' and 'previous_*'.
    Other days only refresh 'upcoming_*' before weights are updated.
    """
    return _run_earnings_watchlist_update(
        as_of,
        equity_index,
        _EarningsWatchlistUpdateMode.INGEST,
    )
