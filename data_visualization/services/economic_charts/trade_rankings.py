"""Build trade ranking panels for economic charts."""

from dataclasses import dataclass
from typing import NamedTuple, TypedDict

from data_visualization.services.economic_recap.table_content import (
    format_amount_unit_label,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    IndicatorAmountMagnitudeChoices,
)
from economic_overview.models.economic_indicators import EconomicDataCategoryChoices
from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeFlowChoices,
    TradeRankingModel,
    TradeTypeChoices,
)
from economic_overview.services.config import (
    EUROSTAT_COMEXT_EXCLUDED_PARTNER_CODES,
    TRADE_RANKING_CURRENCY_BY_LOCATION,
    TRADE_RANKING_LINE_TOP_N,
    TRADE_RANKING_LOCATIONS,
    TRADE_RANKING_PROFILE_BY_TYPE,
)

_UNSPECIFIED_PARTNER_LABEL_PREFIX = "Countries and territories not specified"


@dataclass(frozen=True)
class _TradeRankingPanel:
    """Static panel copy for one trade type (Top-N comes from the ranking profile)."""

    panel_id_prefix: str
    title_label: str
    description: str


_TRADE_RANKING_PANEL_BY_TYPE: dict[TradeTypeChoices, _TradeRankingPanel] = {
    TradeTypeChoices.MERCHANDISE: _TradeRankingPanel(
        panel_id_prefix="merchandise-trade",
        title_label="Merchandise Trade",
        description=(
            "Annual customs merchandise rankings (not balance-of-payments). "
            "Partners exclude world and regional aggregates. Partner view with a "
            "product filter reads that product's stored Top partners only."
        ),
    ),
    TradeTypeChoices.ENERGY: _TradeRankingPanel(
        panel_id_prefix="energy-trade",
        title_label="Energy Trade",
        description=(
            "Annual customs energy trade (HS energy products). Partner view with a "
            "product filter reads that product's stored Top partners only."
        ),
    ),
}


class TradeDisplayScale(NamedTuple):
    """Shared divisor and axis label for raw trade amounts on charts."""

    divisor: float
    axis_label: str


class TradeBreakdownOption(TypedDict):
    """One selectable breakdown option for trade ranking charts."""

    value: str
    label: str


class TradeFlowOption(TypedDict):
    """One selectable import/export option for trade ranking charts."""

    value: str
    label: str


class TradeSelectOption(TypedDict):
    """One product or partner option for trade ranking cross filters."""

    value: str
    label: str


class TradeBarPoint(TypedDict):
    """One bar on a trade ranking chart."""

    item_code: str
    item_label: str
    rank: int
    trade_value: float


class TradeRankingObservation(TypedDict):
    """One stored Top-N ranking record for client-side filtering."""

    year: int
    flow: str
    breakdown: str
    item_code: str
    item_label: str
    rank: int
    trade_value: float


class TradeCellObservation(TypedDict):
    """One product×partner trade cell for client-side filtering."""

    year: int
    flow: str
    product_code: str
    product_label: str
    partner_code: str
    partner_label: str
    rank: int
    trade_value: float


class TradeRankingChartsPanel(TypedDict):
    """Trade ranking panel payload for economic charts."""

    panel: str
    panel_label: str
    category: str
    panel_id: str
    title: str
    location: str
    as_of_year: int
    available_years: list[int]
    flow: str
    flow_options: list[TradeFlowOption]
    breakdown: str
    breakdown_options: list[TradeBreakdownOption]
    product_code: str
    product_options: list[TradeSelectOption]
    partner_code: str
    partner_options: list[TradeSelectOption]
    top_n: int
    max_top_n: int
    line_top_n: int
    ranking_observations: list[TradeRankingObservation]
    cell_observations: list[TradeCellObservation]
    bars: list[TradeBarPoint]
    value_axis_label: str
    description: str


def _list_trade_breakdown_options() -> list[TradeBreakdownOption]:
    """Return breakdown options for trade ranking charts."""
    return [
        TradeBreakdownOption(value=choice.value, label=str(choice.label))
        for choice in TradeBreakdownChoices
        if choice != TradeBreakdownChoices.PRODUCT_PARTNER
    ]


def _list_trade_flow_options() -> list[TradeFlowOption]:
    """Return import/export options for trade ranking charts."""
    return [
        TradeFlowOption(value=choice.value, label=str(choice.label))
        for choice in TradeFlowChoices
    ]


