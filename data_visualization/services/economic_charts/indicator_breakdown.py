"""Indicator breakdown Trend + Share panels (Budget and GDP)."""

from datetime import date
from typing import NamedTuple, TypedDict

from dateutil.relativedelta import relativedelta

from core.services.time_series_calculation import TimeSeriesPoint
from data_visualization.services.config import (
    ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS,
    ChartPeriodWindow,
)
from data_visualization.services.economic_charts.line_charts import (
    ChartDataPoint,
    filter_time_series_by_period_window,
    format_period,
    get_time_series_by_indicator_id,
)
from data_visualization.services.time_series import (
    change_series_mode,
    convert_points_to_period_level,
    scale_amount_between_magnitudes,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
    IndicatorExpansionRelationChoices,
)
from economic_overview.services.config import ANNUALIZED_ABS_LEVEL_TICKERS

_SHARE_BREAKDOWN_MODE = "Share"
_EXPORTS_SERIES_LABEL = "Exports"
_IMPORTS_SERIES_LABEL = "Imports"
_GDP_TREND_ONLY_SERIES_LABELS = frozenset(
    {_EXPORTS_SERIES_LABEL, _IMPORTS_SERIES_LABEL}
)


class _CompositionPanelConfig(TypedDict):
    """Static wiring for one composition card (Budget or GDP)."""

    parent_series_label: str
    category: EconomicDataCategoryChoices
    subcategory: EconomicDataSubcategoryChoices
    panel_id: str
    title: str
    trend_title: str
    pie_title: str
    share_axis_label: str
    year_only: bool
    # Direct COMPONENT children of the parent that belong on the pie.
    pie_child_parent_series_label: str
    # Extra series labels shown on Trend lines only (not the pie).
    trend_only_series_labels: list[str]
    breakdown_modes: list[str]
    # When True, Trend multiselect starts with every series that has data.
    default_select_all_series: bool
    # When True, the Mode control sits in the Trend panel header.
    mode_in_trend_panel: bool
    # Share period dropdown options (quarter and/or year).
    pie_granularities: list[str]


_BUDGET_COMPOSITION_PANEL = _CompositionPanelConfig(
    parent_series_label="Annual Government Expenditures",
    category=EconomicDataCategoryChoices.GOVERNMENT,
    subcategory=EconomicDataSubcategoryChoices.BUDGET,
    panel_id="budget",
    title="Budget Expenditure Breakdown",
    trend_title="Trend",
    pie_title="Share",
    share_axis_label="Share of Annual Government Expenditures (%)",
    year_only=True,
    pie_child_parent_series_label="Annual Government Expenditures",
    trend_only_series_labels=[],
    breakdown_modes=[
        _SHARE_BREAKDOWN_MODE,
        IndicatorDisplayModeChoices.RAW.value,
        IndicatorDisplayModeChoices.ANNUAL.value,
    ],
    default_select_all_series=False,
    mode_in_trend_panel=False,
    pie_granularities=["year"],
)

_GDP_COMPOSITION_PANEL = _CompositionPanelConfig(
    parent_series_label="Real GDP",
    category=EconomicDataCategoryChoices.MACROECONOMICS,
    subcategory=EconomicDataSubcategoryChoices.GROWTH,
    panel_id="gdp",
    title="GDP Breakdown",
    trend_title="Trend",
    pie_title="Share",
    share_axis_label="Share of Real GDP (%)",
    year_only=False,
    pie_child_parent_series_label="Real GDP",
    trend_only_series_labels=[_EXPORTS_SERIES_LABEL, _IMPORTS_SERIES_LABEL],
    breakdown_modes=[
        _SHARE_BREAKDOWN_MODE,
        IndicatorDisplayModeChoices.RAW.value,
        IndicatorDisplayModeChoices.QUARTER.value,
        IndicatorDisplayModeChoices.ANNUALIZED_QUARTER.value,
        IndicatorDisplayModeChoices.ANNUAL.value,
        IndicatorDisplayModeChoices.REL_QOQ.value,
        IndicatorDisplayModeChoices.REL_YOY.value,
        IndicatorDisplayModeChoices.CONTR_QOQ.value,
        IndicatorDisplayModeChoices.CONTR_YOY.value,
    ],
    default_select_all_series=True,
    mode_in_trend_panel=True,
    pie_granularities=["quarter", "year"],
)

_COMPOSITION_PANEL_CONFIGS: list[_CompositionPanelConfig] = [
    _GDP_COMPOSITION_PANEL,
    _BUDGET_COMPOSITION_PANEL,
]


