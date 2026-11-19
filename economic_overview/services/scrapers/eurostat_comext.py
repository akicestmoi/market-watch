"""Scrape France trade rankings from Eurostat Comext."""

import logging
import re
from datetime import date
from typing import NamedTuple, TypedDict

import requests
from pydantic import TypeAdapter, ValidationError

from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeFlowChoices,
)
from economic_overview.services.config import (
    EUROSTAT_COMEXT_DATASET,
    EUROSTAT_COMEXT_EXCLUDED_PARTNER_CODES,
    EUROSTAT_COMEXT_FLOW_EXPORT,
    EUROSTAT_COMEXT_FLOW_IMPORT,
    EUROSTAT_COMEXT_STATISTICS_API_BASE_URL,
    EUROSTAT_COMEXT_TOTAL_PRODUCT,
    EUROSTAT_COMEXT_VALUE_INDICATOR,
    EUROSTAT_COMEXT_WORLD_PARTNER,
)
from economic_overview.services.scrapers.common import (
    ScrapedTradeProductPartnerRanking,
    ScrapedTradeRanking,
    TradeProductCodesByPeriodFlow,
)

logger = logging.getLogger(__name__)

_COMEXT_FLOW_CODE_BY_TRADE_FLOW: dict[TradeFlowChoices, str] = {
    TradeFlowChoices.IMPORT: EUROSTAT_COMEXT_FLOW_IMPORT,
    TradeFlowChoices.EXPORT: EUROSTAT_COMEXT_FLOW_EXPORT,
}

# HS 2-digit codes 01–99 (Comext omits a few empty chapters).
_HS2_PRODUCT_CODES: list[str] = [f"{code:02d}" for code in range(1, 100)]
_COMEXT_COUNTRY_PARTNER_CODE_RE = re.compile(r"^[A-Z]{2}$")


def _is_comext_country_partner(partner_code: str) -> bool:
    """Return True for ISO-2 partners; drop EU/EA/OECD-style aggregates."""
    if (
        not partner_code
        or partner_code in EUROSTAT_COMEXT_EXCLUDED_PARTNER_CODES
        or partner_code == EUROSTAT_COMEXT_WORLD_PARTNER
    ):
        return False
    return _COMEXT_COUNTRY_PARTNER_CODE_RE.fullmatch(partner_code) is not None


class _ComextJsonStatCategory(TypedDict, total=False):
    """JSON-stat category block for one Comext dimension."""

    # Usage of dict: keys are dynamic JSON-stat category codes; values are flat indexes.
    index: dict[str, int]
    # Usage of dict: keys are category codes; values are display labels.
    label: dict[str, str]


class _ComextJsonStatDimension(TypedDict, total=False):
    """JSON-stat dimension block."""

    label: str
    category: _ComextJsonStatCategory


class _ComextJsonStatPayload(TypedDict, total=False):
    """JSON-stat 2.0 payload from the Comext statistics API."""

    id: list[str]
    size: list[int]
    # Usage of dict: keys are JSON-stat flat indexes; values are numbers.
    value: dict[str, float | int | None]
    # Usage of dict: keys are dimension ids from the dataset.
    dimension: dict[str, _ComextJsonStatDimension]


_COMEXT_PAYLOAD_ADAPTER = TypeAdapter(_ComextJsonStatPayload)


class _ComextTradeObservation(TypedDict):
    """One decoded Comext value with product and partner codes."""

    product_code: str
    product_label: str
    partner_code: str
    partner_label: str
    trade_value: float


class _ComextDimensionIndexes(NamedTuple):
    """Flat-index positions for product and partner in a Comext JSON-stat cube."""

    product_dimension_index: int
    partner_dimension_index: int
    product_code_by_position: dict[int, str]
    partner_code_by_position: dict[int, str]
    product_labels: dict[str, str]
    partner_labels: dict[str, str]