def _get_trade_display_scale(
    location: EconomicDataLocationChoices,
    max_abs_trade_value: float,
) -> TradeDisplayScale:
    """Pick a K/M/B/T divisor so chart values stay roughly within 1–999."""
    currency = TRADE_RANKING_CURRENCY_BY_LOCATION[location]
    magnitude_order = IndicatorAmountMagnitudeChoices.ordered()
    if max_abs_trade_value <= 0:
        magnitude = IndicatorAmountMagnitudeChoices.B
        divisor = 1000.0 ** (1 + magnitude_order.index(magnitude))
        return TradeDisplayScale(
            divisor=divisor,
            axis_label=format_amount_unit_label(magnitude, currency),
        )

    # Raw currency units enter the ladder at thousands (K).
    scaled_value = float(max_abs_trade_value) / 1000.0
    magnitude = IndicatorAmountMagnitudeChoices.K
    while abs(scaled_value) > 999:
        next_magnitude_index = magnitude_order.index(magnitude) + 1
        if next_magnitude_index >= len(magnitude_order):
            break
        scaled_value /= 1000.0
        magnitude = magnitude_order[next_magnitude_index]
    divisor = 1000.0 ** (1 + magnitude_order.index(magnitude))
    return TradeDisplayScale(
        divisor=divisor,
        axis_label=format_amount_unit_label(magnitude, currency),
    )


def _scale_trade_value(trade_value: float, *, divisor: float) -> float:
    """Divide a raw trade amount by the panel's shared display divisor."""
    if divisor == 0:
        return trade_value
    return trade_value / divisor


# Usage of tuple: active product and partner cross-filter codes for the breakdown.
def _get_selected_cross_codes(
    *,
    breakdown: TradeBreakdownChoices,
    product_code: str | None,
    partner_code: str | None,
    product_options: list[TradeSelectOption],
    partner_options: list[TradeSelectOption],
) -> tuple[str, str]:
    """Keep only the cross filter that matches the active breakdown."""
    selected_product_code = product_code or ""
    selected_partner_code = partner_code or ""
    if breakdown == TradeBreakdownChoices.PARTNER:
        if selected_product_code not in {option["value"] for option in product_options}:
            selected_product_code = ""
        return selected_product_code, ""
    if breakdown == TradeBreakdownChoices.PRODUCT:
        if selected_partner_code not in {option["value"] for option in partner_options}:
            selected_partner_code = ""
        return "", selected_partner_code
    return "", ""


class _TradeCrossSelection(NamedTuple):
    """Product/partner options and the active cross codes for one panel."""

    product_options: list[TradeSelectOption]
    partner_options: list[TradeSelectOption]
    product_code: str
    partner_code: str


def _list_trade_locations(
    location: EconomicDataLocationChoices | None,
    *,
    cross_region: bool,
) -> list[EconomicDataLocationChoices]:
    """Return locations to build panels for, or an empty list when none apply."""
    if cross_region:
        return list(TRADE_RANKING_LOCATIONS)
    if location is None:
        return []
    if location in TRADE_RANKING_LOCATIONS:
        return [location]
    return []


def _format_trade_partner_label(partner_label: str) -> str:
    """Drop trailing notes such as '(incl. Hong Kong)' from partner names."""
    cleaned_label = partner_label.strip()
    if cleaned_label.endswith(")"):
        open_paren = cleaned_label.rfind(" (")
        if open_paren > 0:
            return cleaned_label[:open_paren].strip()
    return cleaned_label


def _is_excluded_trade_partner(*, partner_code: str, partner_label: str) -> bool:
    """Return True for aggregate / unspecified partners that should not chart."""
    if partner_code in EUROSTAT_COMEXT_EXCLUDED_PARTNER_CODES:
        return True
    return _format_trade_partner_label(partner_label).startswith(
        _UNSPECIFIED_PARTNER_LABEL_PREFIX
    )


# Usage of tuple: ranked item code and display label for product or partner Top-N.
def _get_topn_item_code_and_label(
    ranking: TradeRankingModel,
) -> tuple[str, str]:
    """Return the ranked item code/label for a product or partner Top-N ranking."""
    if ranking.breakdown == TradeBreakdownChoices.PRODUCT.value:
        return ranking.product_code, ranking.product_label
    return ranking.partner_code, _format_trade_partner_label(ranking.partner_label)


def _list_trade_available_years(
    location: EconomicDataLocationChoices,
    *,
    trade_type: TradeTypeChoices,
) -> list[int]:
    """List years that have trade rankings for this location and type."""
    return sorted(
        {
            period.year
            for period in TradeRankingModel.objects.filter(
                trade_type=trade_type.value,
                location=location.value,
            ).values_list("period", flat=True)
        },
        reverse=True,
    )