def is_composition_owned_series(
    indicator: EconomicIndicatorInformationModel,
) -> bool:
    """Return whether this series belongs on a composition card, not slot charts."""
    if (
        indicator.expansion_relation == IndicatorExpansionRelationChoices.COMPONENT
        and indicator.parent_series_label
        == _BUDGET_COMPOSITION_PANEL["parent_series_label"]
    ):
        return True
    if indicator.category != EconomicDataCategoryChoices.MACROECONOMICS.value:
        return False
    if indicator.subcategory != EconomicDataSubcategoryChoices.GROWTH.value:
        return False
    if (
        indicator.expansion_relation == IndicatorExpansionRelationChoices.COMPONENT
        and indicator.parent_series_label
        == _GDP_COMPOSITION_PANEL["parent_series_label"]
    ):
        return True
    return indicator.series_label in _GDP_TREND_ONLY_SERIES_LABELS


class CompositionPieSlice(TypedDict):
    """One child's share of the parent for a single pie period."""

    name: str
    share: float


class CompositionMultiselectIndicator(TypedDict):
    """One indicator entry in the composition multiselect."""

    series_label: str
    name: str
    description: str
    include_in_pie: bool


class CompositionLocationOption(TypedDict):
    """One country choice on a composition card country dropdown."""

    code: str
    label: str


class CompositionLocationData(TypedDict):
    """Per-country composition payload inside one card."""

    # Usage of dict: breakdown mode label → line points for that mode.
    line_data_by_mode: dict[str, list[ChartDataPoint]]
    # Usage of dict: breakdown mode label → Y-axis title.
    value_axis_label_by_mode: dict[str, str]
    multiselect_indicators: list[CompositionMultiselectIndicator]
    default_selected_series_labels: list[str]
    # Usage of dict: pie granularity → formatted period → pie slices.
    pie_by_period_by_granularity: dict[str, dict[str, list[CompositionPieSlice]]]
    # Usage of dict: pie granularity → newest-first period labels.
    periods_by_granularity: dict[str, list[str]]
    available_pie_granularities: list[str]
    default_pie_granularity: str
    available_breakdown_modes: list[str]
    default_breakdown_mode: str
    mode_in_trend_panel: bool


class CompositionChartPanel(TypedDict):
    """Combined Trend + Share composition card for one parent series."""

    category: str
    panel_id: str
    title: str
    trend_title: str
    pie_title: str
    available_locations: list[CompositionLocationOption]
    default_location: str
    # Usage of dict: location code → per-country composition payload.
    by_location: dict[str, CompositionLocationData]


class _CompositionSharePoint(NamedTuple):
    """One child's share of its parent on a single period."""

    period: date
    period_label: str
    share_percent: float


def _scale_composition_value_to_parent_unit(
    value: float,
    child_unit: str,
    parent_unit: str,
) -> float:
    """Align child and parent amount magnitudes before dividing into a share."""
    amount_units = {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }
    if (
        child_unit in amount_units
        and parent_unit in amount_units
        and child_unit != parent_unit
    ):
        return scale_amount_between_magnitudes(
            value,
            IndicatorAmountMagnitudeChoices(child_unit),
            IndicatorAmountMagnitudeChoices(parent_unit),
        )
    return value


def _build_composition_share_series(
    *,
    child_points: list[TimeSeriesPoint],
    parent_value_by_period: dict[date, float],
    child_unit: str,
    parent_unit: str,
    frequency: EconomicPublicationFrequencyChoices,
    year_only: bool,
) -> list[_CompositionSharePoint]:
    """Return each overlapping period as the child's share of the parent, in percent."""
    share_points: list[_CompositionSharePoint] = []
    for child_point in child_points:
        parent_value = parent_value_by_period.get(child_point.period)
        if parent_value is None or parent_value == 0:
            continue
        if year_only and child_point.period.month != 1:
            # Annual composition uses calendar-year totals stamped on January 1.
            continue
        scaled_child_value = _scale_composition_value_to_parent_unit(
            child_point.value, child_unit, parent_unit
        )
        period_frequency = (
            EconomicPublicationFrequencyChoices.ANNUAL if year_only else frequency
        )
        share_points.append(
            _CompositionSharePoint(
                period=child_point.period,
                period_label=format_period(child_point.period, period_frequency),
                share_percent=(scaled_child_value / parent_value) * 100.0,
            )
        )
    return share_points


class _CompositionParentAndChildren(NamedTuple):
    """Parent indicator plus pie children and Trend-only line series."""

    parent_indicator: EconomicIndicatorInformationModel
    pie_child_indicators: list[EconomicIndicatorInformationModel]
    trend_only_indicators: list[EconomicIndicatorInformationModel]