def _get_comext_dataset_url() -> str:
    """Return the Comext statistics API URL for the configured dataset."""
    return f"{EUROSTAT_COMEXT_STATISTICS_API_BASE_URL}/{EUROSTAT_COMEXT_DATASET}"


def _fetch_comext_json(
    *,
    year: int,
    flow: TradeFlowChoices,
    products: list[str] | None,
    partners: list[str] | None,
) -> _ComextJsonStatPayload | None:
    """GET one Comext annual VALUE_IN_EUROS slice for France."""
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    request_params: list[tuple[str, str]] = [
        ("freq", "A"),
        ("reporter", "FR"),
        ("flow", _COMEXT_FLOW_CODE_BY_TRADE_FLOW[flow]),
        ("indicators", EUROSTAT_COMEXT_VALUE_INDICATOR),
        ("time_period", str(year)),
        ("lang", "en"),
    ]
    if products is not None:
        for product_code in products:
            request_params.append(("product", product_code))
    if partners is not None:
        for partner_code in partners:
            request_params.append(("partner", partner_code))
    response = requests.get(
        _get_comext_dataset_url(),
        params=request_params,
        timeout=120,
    )
    if response.status_code >= 400:
        logger.warning(
            "Comext HTTP %s for year=%s flow=%s: %s",
            response.status_code,
            year,
            flow.value,
            response.text[:200],
        )
        return None
    try:
        return _COMEXT_PAYLOAD_ADAPTER.validate_python(response.json())
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("Comext JSON validation failed for year=%s: %s", year, exc)
        return None


def _get_comext_dimension_indexes(
    payload: _ComextJsonStatPayload,
) -> _ComextDimensionIndexes | None:
    """Read product/partner dimension maps from one Comext JSON-stat payload."""
    dimension_ids = payload.get("id") or []
    sizes = payload.get("size") or []
    dimensions = payload.get("dimension") or {}
    if not dimension_ids or not sizes or len(dimension_ids) != len(sizes):
        return None

    product_dimension = dimensions.get("product", {})
    partner_dimension = dimensions.get("partner", {})
    product_category = product_dimension.get("category") or {}
    partner_category = partner_dimension.get("category") or {}
    product_index = product_category.get("index") or {}
    partner_index = partner_category.get("index") or {}
    product_labels = product_category.get("label") or {}
    partner_labels = partner_category.get("label") or {}
    try:
        product_dimension_index = dimension_ids.index("product")
        partner_dimension_index = dimension_ids.index("partner")
    except ValueError:
        return None
    return _ComextDimensionIndexes(
        product_dimension_index=product_dimension_index,
        partner_dimension_index=partner_dimension_index,
        product_code_by_position={
            position: code for code, position in product_index.items()
        },
        partner_code_by_position={
            position: code for code, position in partner_index.items()
        },
        product_labels=product_labels,
        partner_labels=partner_labels,
    )


def _decode_comext_observation_from_flat_index(
    flat_index: int,
    trade_value: float,
    *,
    sizes: list[int],
    dimension_indexes: _ComextDimensionIndexes,
) -> _ComextTradeObservation | None:
    """Decode one Comext JSON-stat flat index into a product/partner observation."""
    remaining = flat_index
    positions: list[int] = []
    for size in reversed(sizes):
        positions.append(remaining % size)
        remaining //= size
    positions.reverse()
    product_code = dimension_indexes.product_code_by_position.get(
        positions[dimension_indexes.product_dimension_index], ""
    )
    partner_code = dimension_indexes.partner_code_by_position.get(
        positions[dimension_indexes.partner_dimension_index], ""
    )
    if not product_code or not partner_code:
        return None
    return _ComextTradeObservation(
        product_code=product_code,
        product_label=dimension_indexes.product_labels.get(product_code, product_code),
        partner_code=partner_code,
        partner_label=dimension_indexes.partner_labels.get(partner_code, partner_code),
        trade_value=trade_value,
    )