def _list_trade_observations(
    location: EconomicDataLocationChoices,
    *,
    trade_type: TradeTypeChoices,
) -> list[TradeRankingObservation]:
    """Load every stored Top-N ranking record for one location and type."""
    rankings = TradeRankingModel.objects.filter(
        trade_type=trade_type.value,
        location=location.value,
        breakdown__in=[
            TradeBreakdownChoices.PRODUCT.value,
            TradeBreakdownChoices.PARTNER.value,
        ],
    ).order_by("period", "flow", "breakdown", "rank")
    observations: list[TradeRankingObservation] = []
    for ranking in rankings:
        item_code, item_label = _get_topn_item_code_and_label(ranking)
        if ranking.breakdown == TradeBreakdownChoices.PARTNER.value and (
            _is_excluded_trade_partner(
                partner_code=item_code, partner_label=ranking.partner_label
            )
        ):
            continue
        observations.append(
            TradeRankingObservation(
                year=ranking.period.year,
                flow=ranking.flow,
                breakdown=ranking.breakdown,
                item_code=item_code,
                item_label=item_label,
                rank=ranking.rank,
                trade_value=float(ranking.trade_value),
            )
        )
    return observations


def _list_trade_product_partner_observations(
    location: EconomicDataLocationChoices,
    product_codes: list[str],
    *,
    trade_type: TradeTypeChoices,
) -> list[TradeCellObservation]:
    """Load product×partner cells for the charts product filter."""
    if not product_codes:
        return []
    rankings = TradeRankingModel.objects.filter(
        trade_type=trade_type.value,
        location=location.value,
        breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
        product_code__in=product_codes,
    ).order_by("period", "flow", "product_code", "rank")
    cell_observations: list[TradeCellObservation] = []
    for ranking in rankings:
        if _is_excluded_trade_partner(
            partner_code=ranking.partner_code,
            partner_label=ranking.partner_label,
        ):
            continue
        cell_observations.append(
            TradeCellObservation(
                year=ranking.period.year,
                flow=ranking.flow,
                product_code=ranking.product_code,
                product_label=ranking.product_label,
                partner_code=ranking.partner_code,
                partner_label=_format_trade_partner_label(ranking.partner_label),
                rank=ranking.rank,
                trade_value=float(ranking.trade_value),
            )
        )
    return cell_observations


def _list_trade_product_options_from_observations(
    observations: list[TradeRankingObservation],
    *,
    year: int,
    flow: str,
) -> list[TradeSelectOption]:
    """List products present for one year/flow selection."""
    product_options: list[TradeSelectOption] = []
    for observation in observations:
        if (
            observation["year"] != year
            or observation["flow"] != flow
            or observation["breakdown"] != TradeBreakdownChoices.PRODUCT.value
        ):
            continue
        product_options.append(
            TradeSelectOption(
                value=observation["item_code"],
                label=observation["item_label"],
            )
        )
    product_options.sort(key=lambda option: option["label"])
    return product_options


def _list_trade_partner_options_from_observations(
    observations: list[TradeRankingObservation],
    *,
    year: int,
    flow: str,
) -> list[TradeSelectOption]:
    """List partners present for one year/flow selection."""
    partner_options: list[TradeSelectOption] = []
    for observation in observations:
        if (
            observation["year"] != year
            or observation["flow"] != flow
            or observation["breakdown"] != TradeBreakdownChoices.PARTNER.value
        ):
            continue
        partner_options.append(
            TradeSelectOption(
                value=observation["item_code"],
                label=observation["item_label"],
            )
        )
    partner_options.sort(key=lambda option: option["label"])
    return partner_options


def _list_trade_cross_bars(
    cell_observations: list[TradeCellObservation],
    *,
    year: int,
    flow: str,
    product_code: str,
    partner_code: str,
    top_n: int,
) -> list[TradeBarPoint]:
    """Build Top-N bars for a product×partner cross selection."""
    if product_code:
        matching_cells = [
            observation
            for observation in cell_observations
            if observation["year"] == year
            and observation["flow"] == flow
            and observation["product_code"] == product_code
            and observation["rank"] <= top_n
        ]
        matching_cells.sort(key=lambda observation: observation["rank"])
        return [
            TradeBarPoint(
                item_code=observation["partner_code"],
                item_label=observation["partner_label"],
                rank=observation["rank"],
                trade_value=observation["trade_value"],
            )
            for observation in matching_cells
        ]

    matching_cells = [
        observation
        for observation in cell_observations
        if observation["year"] == year
        and observation["flow"] == flow
        and observation["partner_code"] == partner_code
    ]
    matching_cells.sort(
        key=lambda observation: observation["trade_value"], reverse=True
    )
    return [
        TradeBarPoint(
            item_code=observation["product_code"],
            item_label=observation["product_label"],
            rank=rank,
            trade_value=observation["trade_value"],
        )
        for rank, observation in enumerate(matching_cells[:top_n], start=1)
    ]