def _list_composition_child_indicators(
    location: EconomicDataLocationChoices,
    panel: _CompositionPanelConfig,
    *,
    parent_series_label: str,
) -> list[EconomicIndicatorInformationModel]:
    """Return COMPONENT children of one parent series for this panel slot."""
    return list(
        EconomicIndicatorInformationModel.objects.filter(
            location=location.value,
            category=panel["category"].value,
            subcategory=panel["subcategory"].value,
            parent_series_label=parent_series_label,
            expansion_relation=IndicatorExpansionRelationChoices.COMPONENT,
            is_hidden=False,
        ).order_by("id")
    )


def _list_composition_trend_only_indicators(
    location: EconomicDataLocationChoices,
    panel: _CompositionPanelConfig,
) -> list[EconomicIndicatorInformationModel]:
    """Return Trend-only series (Exports / Imports) that are not pie slices."""
    if not panel["trend_only_series_labels"]:
        return []
    return list(
        EconomicIndicatorInformationModel.objects.filter(
            location=location.value,
            category=panel["category"].value,
            subcategory=panel["subcategory"].value,
            series_label__in=panel["trend_only_series_labels"],
            is_hidden=False,
        ).order_by("id")
    )


def _get_composition_parent_and_children(
    location: EconomicDataLocationChoices,
    panel: _CompositionPanelConfig,
) -> _CompositionParentAndChildren | None:
    """Load the parent, pie children, and Trend-only series, or None when missing."""
    parent_indicator = (
        EconomicIndicatorInformationModel.objects.filter(
            location=location.value,
            series_label=panel["parent_series_label"],
            category=panel["category"].value,
            subcategory=panel["subcategory"].value,
            is_hidden=False,
        )
        .order_by("id")
        .first()
    )
    if parent_indicator is None:
        return None
    pie_child_indicators = _list_composition_child_indicators(
        location,
        panel,
        parent_series_label=panel["pie_child_parent_series_label"],
    )
    if not pie_child_indicators:
        return None
    return _CompositionParentAndChildren(
        parent_indicator=parent_indicator,
        pie_child_indicators=pie_child_indicators,
        trend_only_indicators=_list_composition_trend_only_indicators(location, panel),
    )


def _get_composition_share_series_by_child(
    *,
    parent_indicator: EconomicIndicatorInformationModel,
    child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    year_only: bool,
) -> dict[str, list[_CompositionSharePoint]]:
    """Return each child's share-of-parent series keyed by series label."""
    parent_points = time_series_by_indicator_id.get(parent_indicator.id, [])
    if not parent_points:
        return {}
    # Usage of dict: period date → parent level.
    parent_value_by_period: dict[date, float] = {
        point.period: point.value for point in parent_points
    }
    # Usage of dict: child series label → share observations.
    share_series_by_child_series_label: dict[str, list[_CompositionSharePoint]] = {}
    for child_indicator in child_indicators:
        share_points = _build_composition_share_series(
            child_points=time_series_by_indicator_id.get(child_indicator.id, []),
            parent_value_by_period=parent_value_by_period,
            child_unit=child_indicator.base_unit,
            parent_unit=parent_indicator.base_unit,
            frequency=EconomicPublicationFrequencyChoices(child_indicator.frequency),
            year_only=year_only,
        )
        if share_points:
            share_series_by_child_series_label[child_indicator.series_label] = (
                share_points
            )
    return share_series_by_child_series_label


class _CompositionShareTables(NamedTuple):
    """Share series plus period pivots used to draw lines and pies."""

    # Usage of dict: child series label → share observations.
    share_series_by_child_series_label: dict[str, list[_CompositionSharePoint]]
    # Usage of dict: formatted period → child series label → share percent.
    share_by_period_and_child: dict[str, dict[str, float]]
    # Usage of dict: formatted period label → underlying period date.
    period_date_by_label: dict[str, date]


def _get_composition_share_tables(
    share_series_by_child_series_label: dict[str, list[_CompositionSharePoint]],
) -> _CompositionShareTables | None:
    """Pivot child share series into period tables for pies and defaults."""
    # Usage of dict: formatted period → child series label → share percent.
    share_by_period_and_child: dict[str, dict[str, float]] = {}
    # Usage of dict: formatted period label → underlying period date.
    period_date_by_label: dict[str, date] = {}
    for child_series_label, share_points in share_series_by_child_series_label.items():
        for share_point in share_points:
            period_date_by_label[share_point.period_label] = share_point.period
            share_by_period_and_child.setdefault(share_point.period_label, {})[
                child_series_label
            ] = share_point.share_percent
    if not share_by_period_and_child:
        return None
    return _CompositionShareTables(
        share_series_by_child_series_label=share_series_by_child_series_label,
        share_by_period_and_child=share_by_period_and_child,
        period_date_by_label=period_date_by_label,
    )


