"""Scrape US trade rankings from Census International Trade."""

import logging
from datetime import date
from typing import Required, TypedDict

import requests
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeFlowChoices,
)
from economic_overview.services.config import (
    CENSUS_INTLTRADE_EXCLUDED_CTY_CODES,
    CENSUS_INTLTRADE_EXPORTS_HS_URL,
    CENSUS_INTLTRADE_IMPORTS_HS_URL,
    CENSUS_INTLTRADE_WORLD_CTY_CODE,
)
from economic_overview.services.scrapers.common import (
    ScrapedTradeProductPartnerRanking,
    ScrapedTradeRanking,
    TradeProductCodesByPeriodFlow,
)

logger = logging.getLogger(__name__)

_CENSUS_URL_BY_FLOW: dict[TradeFlowChoices, str] = {
    TradeFlowChoices.IMPORT: CENSUS_INTLTRADE_IMPORTS_HS_URL,
    TradeFlowChoices.EXPORT: CENSUS_INTLTRADE_EXPORTS_HS_URL,
}
_CENSUS_COMMODITY_FIELD_BY_FLOW: dict[TradeFlowChoices, str] = {
    TradeFlowChoices.IMPORT: "I_COMMODITY",
    TradeFlowChoices.EXPORT: "E_COMMODITY",
}
_CENSUS_COMMODITY_LABEL_FIELD_BY_FLOW: dict[TradeFlowChoices, str] = {
    TradeFlowChoices.IMPORT: "I_COMMODITY_LDESC",
    TradeFlowChoices.EXPORT: "E_COMMODITY_LDESC",
}
_CENSUS_VALUE_FIELD_BY_FLOW: dict[TradeFlowChoices, str] = {
    TradeFlowChoices.IMPORT: "GEN_VAL_YR",
    TradeFlowChoices.EXPORT: "ALL_VAL_YR",
}


class _CensusTradeRow(TypedDict, total=False):
    """One Census International Trade API row after header→value zip."""

    commodity_code: str
    commodity_label: str
    partner_code: str
    partner_label: str
    trade_value: Required[float]


_CENSUS_TABLE_ADAPTER = TypeAdapter(list[list[str]])


def _get_census_api_key() -> str:
    """Return the configured Census API key, or an empty string when unset."""
    return (getattr(settings, "CENSUS_API_KEY", None) or "").strip()


def _fetch_census_table(
    *,
    flow: TradeFlowChoices,
    year: int,
    get_fields: list[str],
    extra_params: dict[str, str],
) -> list[list[str]] | None:
    """GET one Census intltrade HS table; return header + data rows."""
    api_key = _get_census_api_key()
    if not api_key:
        logger.warning("CENSUS_API_KEY is empty; skipping Census trade scrape.")
        return None
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    request_params: dict[str, str] = {
        "get": ",".join(get_fields),
        "YEAR": str(year),
        "MONTH": "12",
        "key": api_key,
        **extra_params,
    }
    response = requests.get(
        _CENSUS_URL_BY_FLOW[flow],
        params=request_params,
        timeout=180,
        allow_redirects=True,
    )
    if response.status_code == 204 or not response.content:
        logger.warning(
            "Census trade empty response for year=%s flow=%s fields=%s",
            year,
            flow.value,
            get_fields,
        )
        return None
    if response.status_code >= 400:
        logger.warning(
            "Census trade HTTP %s for year=%s flow=%s: %s",
            response.status_code,
            year,
            flow.value,
            response.text[:200],
        )
        return None
    try:
        return _CENSUS_TABLE_ADAPTER.validate_python(response.json())
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("Census trade JSON validation failed: %s", exc)
        return None


def _list_census_trade_rows(
    table: list[list[str]],
    *,
    flow: TradeFlowChoices,
    include_commodity: bool,
    include_partner: bool,
) -> list[_CensusTradeRow]:
    """Zip Census header/data rows into typed trade rows."""
    if len(table) < 2:
        return []
    # Header row is always first in Census JSON tables.
    header = table[0]
    commodity_field = _CENSUS_COMMODITY_FIELD_BY_FLOW[flow]
    commodity_label_field = _CENSUS_COMMODITY_LABEL_FIELD_BY_FLOW[flow]
    value_field = _CENSUS_VALUE_FIELD_BY_FLOW[flow]
    rows: list[_CensusTradeRow] = []
    for raw_row in table[1:]:
        # Usage of dict: keys are Census column names from the header row.
        cells_by_name: dict[str, str] = {
            header[index]: raw_row[index]
            for index in range(min(len(header), len(raw_row)))
        }
        raw_value = cells_by_name.get(value_field, "")
        try:
            trade_value = float(raw_value)
        except ValueError:
            continue
        if trade_value <= 0:
            continue
        trade_row = _CensusTradeRow(trade_value=trade_value)
        if include_commodity:
            trade_row["commodity_code"] = cells_by_name.get(commodity_field, "").strip()
            trade_row["commodity_label"] = cells_by_name.get(
                commodity_label_field, ""
            ).strip()
        if include_partner:
            trade_row["partner_code"] = cells_by_name.get("CTY_CODE", "").strip()
            trade_row["partner_label"] = cells_by_name.get("CTY_NAME", "").strip()
        rows.append(trade_row)
    return rows