def list_trade_bars_from_observations(
    observations: list[TradeRankingObservation],
    cell_observations: list[TradeCellObservation],
    *,
    year: int,
    flow: str,
    breakdown: str,
    product_code: str,
    partner_code: str,
    top_n: int,
) -> list[TradeBarPoint]:
    """Filter observations into Top-N bars for one chart selection."""
    if (breakdown == TradeBreakdownChoices.PARTNER.value and product_code) or (
        breakdown == TradeBreakdownChoices.PRODUCT.value and partner_code
    ):
        return _list_trade_cross_bars(
            cell_observations,
            year=year,
            flow=flow,
            product_code=product_code,
            partner_code=partner_code,
            top_n=top_n,
        )

    matching_observations = [
        observation
        for observation in observations
        if observation["year"] == year
        and observation["flow"] == flow
        and observation["breakdown"] == breakdown
        and observation["rank"] <= top_n
    ]
    matching_observations.sort(key=lambda observation: observation["rank"])
    return [
        TradeBarPoint(
            item_code=observation["item_code"],
            item_label=observation["item_label"],
            rank=observation["rank"],
            trade_value=observation["trade_value"],
        )
        for observation in matching_observations
    ]


def _scale_trade_observations(
    observations: list[TradeRankingObservation],
    *,
    divisor: float,
) -> list[TradeRankingObservation]:
    """Return ranking observations with trade values divided for the chart axis."""
    return [
        TradeRankingObservation(
            year=observation["year"],
            flow=observation["flow"],
            breakdown=observation["breakdown"],
            item_code=observation["item_code"],
            item_label=observation["item_label"],
            rank=observation["rank"],
            trade_value=_scale_trade_value(observation["trade_value"], divisor=divisor),
        )
        for observation in observations
    ]


def _scale_trade_cell_observations(
    observations: list[TradeCellObservation],
    *,
    divisor: float,
) -> list[TradeCellObservation]:
    """Return product×partner cells with trade values divided for the chart axis."""
    return [
        TradeCellObservation(
            year=observation["year"],
            flow=observation["flow"],
            product_code=observation["product_code"],
            product_label=observation["product_label"],
            partner_code=observation["partner_code"],
            partner_label=observation["partner_label"],
            rank=observation["rank"],
            trade_value=_scale_trade_value(observation["trade_value"], divisor=divisor),
        )
        for observation in observations
    ]


class _ScaledTradeObservations(NamedTuple):
    """Ranking and cross cells after shared display scaling."""

    observations: list[TradeRankingObservation]
    cell_observations: list[TradeCellObservation]
    axis_label: str


def _get_scaled_trade_observations(
    location: EconomicDataLocationChoices,
    raw_observations: list[TradeRankingObservation],
    *,
    trade_type: TradeTypeChoices,
) -> _ScaledTradeObservations:
    """Scale ranking and product×partner cells to one chart unit."""
    all_product_codes = sorted(
        {
            observation["item_code"]
            for observation in raw_observations
            if observation["breakdown"] == TradeBreakdownChoices.PRODUCT.value
        }
    )
    raw_cell_observations = _list_trade_product_partner_observations(
        location,
        all_product_codes,
        trade_type=trade_type,
    )
    max_abs_trade_value = max(
        [abs(observation["trade_value"]) for observation in raw_observations]
        + [abs(observation["trade_value"]) for observation in raw_cell_observations],
        default=0.0,
    )
    display_scale = _get_trade_display_scale(location, max_abs_trade_value)
    return _ScaledTradeObservations(
        observations=_scale_trade_observations(
            raw_observations, divisor=display_scale.divisor
        ),
        cell_observations=_scale_trade_cell_observations(
            raw_cell_observations, divisor=display_scale.divisor
        ),
        axis_label=display_scale.axis_label,
    )


def _get_trade_cross_selection(
    raw_observations: list[TradeRankingObservation],
    *,
    year: int,
    flow: str,
    breakdown: TradeBreakdownChoices,
    product_code: str | None,
    partner_code: str | None,
) -> _TradeCrossSelection:
    """Build cross-filter options and the active breakdown's code."""
    product_options = _list_trade_product_options_from_observations(
        raw_observations, year=year, flow=flow
    )
    partner_options = _list_trade_partner_options_from_observations(
        raw_observations, year=year, flow=flow
    )
    selected_product_code, selected_partner_code = _get_selected_cross_codes(
        breakdown=breakdown,
        product_code=product_code,
        partner_code=partner_code,
        product_options=product_options,
        partner_options=partner_options,
    )
    return _TradeCrossSelection(
        product_options=product_options,
        partner_options=partner_options,
        product_code=selected_product_code,
        partner_code=selected_partner_code,
    )