def _list_composition_periods_newest_first(
    share_tables: _CompositionShareTables,
) -> list[str]:
    """Return formatted period labels newest-first for the pie dropdown."""
    return sorted(
        share_tables.share_by_period_and_child.keys(),
        key=lambda period_label: share_tables.period_date_by_label[period_label],
        reverse=True,
    )


def _list_default_composition_series_labels(
    share_by_period_and_child: dict[str, dict[str, float]],
    periods: list[str],
    *,
    pie_series_labels: set[str],
    series_labels_with_data: set[str],
    default_select_all_series: bool,
) -> list[str]:
    """Return default Trend multiselect labels (all series, or top three pie shares)."""
    if default_select_all_series:
        return sorted(series_labels_with_data)
    # Index 0 is the latest period with any child share.
    latest_shares = {
        series_label: share
        for series_label, share in share_by_period_and_child[periods[0]].items()
        if series_label in pie_series_labels
    }
    # Top three pie contributors by latest share are the Trend chart defaults.
    return [
        child_series_label
        for child_series_label, _share in sorted(
            latest_shares.items(),
            key=lambda child_share: child_share[1],
            reverse=True,
        )[:3]
    ]


def _list_composition_multiselect_indicators(
    pie_child_indicators: list[EconomicIndicatorInformationModel],
    trend_only_indicators: list[EconomicIndicatorInformationModel],
    series_labels_with_data: set[str],
) -> list[CompositionMultiselectIndicator]:
    """Return composition-multiselect indicators that have line data."""
    multiselect_indicators: list[CompositionMultiselectIndicator] = []
    for child_indicator in sorted(
        [*pie_child_indicators, *trend_only_indicators],
        key=lambda indicator: indicator.series_label,
    ):
        if child_indicator.series_label not in series_labels_with_data:
            continue
        multiselect_indicators.append(
            CompositionMultiselectIndicator(
                series_label=child_indicator.series_label,
                name=child_indicator.series_label,
                description=child_indicator.description or "",
                include_in_pie=child_indicator.series_label
                not in _GDP_TREND_ONLY_SERIES_LABELS,
            )
        )
    return multiselect_indicators


def _list_share_mode_line_data(
    share_series_by_child_series_label: dict[str, list[_CompositionSharePoint]],
    period_window: ChartPeriodWindow,
) -> list[ChartDataPoint]:
    """Return share line points for every child inside the period window."""
    line_data: list[ChartDataPoint] = []
    for child_series_label, share_points in share_series_by_child_series_label.items():
        filtered_points = filter_time_series_by_period_window(
            [
                TimeSeriesPoint(
                    period=share_point.period, value=share_point.share_percent
                )
                for share_point in share_points
            ],
            period_window,
        )
        # Usage of dict: period date → formatted label for the filtered window.
        period_label_by_date: dict[date, str] = {
            share_point.period: share_point.period_label for share_point in share_points
        }
        for filtered_point in filtered_points:
            period_label = period_label_by_date.get(filtered_point.period)
            if period_label is None:
                continue
            line_data.append(
                ChartDataPoint(
                    period=period_label,
                    data_value=filtered_point.value,
                    indicator_name=child_series_label,
                    unit_label="%",
                )
            )
    line_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return line_data


def _list_level_mode_line_data(
    *,
    child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    period_window: ChartPeriodWindow,
    mode: IndicatorDisplayModeChoices,
    year_only: bool,
) -> list[ChartDataPoint]:
    """Return level-based breakdown points for one display mode."""
    line_data: list[ChartDataPoint] = []
    for child_indicator in child_indicators:
        frequency = EconomicPublicationFrequencyChoices(child_indicator.frequency)
        source_points = time_series_by_indicator_id.get(child_indicator.id, [])
        if year_only:
            source_points = [
                point for point in source_points if point.period.month == 1
            ]
        transformed_points = change_series_mode(source_points, frequency, mode)
        filtered_points = filter_time_series_by_period_window(
            transformed_points, period_window
        )
        period_frequency = (
            EconomicPublicationFrequencyChoices.ANNUAL if year_only else frequency
        )
        unit_label = "%" if mode != IndicatorDisplayModeChoices.RAW else ""
        for filtered_point in filtered_points:
            line_data.append(
                ChartDataPoint(
                    period=format_period(filtered_point.period, period_frequency),
                    data_value=filtered_point.value,
                    indicator_name=child_indicator.series_label,
                    unit_label=unit_label,
                )
            )
    line_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return line_data


def _get_lookback_months_for_rel_contr_mode(mode: IndicatorDisplayModeChoices) -> int:
    """Return calendar months to look back for Rel / Contr modes."""
    if mode in {
        IndicatorDisplayModeChoices.REL_QOQ,
        IndicatorDisplayModeChoices.CONTR_QOQ,
    }:
        return 3
    return 12


