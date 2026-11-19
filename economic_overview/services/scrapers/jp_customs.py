"""Scrape Japan trade rankings from Japan Customs / e-Stat."""

import logging
from datetime import date
from typing import NamedTuple, TypedDict

from economic_overview.models.trade_ranking import TradeBreakdownChoices
from economic_overview.services.config import (
    JP_CUSTOMS_PRINCIPAL_COMMODITY_TABLES,
    JP_CUSTOMS_PRODUCT_CLASS_LEVEL,
    JP_CUSTOMS_PRODUCT_CODE_ALIASES,
    JP_CUSTOMS_VALUE_SCALE,
    JP_CUSTOMS_VALUE_YEAR_CAT02,
)
from economic_overview.services.scrapers.common import (
    ScrapedTradeProductPartnerRanking,
    ScrapedTradeRanking,
    TradeProductCodesByPeriodFlow,
)
from economic_overview.services.scrapers.stat_of_jp import (
    EstatJsonObject,
    EstatJsonValue,
    fetch_estat_stats_data,
    list_estat_dict_entries,
)

logger = logging.getLogger(__name__)

# Aggregate partner / product codes excluded from Japan partner rankings.
_JP_CUSTOMS_EXCLUDED_PARTNER_CODES: frozenset[str] = frozenset(
    {
        "TOTAL",
        "世界",
        "合計",
        "ALL",
        "000",
        "999",
    }
)


class _JpCustomsTradeCell(TypedDict):
    """One Japan customs trade cell after source-local parsing."""

    period: date
    flow: str
    product_code: str
    product_label: str
    partner_code: str
    partner_label: str
    trade_value: float


class _JpClassMeta(TypedDict):
    """Label and hierarchy level for one e-Stat CLASS code."""

    label: str
    level: str


class _PeriodFlowKey(NamedTuple):
    """Period date and import/export flow for local grouping."""

    period: date
    flow: str


def _build_class_meta_by_code(
    class_objs: EstatJsonValue,
    class_id: str,
) -> dict[str, _JpClassMeta]:
    """Map CLASS '@code' → label/level for one CLASS_OBJ id."""
    meta_by_code: dict[str, _JpClassMeta] = {}
    for class_obj in list_estat_dict_entries(class_objs):
        if class_obj.get("@id") != class_id:
            continue
        for class_entry in list_estat_dict_entries(class_obj.get("CLASS")):
            code = str(class_entry.get("@code") or "").strip()
            if not code:
                continue
            meta_by_code[code] = _JpClassMeta(
                label=str(class_entry.get("@name") or "").strip() or code,
                level=str(class_entry.get("@level") or "").strip(),
            )
    return meta_by_code


def _list_cells_for_product_universe(
    trade_cells: list[_JpCustomsTradeCell],
    *,
    product_codes: list[str] | None,
    product_label_by_code: dict[str, str],
) -> list[_JpCustomsTradeCell]:
    """Keep cells for the unrestricted universe, or remap/filter to product codes."""
    if product_codes is None:
        return trade_cells

    allowed_codes = set(product_codes)
    remapped_cells: list[_JpCustomsTradeCell] = []
    for trade_cell in trade_cells:
        canonical_code = JP_CUSTOMS_PRODUCT_CODE_ALIASES.get(trade_cell["product_code"])
        if canonical_code is None or canonical_code not in allowed_codes:
            continue
        remapped_cells.append(
            _JpCustomsTradeCell(
                period=trade_cell["period"],
                flow=trade_cell["flow"],
                product_code=canonical_code,
                product_label=product_label_by_code.get(
                    canonical_code, trade_cell["product_label"]
                ),
                partner_code=trade_cell["partner_code"],
                partner_label=trade_cell["partner_label"],
                trade_value=trade_cell["trade_value"],
            )
        )
    return remapped_cells