def _get_trade_ranking_charts_panel(
    location: EconomicDataLocationChoices,
    *,
    trade_type: TradeTypeChoices,
    panel: _TradeRankingPanel,
    available_years: list[int],
    as_of_year: int,
    flow: TradeFlowChoices,
    breakdown: TradeBreakdownChoices,
    cross: _TradeCrossSelection,
    scaled: _ScaledTradeObservations,
    bars: list[TradeBarPoint],
    capped_top_n: int,
    display_top_n: int,
) -> TradeRankingChartsPanel:
    """Assemble the charts panel TypedDict from already-scaled selections."""
    return TradeRankingChartsPanel(
        panel=trade_type.value.lower(),
        panel_label=panel.title_label,
        category=str(EconomicDataCategoryChoices.MACROECONOMICS.label),
        panel_id=f"{panel.panel_id_prefix}-{location.value.lower()}",
        title=f"{location.value} {panel.title_label} — {str(breakdown.label)}",
        location=location.value,
        as_of_year=as_of_year,
        available_years=available_years,
        flow=flow.value,
        flow_options=_list_trade_flow_options(),
        breakdown=breakdown.value,
        breakdown_options=_list_trade_breakdown_options(),
        product_code=cross.product_code,
        product_options=cross.product_options,
        partner_code=cross.partner_code,
        partner_options=cross.partner_options,
        top_n=capped_top_n,
        max_top_n=display_top_n,
        line_top_n=TRADE_RANKING_LINE_TOP_N,
        ranking_observations=scaled.observations,
        cell_observations=scaled.cell_observations,
        bars=bars,
        value_axis_label=scaled.axis_label,
        description=panel.description,
    )


def get_trade_ranking_panel(
    location: EconomicDataLocationChoices,
    *,
    trade_type: TradeTypeChoices,
    year: int | None = None,
    flow: TradeFlowChoices = TradeFlowChoices.IMPORT,
    breakdown: TradeBreakdownChoices = TradeBreakdownChoices.PRODUCT,
    product_code: str | None = None,
    partner_code: str | None = None,
    top_n: int | None = None,
) -> TradeRankingChartsPanel | None:
    """Build one trade ranking panel for a location and trade type."""
    panel = _TRADE_RANKING_PANEL_BY_TYPE[trade_type]
    profile = TRADE_RANKING_PROFILE_BY_TYPE[trade_type]
    available_years = _list_trade_available_years(location, trade_type=trade_type)
    if not available_years:
        return None
    # Newest year first in available_years.
    as_of_year = year if year in available_years else available_years[0]
    capped_top_n = min(max(top_n or profile.display_top_n, 1), profile.display_top_n)
    raw_observations = _list_trade_observations(location, trade_type=trade_type)
    cross = _get_trade_cross_selection(
        raw_observations,
        year=as_of_year,
        flow=flow.value,
        breakdown=breakdown,
        product_code=product_code,
        partner_code=partner_code,
    )
    scaled = _get_scaled_trade_observations(
        location, raw_observations, trade_type=trade_type
    )
    bars = list_trade_bars_from_observations(
        scaled.observations,
        scaled.cell_observations,
        year=as_of_year,
        flow=flow.value,
        breakdown=breakdown.value,
        product_code=cross.product_code,
        partner_code=cross.partner_code,
        top_n=capped_top_n,
    )
    return _get_trade_ranking_charts_panel(
        location,
        trade_type=trade_type,
        panel=panel,
        available_years=available_years,
        as_of_year=as_of_year,
        flow=flow,
        breakdown=breakdown,
        cross=cross,
        scaled=scaled,
        bars=bars,
        capped_top_n=capped_top_n,
        display_top_n=profile.display_top_n,
    )


def get_trade_ranking_panels(
    location: EconomicDataLocationChoices | None,
    *,
    cross_region: bool = False,
) -> list[TradeRankingChartsPanel]:
    """Return trade ranking panels for every trade type at the charts locations."""
    panels: list[TradeRankingChartsPanel] = []
    for panel_location in _list_trade_locations(location, cross_region=cross_region):
        for trade_type in TradeTypeChoices:
            panel = get_trade_ranking_panel(panel_location, trade_type=trade_type)
            if panel is not None:
                panels.append(panel)
    return panels