def _list_rel_contr_mode_line_data(
    *,
    child_indicators: list[EconomicIndicatorInformationModel],
    parent_indicator: EconomicIndicatorInformationModel,
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    period_window: ChartPeriodWindow,
    mode: IndicatorDisplayModeChoices,
    year_only: bool,
) -> list[ChartDataPoint]:
    """Return Rel / Contr points: child change over prior parent level, in percent."""
    parent_points = time_series_by_indicator_id.get(parent_indicator.id, [])
    # Usage of dict: period date → parent level.
    parent_value_by_period: dict[date, float] = {
        point.period: point.value for point in parent_points
    }
    lookback_months = _get_lookback_months_for_rel_contr_mode(mode)
    line_data: list[ChartDataPoint] = []
    for child_indicator in child_indicators:
        frequency = EconomicPublicationFrequencyChoices(child_indicator.frequency)
        # Usage of dict: period date → child level.
        child_value_by_period: dict[date, float] = {
            point.period: point.value
            for point in time_series_by_indicator_id.get(child_indicator.id, [])
        }
        period_frequency = (
            EconomicPublicationFrequencyChoices.ANNUAL if year_only else frequency
        )
        transformed_points: list[TimeSeriesPoint] = []
        for period, child_value in sorted(child_value_by_period.items()):
            if year_only and period.month != 1:
                continue
            prior_period = period + relativedelta(months=-lookback_months)
            prior_child = child_value_by_period.get(prior_period)
            prior_parent = parent_value_by_period.get(prior_period)
            if prior_child is None or prior_parent is None or prior_parent == 0:
                continue
            contribution = ((child_value - prior_child) / prior_parent) * 100.0
            transformed_points.append(
                TimeSeriesPoint(period=period, value=contribution)
            )
        for filtered_point in filter_time_series_by_period_window(
            transformed_points, period_window
        ):
            line_data.append(
                ChartDataPoint(
                    period=format_period(filtered_point.period, period_frequency),
                    data_value=filtered_point.value,
                    indicator_name=child_indicator.series_label,
                    unit_label="%",
                )
            )
    line_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return line_data


def _get_breakdown_mode_axis_label(
    panel: _CompositionPanelConfig,
    mode_label: str,
) -> str:
    """Return the Y-axis title for one breakdown mode."""
    if mode_label == _SHARE_BREAKDOWN_MODE:
        return panel["share_axis_label"]
    if mode_label == IndicatorDisplayModeChoices.RAW.value:
        return "Level"
    return f"{mode_label} (%)"


def _build_line_data_by_mode(
    *,
    panel: _CompositionPanelConfig,
    parent_indicator: EconomicIndicatorInformationModel,
    line_child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    share_series_by_child_series_label: dict[str, list[_CompositionSharePoint]],
    period_window: ChartPeriodWindow,
) -> dict[str, list[ChartDataPoint]]:
    """Build breakdown line payloads for every configured mode."""
    # Usage of dict: breakdown mode label → line points.
    line_data_by_mode: dict[str, list[ChartDataPoint]] = {
        _SHARE_BREAKDOWN_MODE: _list_share_mode_line_data(
            share_series_by_child_series_label, period_window
        )
    }
    rel_contr_modes = {
        IndicatorDisplayModeChoices.REL_QOQ.value,
        IndicatorDisplayModeChoices.REL_YOY.value,
        IndicatorDisplayModeChoices.CONTR_QOQ.value,
        IndicatorDisplayModeChoices.CONTR_YOY.value,
    }
    for mode_label in panel["breakdown_modes"]:
        if mode_label == _SHARE_BREAKDOWN_MODE:
            continue
        if mode_label in rel_contr_modes:
            line_data_by_mode[mode_label] = _list_rel_contr_mode_line_data(
                child_indicators=line_child_indicators,
                parent_indicator=parent_indicator,
                time_series_by_indicator_id=time_series_by_indicator_id,
                period_window=period_window,
                mode=IndicatorDisplayModeChoices(mode_label),
                year_only=panel["year_only"],
            )
            continue
        line_data_by_mode[mode_label] = _list_level_mode_line_data(
            child_indicators=line_child_indicators,
            time_series_by_indicator_id=time_series_by_indicator_id,
            period_window=period_window,
            mode=IndicatorDisplayModeChoices(mode_label),
            year_only=panel["year_only"],
        )
    return line_data_by_mode


def _list_sorted_pie_slices(
    child_shares: dict[str, float],
) -> list[CompositionPieSlice]:
    """Return pie slices largest-share first."""
    return [
        CompositionPieSlice(name=child_series_label, share=share)
        for child_series_label, share in sorted(
            child_shares.items(),
            key=lambda child_share: child_share[1],
            reverse=True,
        )
    ]