def _list_top_trade_rankings_from_cells(
    trade_cells: list[_JpCustomsTradeCell],
    *,
    breakdown: TradeBreakdownChoices,
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Collapse product×partner cells into Top-N rankings."""
    # Usage of dict: keys are (period, flow, item_code); values are label + sum.
    totals_by_key: dict[tuple[date, str, str], tuple[str, float]] = {}
    for trade_cell in trade_cells:
        if breakdown == TradeBreakdownChoices.PRODUCT:
            item_code = trade_cell["product_code"]
            item_label = trade_cell["product_label"]
        else:
            if trade_cell["partner_code"] in _JP_CUSTOMS_EXCLUDED_PARTNER_CODES:
                continue
            item_code = trade_cell["partner_code"]
            item_label = trade_cell["partner_label"]
        if not item_code:
            continue
        key = (trade_cell["period"], trade_cell["flow"], item_code)
        previous_label, previous_value = totals_by_key.get(key, (item_label, 0.0))
        totals_by_key[key] = (
            previous_label or item_label,
            previous_value + trade_cell["trade_value"],
        )

    scraped_rankings: list[ScrapedTradeRanking] = []
    # Usage of dict: group totals by period/flow for per-year Top-N.
    items_by_period_flow: dict[_PeriodFlowKey, list[tuple[str, str, float]]] = {}
    for (period, flow, item_code), (item_label, trade_value) in totals_by_key.items():
        period_flow = _PeriodFlowKey(period=period, flow=flow)
        items_by_period_flow.setdefault(period_flow, []).append(
            (item_code, item_label, trade_value)
        )
    for period_flow, items in items_by_period_flow.items():
        ranked_items = sorted(items, key=lambda item: item[2], reverse=True)[:top_n]
        for rank, (item_code, item_label, trade_value) in enumerate(
            ranked_items, start=1
        ):
            scraped_rankings.append(
                ScrapedTradeRanking(
                    period=period_flow.period,
                    flow=period_flow.flow,
                    breakdown=breakdown.value,
                    rank=rank,
                    item_code=item_code,
                    item_label=item_label,
                    trade_value=trade_value,
                )
            )
    return scraped_rankings


def _get_product_codes_for_period_flow(
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow],
    *,
    period: date,
    flow: str,
) -> list[str] | None:
    """Return product codes for one period/flow, or None when absent."""
    for trade_product_codes in trade_product_codes_by_period_flow:
        if (
            trade_product_codes["period"] == period
            and trade_product_codes["flow"] == flow
        ):
            return trade_product_codes["product_codes"]
    return None


def _list_trade_cells_from_estat(
    years: list[int],
    *,
    product_codes: frozenset[str] | None = None,
) -> list[_JpCustomsTradeCell]:
    """Fetch Principal Commodity × Country annual Value-Year cells from e-Stat.

    Uses 概況品別国別表 bundles (export/import). When 'product_codes' is set, keep
    those 概況品 codes at any CLASS level (energy aliases). Otherwise keep CLASS
    level-2 commodities for merchandise Top-N. Values are scaled from thousand-yen
    units to yen.
    """
    if not years:
        return []
    trade_cells: list[_JpCustomsTradeCell] = []
    year_set = set(years)
    for stats_data_id, flow in JP_CUSTOMS_PRINCIPAL_COMMODITY_TABLES:
        for year in years:
            trade_cells.extend(
                _list_trade_cells_from_estat_table(
                    stats_data_id=stats_data_id,
                    flow=flow,
                    year=year,
                    year_set=year_set,
                    product_codes=product_codes,
                )
            )
    if not trade_cells:
        logger.warning(
            "Japan Customs scrape produced no cells for years=%s; check "
            "JP_CUSTOMS_PRINCIPAL_COMMODITY_TABLES.",
            years,
        )
    return trade_cells


def _list_trade_cells_from_estat_table(
    *,
    stats_data_id: str,
    flow: str,
    year: int,
    year_set: set[int],
    product_codes: frozenset[str] | None,
) -> list[_JpCustomsTradeCell]:
    """Fetch and parse one e-Stat principal-commodity table for one year."""
    payload = fetch_estat_stats_data(
        stats_data_id=stats_data_id,
        query_params={
            "lang": "E",
            "cdCat02": JP_CUSTOMS_VALUE_YEAR_CAT02,
            "cdTime": f"{year}000000",
            "limit": "100000",
        },
        log_label=f"jp_customs:{stats_data_id}:{year}",
    )
    if payload is None:
        return []
    values = payload.get("values") or []
    if not values:
        logger.warning(
            "Japan Customs e-Stat table %s year=%s returned no VALUE rows.",
            stats_data_id,
            year,
        )
        return []
    class_objs = payload.get("class_objs")
    product_meta_by_code = _build_class_meta_by_code(class_objs, "cat01")
    partner_meta_by_code = _build_class_meta_by_code(class_objs, "area")
    # Usage of dict: keys are e-Stat time codes; values are display labels.
    time_labels_by_code: dict[str, str] = payload.get("time_labels_by_code") or {}
    trade_cells: list[_JpCustomsTradeCell] = []
    for raw_value_row in values:
        if not isinstance(raw_value_row, dict):
            continue
        trade_cell = _get_trade_cell_from_estat_value_row(
            raw_value_row,
            flow=flow,
            year_set=year_set,
            time_labels_by_code=time_labels_by_code,
            product_meta_by_code=product_meta_by_code,
            partner_meta_by_code=partner_meta_by_code,
            product_codes=product_codes,
        )
        if trade_cell is not None:
            trade_cells.append(trade_cell)
    return trade_cells


def _get_trade_cell_from_estat_value_row(
    value_row: EstatJsonObject,
    *,
    flow: str,
    year_set: set[int],
    time_labels_by_code: dict[str, str],
    product_meta_by_code: dict[str, _JpClassMeta],
    partner_meta_by_code: dict[str, _JpClassMeta],
    product_codes: frozenset[str] | None,
) -> _JpCustomsTradeCell | None:
    """Turn one e-Stat VALUE row into a trade cell, or None when it should be skipped."""
    raw_time = str(value_row.get("@time") or value_row.get("time") or "")
    time_label = time_labels_by_code.get(raw_time, raw_time)
    year_digits = "".join(character for character in time_label if character.isdigit())
    if not year_digits:
        year_digits = "".join(
            character for character in raw_time if character.isdigit()
        )
    year_text = year_digits[:4]
    if not year_text.isdigit() or int(year_text) not in year_set:
        return None
    raw_amount = value_row.get("$") or value_row.get("value")
    try:
        trade_value = float(str(raw_amount).replace(",", "")) * JP_CUSTOMS_VALUE_SCALE
    except (TypeError, ValueError):
        return None
    if trade_value <= 0:
        return None
    product_code = str(value_row.get("@cat01") or value_row.get("cat01") or "").strip()
    partner_code = str(value_row.get("@area") or value_row.get("area") or "").strip()
    product_meta = product_meta_by_code.get(product_code)
    if product_meta is None:
        return None
    if product_codes is not None:
        if product_code not in product_codes:
            return None
    elif product_meta["level"] != JP_CUSTOMS_PRODUCT_CLASS_LEVEL:
        return None
    if not partner_code or partner_code in _JP_CUSTOMS_EXCLUDED_PARTNER_CODES:
        return None
    partner_meta = partner_meta_by_code.get(partner_code)
    return _JpCustomsTradeCell(
        period=date(int(year_text), 1, 1),
        flow=flow,
        product_code=product_code,
        product_label=product_meta["label"],
        partner_code=partner_code,
        partner_label=partner_meta["label"] if partner_meta else partner_code,
        trade_value=trade_value,
    )


def get_trade_rankings_from_jp_customs(
    years: list[int],
    *,
    top_n: int,
    product_codes: list[str] | None = None,
    product_label_by_code: dict[str, str] | None = None,
) -> list[ScrapedTradeRanking]:
    """Scrape Japan Top-N product and partner rankings.

    When 'product_codes' is set, 概況品 codes remap to those canonical HS codes.
    """
    label_by_code = product_label_by_code or {}
    estat_product_codes = (
        frozenset(JP_CUSTOMS_PRODUCT_CODE_ALIASES)
        if product_codes is not None
        else None
    )
    trade_cells = _list_cells_for_product_universe(
        _list_trade_cells_from_estat(years, product_codes=estat_product_codes),
        product_codes=product_codes,
        product_label_by_code=label_by_code,
    )
    return [
        *_list_top_trade_rankings_from_cells(
            trade_cells, breakdown=TradeBreakdownChoices.PRODUCT, top_n=top_n
        ),
        *_list_top_trade_rankings_from_cells(
            trade_cells, breakdown=TradeBreakdownChoices.PARTNER, top_n=top_n
        ),
    ]


def _group_jp_customs_cells_by_product_ranking_set(
    trade_cells: list[_JpCustomsTradeCell],
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow],
) -> dict[tuple[date, str, str], list[_JpCustomsTradeCell]]:
    """Group JP customs cells by (period, flow, product_code) ranking set."""
    # Usage of dict: group cells by (period, flow, product_code).
    cells_by_product_ranking_set: dict[
        tuple[date, str, str], list[_JpCustomsTradeCell]
    ] = {}
    for trade_cell in trade_cells:
        allowed_codes = _get_product_codes_for_period_flow(
            trade_product_codes_by_period_flow,
            period=trade_cell["period"],
            flow=trade_cell["flow"],
        )
        if allowed_codes is None or trade_cell["product_code"] not in allowed_codes:
            continue
        if trade_cell["partner_code"] in _JP_CUSTOMS_EXCLUDED_PARTNER_CODES:
            continue
        key = (trade_cell["period"], trade_cell["flow"], trade_cell["product_code"])
        cells_by_product_ranking_set.setdefault(key, []).append(trade_cell)
    return cells_by_product_ranking_set


def _list_jp_customs_product_partner_rankings_for_cells(
    *,
    period: date,
    flow: str,
    product_code: str,
    product_cells: list[_JpCustomsTradeCell],
    product_label_by_code: dict[str, str],
    top_n: int,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Build Top-N partner rankings for one product ranking set."""
    # Usage of dict: sum duplicate partner cells for the same product.
    totals_by_partner: dict[str, tuple[str, float]] = {}
    for trade_cell in product_cells:
        previous_label, previous_value = totals_by_partner.get(
            trade_cell["partner_code"],
            (trade_cell["partner_label"], 0.0),
        )
        totals_by_partner[trade_cell["partner_code"]] = (
            previous_label or trade_cell["partner_label"],
            previous_value + trade_cell["trade_value"],
        )
    ranked_partners = sorted(
        totals_by_partner.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )[:top_n]
    product_label = product_label_by_code.get(
        product_code,
        product_cells[0]["product_label"] if product_cells else product_code,
    )
    return [
        ScrapedTradeProductPartnerRanking(
            period=period,
            flow=flow,
            product_code=product_code,
            product_label=product_label,
            partner_code=partner_code,
            partner_label=partner_label,
            rank=rank,
            trade_value=trade_value,
        )
        for rank, (partner_code, (partner_label, trade_value)) in enumerate(
            ranked_partners, start=1
        )
    ]


def list_trade_partners_by_product_from_jp_customs(
    years: list[int],
    *,
    trade_product_codes_by_period_flow: list[TradeProductCodesByPeriodFlow],
    top_n: int,
    product_label_by_code: dict[str, str] | None = None,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Keep Top-N partners per product for the charts product filter."""
    if not trade_product_codes_by_period_flow:
        return []
    label_by_code = product_label_by_code or {}
    # Remap when requested codes are canonical HS; otherwise keep JP codes.
    requested_codes = {
        product_code
        for trade_product_codes in trade_product_codes_by_period_flow
        for product_code in trade_product_codes["product_codes"]
    }
    uses_product_codes = bool(
        requested_codes & set(JP_CUSTOMS_PRODUCT_CODE_ALIASES.values())
    )
    estat_product_codes = (
        frozenset(JP_CUSTOMS_PRODUCT_CODE_ALIASES) if uses_product_codes else None
    )
    trade_cells = _list_cells_for_product_universe(
        _list_trade_cells_from_estat(years, product_codes=estat_product_codes),
        product_codes=list(requested_codes) if uses_product_codes else None,
        product_label_by_code=label_by_code,
    )
    cells_by_product_ranking_set = _group_jp_customs_cells_by_product_ranking_set(
        trade_cells,
        trade_product_codes_by_period_flow,
    )
    scraped_rankings: list[ScrapedTradeProductPartnerRanking] = []
    for (
        period,
        flow,
        product_code,
    ), product_cells in cells_by_product_ranking_set.items():
        scraped_rankings.extend(
            _list_jp_customs_product_partner_rankings_for_cells(
                period=period,
                flow=flow,
                product_code=product_code,
                product_cells=product_cells,
                product_label_by_code=label_by_code,
                top_n=top_n,
            )
        )
    return scraped_rankings
