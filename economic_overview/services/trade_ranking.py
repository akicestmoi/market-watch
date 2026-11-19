"""Ingest customs trade rankings for US / FR / JP."""

import logging
from datetime import date
from enum import Enum
from typing import NamedTuple, TypedDict

from django.db import transaction

from core.services.calendar import get_local_today
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeRankingModel,
    TradeTypeChoices,
)
from economic_overview.services.config import (
    TRADE_RANKING_LOCATIONS,
    TRADE_RANKING_PROFILE_BY_TYPE,
    TRADE_RANKING_REFRESH_YEARS,
    TradeRankingProfile,
)
from economic_overview.services.scrapers.census_trade import (
    get_trade_rankings_from_census,
    list_trade_partners_by_product_from_census,
)
from economic_overview.services.scrapers.common import (
    ScrapedTradeProductPartnerRanking,
    ScrapedTradeRanking,
    TradeProductCodesByPeriodFlow,
)
from economic_overview.services.scrapers.eurostat_comext import (
    get_trade_rankings_from_comext,
    list_trade_partners_by_product_from_comext,
)
from economic_overview.services.scrapers.jp_customs import (
    get_trade_rankings_from_jp_customs,
    list_trade_partners_by_product_from_jp_customs,
)

logger = logging.getLogger(__name__)

_TRADE_LABEL_MAX_LENGTH = 255

TRADE_SOURCE_BY_LOCATION: dict[
    EconomicDataLocationChoices, EconomicDataSourceChoices
] = {
    EconomicDataLocationChoices.FR: EconomicDataSourceChoices.EUROSTAT,
    EconomicDataLocationChoices.US: EconomicDataSourceChoices.CENSUS,
    EconomicDataLocationChoices.JP: EconomicDataSourceChoices.JP_CUSTOMS,
}


class TradeRankingIngestStatus(str, Enum):
    """Per-location outcome for one trade-ranking ingest run."""

    SUCCESS = "success"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    SKIPPED = "skipped"


class TradeRankingLocationResult(TypedDict):
    """Ingest result for one charts location and trade type."""

    location: str
    trade_type: str
    status: str
    upserted_count: int
    message: str


class TradeRankingIngestReport(TypedDict):
    """Summary returned by the trade ranking Celery task."""

    as_of: str
    status: str
    message: str
    results: list[TradeRankingLocationResult]


class _TradeRankingSetKey(NamedTuple):
    """Identity of one replaceable trade ranking set in storage."""

    period: date
    flow: str
    breakdown: str
    product_code_for_set: str


class _TradeRankingToUpsert(TypedDict):
    """One trade ranking ready to replace a stored ranking set."""

    period: date
    flow: str
    breakdown: str
    rank: int
    product_code: str
    product_label: str
    partner_code: str
    partner_label: str
    trade_value: float


def _format_trade_partner_label(partner_label: str) -> str:
    """Drop trailing notes such as '(incl. Hong Kong)' from partner names."""
    cleaned_label = partner_label.strip()
    if cleaned_label.endswith(")"):
        open_paren = cleaned_label.rfind(" (")
        if open_paren > 0:
            cleaned_label = cleaned_label[:open_paren].strip()
    return _truncate_trade_label(cleaned_label)


def _truncate_trade_label(label: str) -> str:
    """Keep trade labels within the model CharField max length."""
    if len(label) <= _TRADE_LABEL_MAX_LENGTH:
        return label
    return label[: _TRADE_LABEL_MAX_LENGTH - 1] + "…"


def _list_completed_calendar_years(history_years: int, *, as_of: date) -> list[int]:
    """Return the last 'history_years' completed calendar years before 'as_of'."""
    last_completed_year = as_of.year - 1
    return list(range(last_completed_year - history_years + 1, last_completed_year + 1))


def _list_years_to_scrape(
    history_years: int,
    *,
    as_of: date,
    full_history: bool,
) -> list[int]:
    """Choose full history years or only the recent revision window."""
    completed_years = _list_completed_calendar_years(history_years, as_of=as_of)
    if full_history:
        return completed_years
    return completed_years[-TRADE_RANKING_REFRESH_YEARS:]


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------