def _get_composition_pie_by_period(
    share_by_period_and_child: dict[str, dict[str, float]],
    periods: list[str],
    *,
    pie_series_labels: set[str],
) -> dict[str, list[CompositionPieSlice]]:
    """Return pie slices per period for pie-eligible series only."""
    # Usage of dict: period label → pie slices for that period.
    pie_by_period: dict[str, list[CompositionPieSlice]] = {}
    for period_label in periods:
        child_shares = {
            series_label: share
            for series_label, share in share_by_period_and_child[period_label].items()
            if series_label in pie_series_labels
        }
        pie_by_period[period_label] = _list_sorted_pie_slices(child_shares)
    return pie_by_period


def _get_common_year_through_period(
    series_points: list[list[TimeSeriesPoint]],
    year: int,
) -> date | None:
    """Return the latest period every series shares in 'year'.

    Returns None when any series is missing that year.
    """
    max_periods: list[date] = []
    for points in series_points:
        year_periods = [point.period for point in points if point.period.year == year]
        if not year_periods:
            return None
        max_periods.append(max(year_periods))
    return min(max_periods)


def _sum_year_flow_through_period(
    points: list[TimeSeriesPoint],
    *,
    year: int,
    through_period: date,
    is_annualized: bool,
    child_unit: str,
    parent_unit: str,
) -> float | None:
    """Sum period-level flow for 'year' through 'through_period'.

    Values are scaled to the parent unit before summing.
    """
    period_level_points = convert_points_to_period_level(
        points, is_annualized=is_annualized
    )
    year_points = [
        point
        for point in period_level_points
        if point.period.year == year and point.period <= through_period
    ]
    if not year_points:
        return None
    total = sum(
        _scale_composition_value_to_parent_unit(point.value, child_unit, parent_unit)
        for point in year_points
    )
    return total


def _build_year_share_pie_by_period(
    *,
    parent_indicator: EconomicIndicatorInformationModel,
    pie_child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
) -> dict[str, list[CompositionPieSlice]]:
    """Build year Share pies by summing flows through the common latest period."""
    parent_points = time_series_by_indicator_id.get(parent_indicator.id, [])
    child_points_by_label: dict[str, list[TimeSeriesPoint]] = {
        child_indicator.series_label: time_series_by_indicator_id.get(
            child_indicator.id, []
        )
        for child_indicator in pie_child_indicators
    }
    all_series_points = [parent_points, *child_points_by_label.values()]
    years = sorted(
        {point.period.year for points in all_series_points for point in points},
        reverse=True,
    )
    # Usage of dict: year label → pie slices.
    pie_by_period: dict[str, list[CompositionPieSlice]] = {}
    for year in years:
        through_period = _get_common_year_through_period(all_series_points, year)
        if through_period is None:
            continue
        parent_total = _sum_year_flow_through_period(
            parent_points,
            year=year,
            through_period=through_period,
            is_annualized=parent_indicator.ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
            child_unit=parent_indicator.base_unit,
            parent_unit=parent_indicator.base_unit,
        )
        if parent_total is None or parent_total == 0:
            continue
        child_shares: dict[str, float] = {}
        for child_indicator in pie_child_indicators:
            child_total = _sum_year_flow_through_period(
                child_points_by_label[child_indicator.series_label],
                year=year,
                through_period=through_period,
                is_annualized=child_indicator.ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
                child_unit=child_indicator.base_unit,
                parent_unit=parent_indicator.base_unit,
            )
            if child_total is None:
                continue
            child_shares[child_indicator.series_label] = (
                child_total / parent_total
            ) * 100.0
        if child_shares:
            pie_by_period[str(year)] = _list_sorted_pie_slices(child_shares)
    return pie_by_period


def _get_default_pie_granularity(panel: _CompositionPanelConfig) -> str:
    """Return the default Share period granularity for this panel."""
    if "quarter" in panel["pie_granularities"]:
        return "quarter"
    # Budget / annual panels only expose year.
    return panel["pie_granularities"][0]