def _is_census_country_partner(partner_code: str) -> bool:
    """Return True when the Census CTY_CODE looks like a country, not a group."""
    if (
        not partner_code
        or partner_code in CENSUS_INTLTRADE_EXCLUDED_CTY_CODES
        or partner_code == CENSUS_INTLTRADE_WORLD_CTY_CODE
    ):
        return False
    # Continental / residual groups use codes like 5XXX.
    if "X" in partner_code.upper():
        return False
    # Multilateral aggregates (OECD, APEC, EU, …) use 00xx codes.
    if partner_code.startswith("00"):
        return False
    return partner_code.isdigit() and len(partner_code) == 4


def _get_census_commodity_level(product_code: str) -> str:
    """Pick Census COMM_LVL from the product code length."""
    if len(product_code) > 4:
        return "HS6"
    if len(product_code) > 2:
        return "HS4"
    return "HS2"


def _list_top_trade_rankings_from_rows(
    rows: list[_CensusTradeRow],
    *,
    period: date,
    flow: TradeFlowChoices,
    breakdown: TradeBreakdownChoices,
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Filter aggregates, sort Census rows, and keep Top-N rankings."""
    # Usage of dict: keys are item codes; values are label + summed trade value.
    totals_by_item_code: dict[str, tuple[str, float]] = {}
    for row in rows:
        if breakdown == TradeBreakdownChoices.PRODUCT:
            item_code = row.get("commodity_code", "")
            item_label = row.get("commodity_label", "") or item_code
        else:
            item_code = row.get("partner_code", "")
            item_label = row.get("partner_label", "") or item_code
            if not _is_census_country_partner(item_code):
                continue
        if not item_code:
            continue
        previous_label, previous_value = totals_by_item_code.get(
            item_code, (item_label, 0.0)
        )
        totals_by_item_code[item_code] = (
            previous_label or item_label,
            previous_value + row["trade_value"],
        )

    ranked_rows = sorted(
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
            ranked_rows, start=1
        )
    ]


def _list_ranked_census_partner_cells(
    ranked_partners: list[_CensusTradeRow],
    *,
    period: date,
    flow: TradeFlowChoices,
    product_code: str,
    product_label: str,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Turn ranked Census partner rows into product×partner scrape cells."""
    scraped_rankings: list[ScrapedTradeProductPartnerRanking] = []
    for rank, row in enumerate(ranked_partners, start=1):
        partner_code = row.get("partner_code", "")
        if not partner_code:
            continue
        resolved_label = row.get("commodity_label", "") or product_label or product_code
        scraped_rankings.append(
            ScrapedTradeProductPartnerRanking(
                period=period,
                flow=flow.value,
                product_code=product_code,
                product_label=resolved_label,
                partner_code=partner_code,
                partner_label=row.get("partner_label", "") or partner_code,
                rank=rank,
                trade_value=row["trade_value"],
            )
        )
    return scraped_rankings


def _list_census_partners_for_product(
    *,
    period: date,
    flow: TradeFlowChoices,
    product_code: str,
    product_label: str,
    commodity_level: str,
    top_n: int,
) -> list[ScrapedTradeProductPartnerRanking]:
    """Fetch Top-N country partners for one Census commodity code."""
    commodity_field = _CENSUS_COMMODITY_FIELD_BY_FLOW[flow]
    commodity_label_field = _CENSUS_COMMODITY_LABEL_FIELD_BY_FLOW[flow]
    value_field = _CENSUS_VALUE_FIELD_BY_FLOW[flow]
    table = _fetch_census_table(
        flow=flow,
        year=period.year,
        get_fields=[
            "CTY_CODE",
            "CTY_NAME",
            commodity_field,
            commodity_label_field,
            value_field,
        ],
        extra_params={
            "COMM_LVL": commodity_level,
            commodity_field: product_code,
        },
    )
    if table is None:
        return []
    partner_rows = [
        row
        for row in _list_census_trade_rows(
            table,
            flow=flow,
            include_commodity=True,
            include_partner=True,
        )
        if _is_census_country_partner(row.get("partner_code", ""))
    ]
    ranked_partners = sorted(
        partner_rows,
        key=lambda row: row["trade_value"],
        reverse=True,
    )[:top_n]
    return _list_ranked_census_partner_cells(
        ranked_partners,
        period=period,
        flow=flow,
        product_code=product_code,
        product_label=product_label,
    )


def _add_census_product_world_total_for_code(
    totals_by_product_code: dict[str, tuple[str, float]],
    *,
    period: date,
    flow: TradeFlowChoices,
    product_code: str,
    product_label_by_code: dict[str, str],
) -> None:
    """Add world-total trade value for one product code into 'totals_by_product_code'."""
    commodity_level = _get_census_commodity_level(product_code)
    commodity_field = _CENSUS_COMMODITY_FIELD_BY_FLOW[flow]
    commodity_label_field = _CENSUS_COMMODITY_LABEL_FIELD_BY_FLOW[flow]
    value_field = _CENSUS_VALUE_FIELD_BY_FLOW[flow]
    table = _fetch_census_table(
        flow=flow,
        year=period.year,
        get_fields=[commodity_field, commodity_label_field, value_field],
        extra_params={
            "COMM_LVL": commodity_level,
            "CTY_CODE": CENSUS_INTLTRADE_WORLD_CTY_CODE,
            commodity_field: product_code,
        },
    )
    if table is None:
        return
    for row in _list_census_trade_rows(
        table,
        flow=flow,
        include_commodity=True,
        include_partner=False,
    ):
        item_code = row.get("commodity_code", "") or product_code
        item_label = (
            product_label_by_code.get(item_code)
            or row.get("commodity_label", "")
            or item_code
        )
        previous_label, previous_value = totals_by_product_code.get(
            item_code, (item_label, 0.0)
        )
        totals_by_product_code[item_code] = (
            previous_label or item_label,
            previous_value + row["trade_value"],
        )


def _list_census_product_rankings_for_codes(
    *,
    period: date,
    flow: TradeFlowChoices,
    product_codes: list[str],
    product_label_by_code: dict[str, str],
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Build product Top-N from world totals for an explicit product-code list."""
    # Usage of dict: keys are product codes; values are label + world trade value.
    totals_by_product_code: dict[str, tuple[str, float]] = {}
    for product_code in product_codes:
        _add_census_product_world_total_for_code(
            totals_by_product_code,
            period=period,
            flow=flow,
            product_code=product_code,
            product_label_by_code=product_label_by_code,
        )
    ranked_items = sorted(
        totals_by_product_code.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )[:top_n]
    return [
        ScrapedTradeRanking(
            period=period,
            flow=flow.value,
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            rank=rank,
            item_code=item_code,
            item_label=item_label,
            trade_value=trade_value,
        )
        for rank, (item_code, (item_label, trade_value)) in enumerate(
            ranked_items, start=1
        )
    ]


def _list_census_partner_rankings_for_codes(
    *,
    period: date,
    flow: TradeFlowChoices,
    product_codes: list[str],
    product_label_by_code: dict[str, str],
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Sum country partners across the product-code filter into a partner Top-N."""
    # Usage of dict: keys are partner codes; values are label + summed trade value.
    totals_by_partner_code: dict[str, tuple[str, float]] = {}
    for product_code in product_codes:
        partner_cells = _list_census_partners_for_product(
            period=period,
            flow=flow,
            product_code=product_code,
            product_label=product_label_by_code.get(product_code, product_code),
            commodity_level=_get_census_commodity_level(product_code),
            top_n=10_000,
        )
        for partner_cell in partner_cells:
            partner_code = partner_cell["partner_code"]
            previous_label, previous_value = totals_by_partner_code.get(
                partner_code, (partner_cell["partner_label"], 0.0)
            )
            totals_by_partner_code[partner_code] = (
                previous_label or partner_cell["partner_label"],
                previous_value + partner_cell["trade_value"],
            )
    ranked_partners = sorted(
        totals_by_partner_code.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )[:top_n]
    return [
        ScrapedTradeRanking(
            period=period,
            flow=flow.value,
            breakdown=TradeBreakdownChoices.PARTNER.value,
            rank=rank,
            item_code=partner_code,
            item_label=partner_label,
            trade_value=trade_value,
        )
        for rank, (partner_code, (partner_label, trade_value)) in enumerate(
            ranked_partners, start=1
        )
    ]


def _list_census_scraped_rankings_for_period_with_product_filter(
    *,
    period: date,
    flow: TradeFlowChoices,
    product_codes: list[str],
    product_label_by_code: dict[str, str],
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Scrape product and partner Top-N for one period and flow with a fixed list."""
    return [
        *_list_census_product_rankings_for_codes(
            period=period,
            flow=flow,
            product_codes=product_codes,
            product_label_by_code=product_label_by_code,
            top_n=top_n,
        ),
        *_list_census_partner_rankings_for_codes(
            period=period,
            flow=flow,
            product_codes=product_codes,
            product_label_by_code=product_label_by_code,
            top_n=top_n,
        ),
    ]


def _list_census_scraped_rankings_for_period_default_universe(
    *,
    period: date,
    year: int,
    flow: TradeFlowChoices,
    top_n: int,
) -> list[ScrapedTradeRanking]:
    """Scrape default HS2 product and all-commodity partner Top-N for one period."""
    commodity_field = _CENSUS_COMMODITY_FIELD_BY_FLOW[flow]
    commodity_label_field = _CENSUS_COMMODITY_LABEL_FIELD_BY_FLOW[flow]
    value_field = _CENSUS_VALUE_FIELD_BY_FLOW[flow]
    scraped_rankings: list[ScrapedTradeRanking] = []
    product_table = _fetch_census_table(
        flow=flow,
        year=year,
        get_fields=[commodity_field, commodity_label_field, value_field],
        extra_params={
            "COMM_LVL": "HS2",
            "CTY_CODE": CENSUS_INTLTRADE_WORLD_CTY_CODE,
        },
    )
    if product_table is not None:
        scraped_rankings.extend(
            _list_top_trade_rankings_from_rows(
                _list_census_trade_rows(
                    product_table,
                    flow=flow,
                    include_commodity=True,
                    include_partner=False,
                ),
                period=period,
                flow=flow,
                breakdown=TradeBreakdownChoices.PRODUCT,
                top_n=top_n,
            )
        )
    # Total trade by partner: all commodities ("-") without COMM_LVL.
    # COMM_LVL=HS2 + commodity="-" returns HTTP 204 from Census.
    partner_table = _fetch_census_table(
        flow=flow,
        year=year,
        get_fields=["CTY_CODE", "CTY_NAME", value_field],
        extra_params={commodity_field: "-"},
    )
    if partner_table is not None:
        scraped_rankings.extend(
            _list_top_trade_rankings_from_rows(
                _list_census_trade_rows(
                    partner_table,
                    flow=flow,
                    include_commodity=False,
                    include_partner=True,
                ),
                period=period,
                flow=flow,
                breakdown=TradeBreakdownChoices.PARTNER,
                top_n=top_n,
            )
        )
    return scraped_rankings


def get_trade_rankings_from_census(
    years: list[int],
    *,
    top_n: int,
    product_codes: list[str] | None = None,
    product_label_by_code: dict[str, str] | None = None,
) -> list[ScrapedTradeRanking]:
    """Scrape US Top-N product and partner rankings from Census.

    When 'product_codes' is set, product and partner rankings use that universe.
    """
    scraped_rankings: list[ScrapedTradeRanking] = []
    label_by_code = product_label_by_code or {}
    for year in years:
        period = date(year, 1, 1)
        for flow in TradeFlowChoices:
            if product_codes is not None:
                scraped_rankings.extend(
                    _list_census_scraped_rankings_for_period_with_product_filter(
                        period=period,
                        flow=flow,
                        product_codes=product_codes,
                        product_label_by_code=label_by_code,
                        top_n=top_n,
                    )
                )
                continue
            scraped_rankings.extend(
                _list_census_scraped_rankings_for_period_default_universe(
                    period=period,
                    year=year,
                    flow=flow,
                    top_n=top_n,
                )
            )
    return scraped_rankings


def list_trade_partners_by_product_from_census(
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
        if trade_product_codes["period"].year not in years:
            continue
        flow = TradeFlowChoices(trade_product_codes["flow"])
        for product_code in trade_product_codes["product_codes"]:
            scraped_rankings.extend(
                _list_census_partners_for_product(
                    period=trade_product_codes["period"],
                    flow=flow,
                    product_code=product_code,
                    product_label=label_by_code.get(product_code, product_code),
                    commodity_level=_get_census_commodity_level(product_code),
                    top_n=top_n,
                )
            )
    return scraped_rankings