def _scrape_trade_rankings_for_location(
    location: EconomicDataLocationChoices,
    years: list[int],
    *,
    profile: TradeRankingProfile,
) -> list[ScrapedTradeRanking]:
    """Dispatch Top-N product/partner scrape to the location's customs source."""
    product_label_by_code = profile.product_label_by_code or None
    match location:
        case EconomicDataLocationChoices.FR:
            return get_trade_rankings_from_comext(
                years,
                top_n=profile.ingest_top_n,
                product_codes=profile.product_codes,
                product_label_by_code=product_label_by_code,
            )
        case EconomicDataLocationChoices.US:
            return get_trade_rankings_from_census(
                years,
                top_n=profile.ingest_top_n,
                product_codes=profile.product_codes,
                product_label_by_code=product_label_by_code,
            )
        case EconomicDataLocationChoices.JP:
            return get_trade_rankings_from_jp_customs(
                years,
                top_n=profile.ingest_top_n,
                product_codes=profile.product_codes,
                product_label_by_code=product_label_by_code,
            )
        case _:
            return []


def _scrape_trade_partners_by_product(
    location: EconomicDataLocationChoices,
    years: list[int],
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow],
    *,
    profile: TradeRankingProfile,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Scrape Top-N partners per product for the charts product filter."""
    if not trade_product_codes_by_period_flow:
        return []
    product_label_by_code = profile.product_label_by_code or None
    match location:
        case EconomicDataLocationChoices.FR:
            return list_trade_partners_by_product_from_comext(
                years,
                trade_product_codes_by_period_flow=trade_product_codes_by_period_flow,
                top_n=profile.ingest_top_n,
                product_label_by_code=product_label_by_code,
            )
        case EconomicDataLocationChoices.US:
            return list_trade_partners_by_product_from_census(
                years,
                trade_product_codes_by_period_flow=trade_product_codes_by_period_flow,
                top_n=profile.ingest_top_n,
                product_label_by_code=product_label_by_code,
            )
        case EconomicDataLocationChoices.JP:
            return list_trade_partners_by_product_from_jp_customs(
                years,
                trade_product_codes_by_period_flow=trade_product_codes_by_period_flow,
                top_n=profile.ingest_top_n,
                product_label_by_code=product_label_by_code,
            )
        case _:
            return []


# ---------------------------------------------------------------------------
# List (scrape → upsert rankings)
# ---------------------------------------------------------------------------


def _list_trade_rankings_from_product_partner_scrape(
    scraped_rankings: list[ScrapedTradeProductPartnerRanking],
) -> list[_TradeRankingToUpsert]:
    """Map product×partner scrapes onto the shared upsert ranking shape."""
    return [
        _TradeRankingToUpsert(
            period=scraped_ranking["period"],
            flow=scraped_ranking["flow"],
            breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            rank=scraped_ranking["rank"],
            product_code=scraped_ranking["product_code"],
            product_label=_truncate_trade_label(scraped_ranking["product_label"]),
            partner_code=scraped_ranking["partner_code"],
            partner_label=_format_trade_partner_label(scraped_ranking["partner_label"]),
            trade_value=scraped_ranking["trade_value"],
        )
        for scraped_ranking in scraped_rankings
    ]


def _list_trade_rankings_from_topn_scrape(
    scraped_rankings: list[ScrapedTradeRanking],
) -> list[_TradeRankingToUpsert]:
    """Map Top-N scrapes onto the shared upsert ranking shape."""
    trade_rankings: list[_TradeRankingToUpsert] = []
    for scraped_ranking in scraped_rankings:
        item_code = scraped_ranking["item_code"]
        if scraped_ranking["breakdown"] == TradeBreakdownChoices.PRODUCT.value:
            product_code, product_label, partner_code, partner_label = (
                item_code,
                _truncate_trade_label(scraped_ranking["item_label"]),
                "",
                "",
            )
        else:
            product_code, product_label, partner_code, partner_label = (
                "",
                "",
                item_code,
                _format_trade_partner_label(scraped_ranking["item_label"]),
            )
        trade_rankings.append(
            _TradeRankingToUpsert(
                period=scraped_ranking["period"],
                flow=scraped_ranking["flow"],
                breakdown=scraped_ranking["breakdown"],
                rank=scraped_ranking["rank"],
                product_code=product_code,
                product_label=product_label,
                partner_code=partner_code,
                partner_label=partner_label,
                trade_value=scraped_ranking["trade_value"],
            )
        )
    return trade_rankings


def _list_trade_product_codes_by_period_flow(
    scraped_rankings: list[ScrapedTradeRanking],
) -> list[TradeProductCodesByPeriodFlow]:
    """Collect Top-N product codes per year/flow for the partner-by-product scrape."""
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow] = []
    for scraped_ranking in scraped_rankings:
        if scraped_ranking["breakdown"] != TradeBreakdownChoices.PRODUCT.value:
            continue
        matching_entry = next(
            (
                entry
                for entry in trade_product_codes_by_period_flow
                if entry["period"] == scraped_ranking["period"]
                and entry["flow"] == scraped_ranking["flow"]
            ),
            None,
        )
        if matching_entry is None:
            trade_product_codes_by_period_flow.append(
                TradeProductCodesByPeriodFlow(
                    period=scraped_ranking["period"],
                    flow=scraped_ranking["flow"],
                    product_codes=[scraped_ranking["item_code"]],
                )
            )
        else:
            matching_entry["product_codes"].append(scraped_ranking["item_code"])
    return trade_product_codes_by_period_flow


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def _get_trade_ranking_set_key(
    trade_ranking: _TradeRankingToUpsert,
) -> _TradeRankingSetKey:
    """Group key for ranking-set replace: product×partner or Top-N per breakdown."""
    product_code_for_set = (
        trade_ranking["product_code"]
        if trade_ranking["breakdown"] == TradeBreakdownChoices.PRODUCT_PARTNER.value
        else ""
    )
    return _TradeRankingSetKey(
        period=trade_ranking["period"],
        flow=trade_ranking["flow"],
        breakdown=trade_ranking["breakdown"],
        product_code_for_set=product_code_for_set,
    )


def _replace_trade_ranking_set(
    location: EconomicDataLocationChoices,
    ranking_set: list[_TradeRankingToUpsert],
    *,
    trade_type: TradeTypeChoices,
    source: EconomicDataSourceChoices,
    period: date,
    flow: str,
    breakdown: str,
    product_code_for_set: str,
) -> int:
    """Delete one ranking set, then bulk-create the scraped rankings for it."""
    ranking_set_filter = TradeRankingModel.objects.filter(
        trade_type=trade_type.value,
        location=location.value,
        period=period,
        flow=flow,
        breakdown=breakdown,
    )
    if breakdown == TradeBreakdownChoices.PRODUCT_PARTNER.value:
        ranking_set_filter = ranking_set_filter.filter(
            product_code=product_code_for_set
        )
    with transaction.atomic():
        ranking_set_filter.delete()
        TradeRankingModel.objects.bulk_create(
            [
                TradeRankingModel(
                    trade_type=trade_type.value,
                    location=location.value,
                    period=period,
                    flow=flow,
                    breakdown=breakdown,
                    rank=trade_ranking["rank"],
                    product_code=trade_ranking["product_code"],
                    product_label=trade_ranking["product_label"],
                    partner_code=trade_ranking["partner_code"],
                    partner_label=trade_ranking["partner_label"],
                    trade_value=trade_ranking["trade_value"],
                    source=source.value,
                )
                for trade_ranking in ranking_set
            ]
        )
    return len(ranking_set)


def upsert_trade_rankings(
    location: EconomicDataLocationChoices,
    trade_rankings: list[_TradeRankingToUpsert],
    *,
    trade_type: TradeTypeChoices,
) -> int:
    """Replace stored rankings for each touched ranking set with the scraped list.

    Each scrape is a full Top-N (or full partner list for one product), so the
    ranking set is deleted first; otherwise dropped ranks would linger.
    """
    if not trade_rankings:
        return 0
    try:
        source = TRADE_SOURCE_BY_LOCATION[location]
    except KeyError as exc:
        raise ValueError(f"Unsupported trade ranking location: {location}") from exc
    # Usage of dict: group rankings by replace set (period, flow, breakdown[, product]).
    rankings_by_set: dict[_TradeRankingSetKey, list[_TradeRankingToUpsert]] = {}
    for trade_ranking in trade_rankings:
        rankings_by_set.setdefault(
            _get_trade_ranking_set_key(trade_ranking), []
        ).append(trade_ranking)

    upserted_count = 0
    for ranking_set_key, ranking_set in rankings_by_set.items():
        upserted_count += _replace_trade_ranking_set(
            location,
            ranking_set,
            trade_type=trade_type,
            source=source,
            period=ranking_set_key.period,
            flow=ranking_set_key.flow,
            breakdown=ranking_set_key.breakdown,
            product_code_for_set=ranking_set_key.product_code_for_set,
        )
    return upserted_count


def _replace_trade_ranking_product_partner_sets(
    location: EconomicDataLocationChoices,
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow],
    trade_rankings: list[_TradeRankingToUpsert],
    *,
    trade_type: TradeTypeChoices,
) -> int:
    """Replace every expected product×partner set; empty scrape clears the set."""
    if not trade_product_codes_by_period_flow:
        return 0
    try:
        source = TRADE_SOURCE_BY_LOCATION[location]
    except KeyError as exc:
        raise ValueError(f"Unsupported trade ranking location: {location}") from exc
    # Usage of dict: group rankings by replace set (period, flow, breakdown, product).
    rankings_by_set: dict[_TradeRankingSetKey, list[_TradeRankingToUpsert]] = {}
    for trade_ranking in trade_rankings:
        rankings_by_set.setdefault(
            _get_trade_ranking_set_key(trade_ranking), []
        ).append(trade_ranking)

    upserted_count = 0
    for trade_product_codes in trade_product_codes_by_period_flow:
        for product_code in trade_product_codes["product_codes"]:
            ranking_set_key = _TradeRankingSetKey(
                period=trade_product_codes["period"],
                flow=trade_product_codes["flow"],
                breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
                product_code_for_set=product_code,
            )
            upserted_count += _replace_trade_ranking_set(
                location,
                rankings_by_set.get(ranking_set_key, []),
                trade_type=trade_type,
                source=source,
                period=trade_product_codes["period"],
                flow=trade_product_codes["flow"],
                breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
                product_code_for_set=product_code,
            )
    return upserted_count


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def _build_trade_ranking_ingest_report(
    *,
    as_of: date,
    results: list[TradeRankingLocationResult],
    subject: str,
) -> TradeRankingIngestReport:
    """Assemble a multi-location trade ranking ingest report."""
    failed = [
        result["location"]
        for result in results
        if result["status"] == TradeRankingIngestStatus.FAILED.value
    ]
    succeeded = [
        result["location"]
        for result in results
        if result["status"] == TradeRankingIngestStatus.SUCCESS.value
    ]
    message = f"{subject}: {len(succeeded)} location(s) updated, {len(failed)} failed."
    logger.info(message)
    return TradeRankingIngestReport(
        as_of=as_of.isoformat(),
        status=(
            TradeRankingIngestStatus.FAILED.value
            if failed
            else TradeRankingIngestStatus.SUCCESS.value
        ),
        message=message,
        results=results,
    )


def _upsert_scraped_trade_rankings_for_location(
    location: EconomicDataLocationChoices,
    years: list[int],
    *,
    trade_type: TradeTypeChoices,
    profile: TradeRankingProfile,
) -> int:
    """Scrape Top-N and product×partner cells, then upsert both for one location."""
    scraped_rankings = _scrape_trade_rankings_for_location(
        location, years, profile=profile
    )
    upserted_count = upsert_trade_rankings(
        location,
        _list_trade_rankings_from_topn_scrape(scraped_rankings),
        trade_type=trade_type,
    )
    trade_product_codes_by_period_flow = _list_trade_product_codes_by_period_flow(
        scraped_rankings
    )
    partner_by_product_rankings = _scrape_trade_partners_by_product(
        location,
        years,
        trade_product_codes_by_period_flow,
        profile=profile,
    )
    upserted_count += _replace_trade_ranking_product_partner_sets(
        location,
        trade_product_codes_by_period_flow,
        _list_trade_rankings_from_product_partner_scrape(partner_by_product_rankings),
        trade_type=trade_type,
    )
    return upserted_count


def _get_trade_ranking_location_result(
    location: EconomicDataLocationChoices,
    *,
    trade_type: TradeTypeChoices,
    upserted_count: int,
) -> TradeRankingLocationResult:
    """Build the per-location ingest result from an upsert count."""
    if upserted_count == 0:
        return TradeRankingLocationResult(
            location=location.value,
            trade_type=trade_type.value,
            status=TradeRankingIngestStatus.UNCHANGED.value,
            upserted_count=0,
            message=f"No {trade_type.label} trade rankings scraped.",
        )
    return TradeRankingLocationResult(
        location=location.value,
        trade_type=trade_type.value,
        status=TradeRankingIngestStatus.SUCCESS.value,
        upserted_count=upserted_count,
        message=f"Upserted {upserted_count} {trade_type.label} trade ranking(s).",
    )


def ingest_trade_rankings_for_location(
    location: EconomicDataLocationChoices,
    *,
    trade_type: TradeTypeChoices,
    as_of: date | None = None,
    full_history: bool = False,
) -> TradeRankingLocationResult:
    """Scrape and upsert Top-N plus product×partner rankings for one location."""
    try:
        profile = TRADE_RANKING_PROFILE_BY_TYPE[trade_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported trade type: {trade_type}") from exc
    reference_date = as_of if as_of is not None else get_local_today()
    years = _list_years_to_scrape(
        profile.history_years,
        as_of=reference_date,
        full_history=full_history,
    )
    try:
        upserted_count = _upsert_scraped_trade_rankings_for_location(
            location, years, trade_type=trade_type, profile=profile
        )
        return _get_trade_ranking_location_result(
            location, trade_type=trade_type, upserted_count=upserted_count
        )
    except Exception as exc:
        logger.exception(
            "%s trade ingest failed for %s: %s",
            trade_type.value,
            location.value,
            exc,
        )
        return TradeRankingLocationResult(
            location=location.value,
            trade_type=trade_type.value,
            status=TradeRankingIngestStatus.FAILED.value,
            upserted_count=0,
            message=str(exc),
        )


def ingest_trade_rankings(
    *,
    trade_type: TradeTypeChoices | None = None,
    as_of: date | None = None,
    force: bool = False,
    full_history: bool = False,
) -> TradeRankingIngestReport:
    """Ingest US / FR / JP trade rankings for one or both trade types.

    Normally only runs on calendar day 1. Pass 'force=True' to run on any day.
    When 'trade_type' is omitted, both 'TradeTypeChoices' values are ingested.
    """
    reference_date = as_of if as_of is not None else get_local_today()
    if not force and reference_date.day != 1:
        message = (
            f"Skipped: {reference_date.isoformat()} is not the first calendar day "
            f"of the month."
        )
        logger.info(message)
        return TradeRankingIngestReport(
            as_of=reference_date.isoformat(),
            status=TradeRankingIngestStatus.SKIPPED.value,
            message=message,
            results=[],
        )

    trade_types = [trade_type] if trade_type is not None else list(TradeTypeChoices)
    results: list[TradeRankingLocationResult] = []
    for active_trade_type in trade_types:
        type_results = [
            ingest_trade_rankings_for_location(
                location,
                trade_type=active_trade_type,
                as_of=reference_date,
                full_history=full_history,
            )
            for location in TRADE_RANKING_LOCATIONS
        ]
        results.extend(type_results)

    subject = (
        f"{trade_types[0].label} trade ranking ingest"
        if len(trade_types) == 1
        else "Trade ranking ingest"
    )
    return _build_trade_ranking_ingest_report(
        as_of=reference_date,
        results=results,
        subject=subject,
    )