# Usage of tuple: pie slices and period labels keyed by share granularity.
def _build_pie_payloads_by_granularity(
    *,
    panel: _CompositionPanelConfig,
    parent_indicator: EconomicIndicatorInformationModel,
    pie_child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    share_tables: _CompositionShareTables,
    pie_series_labels: set[str],
) -> tuple[dict[str, dict[str, list[CompositionPieSlice]]], dict[str, list[str]]]:
    """Return pie slices and period lists keyed by Share granularity."""
    quarter_periods = _list_composition_periods_newest_first(share_tables)
    quarter_pie = _get_composition_pie_by_period(
        share_tables.share_by_period_and_child,
        quarter_periods,
        pie_series_labels=pie_series_labels,
    )
    # Usage of dict: pie granularity → period label → slices.
    pie_by_period_by_granularity: dict[str, dict[str, list[CompositionPieSlice]]] = {}
    # Usage of dict: pie granularity → newest-first period labels.
    periods_by_granularity: dict[str, list[str]] = {}
    if "quarter" in panel["pie_granularities"]:
        pie_by_period_by_granularity["quarter"] = quarter_pie
        periods_by_granularity["quarter"] = quarter_periods
    if "year" in panel["pie_granularities"]:
        if panel["year_only"]:
            pie_by_period_by_granularity["year"] = quarter_pie
            periods_by_granularity["year"] = quarter_periods
        else:
            year_pie = _build_year_share_pie_by_period(
                parent_indicator=parent_indicator,
                pie_child_indicators=pie_child_indicators,
                time_series_by_indicator_id=time_series_by_indicator_id,
            )
            pie_by_period_by_granularity["year"] = year_pie
            periods_by_granularity["year"] = list(year_pie.keys())
    return pie_by_period_by_granularity, periods_by_granularity


def _list_composition_series_labels_with_data(
    *,
    share_tables: _CompositionShareTables,
    trend_only_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
) -> set[str]:
    """Return pie and trend-only series labels that have data for composition."""
    series_labels_with_data = set(share_tables.share_series_by_child_series_label)
    for trend_only_indicator in trend_only_indicators:
        if time_series_by_indicator_id.get(trend_only_indicator.id):
            series_labels_with_data.add(trend_only_indicator.series_label)
    return series_labels_with_data


def _build_composition_location_data_from_share_tables(
    *,
    panel: _CompositionPanelConfig,
    parent_indicator: EconomicIndicatorInformationModel,
    pie_child_indicators: list[EconomicIndicatorInformationModel],
    trend_only_indicators: list[EconomicIndicatorInformationModel],
    line_child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    share_tables: _CompositionShareTables,
    period_window: ChartPeriodWindow,
    pie_series_labels: set[str],
    series_labels_with_data: set[str],
    pie_by_period_by_granularity: dict[str, dict[str, list[CompositionPieSlice]]],
    periods_by_granularity: dict[str, list[str]],
) -> CompositionLocationData:
    """Build the composition payload once pie tables and series labels are ready."""
    # Usage of dict: breakdown mode label → Y-axis title.
    value_axis_label_by_mode: dict[str, str] = {
        mode_label: _get_breakdown_mode_axis_label(panel, mode_label)
        for mode_label in panel["breakdown_modes"]
    }
    return CompositionLocationData(
        line_data_by_mode=_build_line_data_by_mode(
            panel=panel,
            parent_indicator=parent_indicator,
            line_child_indicators=line_child_indicators,
            time_series_by_indicator_id=time_series_by_indicator_id,
            share_series_by_child_series_label=(
                share_tables.share_series_by_child_series_label
            ),
            period_window=period_window,
        ),
        value_axis_label_by_mode=value_axis_label_by_mode,
        multiselect_indicators=_list_composition_multiselect_indicators(
            pie_child_indicators, trend_only_indicators, series_labels_with_data
        ),
        default_selected_series_labels=_list_default_composition_series_labels(
            share_tables.share_by_period_and_child,
            _list_composition_periods_newest_first(share_tables),
            pie_series_labels=pie_series_labels,
            series_labels_with_data=series_labels_with_data,
            default_select_all_series=panel["default_select_all_series"],
        ),
        pie_by_period_by_granularity=pie_by_period_by_granularity,
        periods_by_granularity=periods_by_granularity,
        available_pie_granularities=list(panel["pie_granularities"]),
        default_pie_granularity=_get_default_pie_granularity(panel),
        available_breakdown_modes=list(panel["breakdown_modes"]),
        default_breakdown_mode=_SHARE_BREAKDOWN_MODE,
        mode_in_trend_panel=panel["mode_in_trend_panel"],
    )


def _get_composition_location_data_from_share_tables(
    *,
    panel: _CompositionPanelConfig,
    parent_indicator: EconomicIndicatorInformationModel,
    pie_child_indicators: list[EconomicIndicatorInformationModel],
    trend_only_indicators: list[EconomicIndicatorInformationModel],
    line_child_indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    share_tables: _CompositionShareTables,
    period_window: ChartPeriodWindow,
) -> CompositionLocationData:
    """Assemble the per-country composition payload from share tables."""
    pie_series_labels = {
        child_indicator.series_label for child_indicator in pie_child_indicators
    }
    series_labels_with_data = _list_composition_series_labels_with_data(
        share_tables=share_tables,
        trend_only_indicators=trend_only_indicators,
        time_series_by_indicator_id=time_series_by_indicator_id,
    )
    pie_by_period_by_granularity, periods_by_granularity = (
        _build_pie_payloads_by_granularity(
            panel=panel,
            parent_indicator=parent_indicator,
            pie_child_indicators=pie_child_indicators,
            time_series_by_indicator_id=time_series_by_indicator_id,
            share_tables=share_tables,
            pie_series_labels=pie_series_labels,
        )
    )
    return _build_composition_location_data_from_share_tables(
        panel=panel,
        parent_indicator=parent_indicator,
        pie_child_indicators=pie_child_indicators,
        trend_only_indicators=trend_only_indicators,
        line_child_indicators=line_child_indicators,
        time_series_by_indicator_id=time_series_by_indicator_id,
        share_tables=share_tables,
        period_window=period_window,
        pie_series_labels=pie_series_labels,
        series_labels_with_data=series_labels_with_data,
        pie_by_period_by_granularity=pie_by_period_by_granularity,
        periods_by_granularity=periods_by_granularity,
    )