def _list_comext_observations(
    payload: _ComextJsonStatPayload,
) -> list[_ComextTradeObservation]:
    """Decode JSON-stat flat values into product/partner observations."""
    sizes = payload.get("size") or []
    values = payload.get("value") or {}
    dimension_indexes = _get_comext_dimension_indexes(payload)
    if dimension_indexes is None:
        return []

    observations: list[_ComextTradeObservation] = []
    for flat_index_text, raw_value in values.items():
        if raw_value is None:
            continue
        try:
            flat_index = int(flat_index_text)
            trade_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if trade_value <= 0:
            continue
        observation = _decode_comext_observation_from_flat_index(
            flat_index,
            trade_value,
            sizes=sizes,
            dimension_indexes=dimension_indexes,
        )
        if observation is not None:
            observations.append(observation)
    return observations


def _list_top_trade_rankings(
    observations: list[_ComextTradeObservation],
    *,
    period: date,
    flow: TradeFlowChoices,
    breakdown: TradeBreakdownChoices,
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Collapse Comext cells to Top-N product or partner rankings."""
    # Usage of dict: keys are item codes; values are (label, summed trade value).
    totals_by_item_code: dict[str, tuple[str, float]] = {}
    for observation in observations:
        if breakdown == TradeBreakdownChoices.PRODUCT:
            if observation["partner_code"] != EUROSTAT_COMEXT_WORLD_PARTNER:
                continue
            item_code = observation["product_code"]
            item_label = observation["product_label"]
        else:
            if not _is_comext_country_partner(observation["partner_code"]):
                continue
            item_code = observation["partner_code"]
            item_label = observation["partner_label"]
        previous_label, previous_value = totals_by_item_code.get(
            item_code, (item_label, 0.0)
        )
        totals_by_item_code[item_code] = (
            previous_label or item_label,
            previous_value + observation["trade_value"],
        )

    ranked_items = sorted(
        totals_by_item_code.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )[:top_n]
    return [
        ScrapedTradeRanking(
            period=period,
            flow=flow.value,
            breakdown=breakdown.value,
            rank=rank,
            item_code=item_code,
            item_label=item_label,
            trade_value=trade_value,
        )
        for rank, (item_code, (item_label, trade_value)) in enumerate(
            ranked_items, start=1
        )
    ]


def _list_top_partners_for_product(
    observations: list[_ComextTradeObservation],
    *,
    period: date,
    flow: TradeFlowChoices,
    product_code: str,
    product_label: str,
    top_n: int,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Keep Top-N partners for one product from Comext observations."""
    ranked_partners = sorted(
        (
            observation
            for observation in observations
            if observation["product_code"] == product_code
            and _is_comext_country_partner(observation["partner_code"])
        ),
        key=lambda observation: observation["trade_value"],
        reverse=True,
    )[:top_n]
    return [
        ScrapedTradeProductPartnerRanking(
            period=period,
            flow=flow.value,
            product_code=product_code,
            product_label=product_label,
            partner_code=observation["partner_code"],
            partner_label=observation["partner_label"],
            rank=rank,
            trade_value=observation["trade_value"],
        )
        for rank, observation in enumerate(ranked_partners, start=1)
    ]


def _apply_comext_product_label_overrides(
    observations: list[_ComextTradeObservation],
    product_label_by_code: dict[str, str],
) -> list[_ComextTradeObservation]:
    """Replace product labels with config overrides when present."""
    if not product_label_by_code:
        return observations
    return [
        _ComextTradeObservation(
            product_code=observation["product_code"],
            product_label=product_label_by_code.get(
                observation["product_code"],
                observation["product_label"],
            ),
            partner_code=observation["partner_code"],
            partner_label=observation["partner_label"],
            trade_value=observation["trade_value"],
        )
        for observation in observations
    ]


def _list_comext_scraped_rankings_for_year_flow(
    *,
    year: int,
    flow: TradeFlowChoices,
    top_n: int,
    products_for_scrape: list[str],
    product_codes: list[str] | None,
    product_label_by_code: dict[str, str],
) -> list[ScrapedTradeRanking]:
    """Scrape product and partner Top-N for one Comext year and flow."""
    period = date(year, 1, 1)
    scraped_rankings: list[ScrapedTradeRanking] = []
    product_payload = _fetch_comext_json(
        year=year,
        flow=flow,
        products=products_for_scrape,
        partners=[EUROSTAT_COMEXT_WORLD_PARTNER],
    )
    if product_payload is not None:
        product_observations = _apply_comext_product_label_overrides(
            _list_comext_observations(product_payload),
            product_label_by_code,
        )
        scraped_rankings.extend(
            _list_top_trade_rankings(
                product_observations,
                period=period,
                flow=flow,
                breakdown=TradeBreakdownChoices.PRODUCT,
                top_n=top_n,
            )
        )
    if product_codes is None:
        partner_payload = _fetch_comext_json(
            year=year,
            flow=flow,
            products=[EUROSTAT_COMEXT_TOTAL_PRODUCT],
            partners=None,
        )
    else:
        partner_payload = _fetch_comext_json(
            year=year,
            flow=flow,
            products=product_codes,
            partners=None,
        )
    if partner_payload is not None:
        scraped_rankings.extend(
            _list_top_trade_rankings(
                _list_comext_observations(partner_payload),
                period=period,
                flow=flow,
                breakdown=TradeBreakdownChoices.PARTNER,
                top_n=top_n,
            )
        )
    return scraped_rankings


def get_trade_rankings_from_comext(
    years: list[int],
    *,
    top_n: int,
    product_codes: list[str] | None = None,
    product_label_by_code: dict[str, str] | None = None,
) -> list[ScrapedTradeRanking]:
    """Scrape France Top-N product and partner rankings from Comext.

    When 'product_codes' is set, product rankings use that universe vs WORLD and
    partner rankings sum country partners across those products.
    """
    scraped_rankings: list[ScrapedTradeRanking] = []
    label_by_code = product_label_by_code or {}
    products_for_scrape = (
        product_codes if product_codes is not None else _HS2_PRODUCT_CODES
    )
    for year in years:
        for flow in TradeFlowChoices:
            scraped_rankings.extend(
                _list_comext_scraped_rankings_for_year_flow(
                    year=year,
                    flow=flow,
                    top_n=top_n,
                    products_for_scrape=products_for_scrape,
                    product_codes=product_codes,
                    product_label_by_code=label_by_code,
                )
            )
    return scraped_rankings


def list_trade_partners_by_product_from_comext(
    years: list[int],
    *,
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow],
    top_n: int,
    product_label_by_code: dict[str, str] | None = None,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Scrape Top-N partners per product for the charts product filter."""
    scraped_rankings: list[ScrapedTradeProductPartnerRanking] = []
    label_by_code = product_label_by_code or {}
    for trade_product_codes in trade_product_codes_by_period_flow:
        if (
            trade_product_codes["period"].year not in years
            or not trade_product_codes["product_codes"]
        ):
            continue
        flow = TradeFlowChoices(trade_product_codes["flow"])
        payload = _fetch_comext_json(
            year=trade_product_codes["period"].year,
            flow=flow,
            products=trade_product_codes["product_codes"],
            partners=None,
        )
        if payload is None:
            continue
        observations = _list_comext_observations(payload)
        # Usage of dict: product code → display label from config or the first cell.
        resolved_label_by_product_code: dict[str, str] = dict(label_by_code)
        for observation in observations:
            resolved_label_by_product_code.setdefault(
                observation["product_code"], observation["product_label"]
            )
        for product_code in trade_product_codes["product_codes"]:
            scraped_rankings.extend(
                _list_top_partners_for_product(
                    observations,
                    period=trade_product_codes["period"],
                    flow=flow,
                    product_code=product_code,
                    product_label=resolved_label_by_product_code.get(
                        product_code, product_code
                    ),
                    top_n=top_n,
                )
            )
    return scraped_rankings