def _build_composition_location_data(
    location: EconomicDataLocationChoices,
    period_window: ChartPeriodWindow,
    panel: _CompositionPanelConfig,
) -> CompositionLocationData | None:
    """Build one country's composition payload for a panel config."""
    parent_and_children = _get_composition_parent_and_children(location, panel)
    if parent_and_children is None:
        return None
    parent_indicator = parent_and_children.parent_indicator
    pie_child_indicators = parent_and_children.pie_child_indicators
    trend_only_indicators = parent_and_children.trend_only_indicators
    line_child_indicators = [*pie_child_indicators, *trend_only_indicators]
    time_series_by_indicator_id = get_time_series_by_indicator_id(
        [parent_indicator, *line_child_indicators]
    )
    # Share mode and pies only use pie children; trend-only series stay on other modes.
    share_series_by_child_series_label = _get_composition_share_series_by_child(
        parent_indicator=parent_indicator,
        child_indicators=pie_child_indicators,
        time_series_by_indicator_id=time_series_by_indicator_id,
        year_only=panel["year_only"],
    )
    if not share_series_by_child_series_label:
        return None
    share_tables = _get_composition_share_tables(share_series_by_child_series_label)
    if share_tables is None:
        return None
    return _get_composition_location_data_from_share_tables(
        panel=panel,
        parent_indicator=parent_indicator,
        pie_child_indicators=pie_child_indicators,
        trend_only_indicators=trend_only_indicators,
        line_child_indicators=line_child_indicators,
        time_series_by_indicator_id=time_series_by_indicator_id,
        share_tables=share_tables,
        period_window=period_window,
    )


def _list_composition_locations(
    location: EconomicDataLocationChoices | None,
    *,
    cross_region: bool,
) -> list[EconomicDataLocationChoices]:
    """Return countries to build composition payloads for."""
    if cross_region:
        return list(ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS)
    if location is None:
        return []
    return [location]


def _build_one_composition_panel(
    locations: list[EconomicDataLocationChoices],
    period_window: ChartPeriodWindow,
    panel: _CompositionPanelConfig,
    *,
    default_location: EconomicDataLocationChoices | None,
) -> CompositionChartPanel | None:
    """Build one composition card across the requested locations."""
    # Usage of dict: location code → per-country composition payload.
    by_location: dict[str, CompositionLocationData] = {}
    available_locations: list[CompositionLocationOption] = []
    for location in locations:
        location_data = _build_composition_location_data(location, period_window, panel)
        if location_data is None:
            continue
        by_location[location.value] = location_data
        available_locations.append(
            CompositionLocationOption(code=location.value, label=str(location.label))
        )
    if not by_location:
        return None
    # available_locations follows 'locations' order, so index 0 is the
    # fallback default country.
    preferred_default = (
        default_location.value
        if default_location is not None and default_location.value in by_location
        else available_locations[0]["code"]
    )
    return CompositionChartPanel(
        category=str(panel["category"].label),
        panel_id=panel["panel_id"],
        title=panel["title"],
        trend_title=panel["trend_title"],
        pie_title=panel["pie_title"],
        available_locations=available_locations,
        default_location=preferred_default,
        by_location=by_location,
    )


def get_composition_chart_panels(
    location: EconomicDataLocationChoices | None,
    period_window: ChartPeriodWindow,
    *,
    cross_region: bool,
) -> list[CompositionChartPanel]:
    """Build Budget and GDP composition cards for the charts page."""
    locations = _list_composition_locations(location, cross_region=cross_region)
    if not locations:
        return []
    panels: list[CompositionChartPanel] = []
    for panel_config in _COMPOSITION_PANEL_CONFIGS:
        # Cross-region cards default to the first configured composition location.
        panel = _build_one_composition_panel(
            locations,
            period_window,
            panel_config,
            default_location=location if not cross_region else locations[0],
        )
        if panel is not None:
            panels.append(panel)
    return panels
