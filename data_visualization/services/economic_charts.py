"""Build economic chart series payloads for the visualization UI."""

from datetime import date
from enum import Enum
from typing import NamedTuple, TypedDict

from pydantic import TypeAdapter

import economic_overview.services.economic_data as economic_data
from core.services import ValueChangeType, calculate_value_change
from data_visualization.services.cache import (
    EconomicDisplayCacheType,
    get_cached_economic_display,
    set_cached_economic_display,
)
from data_visualization.services.config import (
    ECONOMIC_CHARTS_DEFAULT_CONFIDENCE_TYPE_BY_LOCATION,
    ECONOMIC_CHARTS_EU_COUNTRIES,
    ECONOMIC_CHARTS_LOCATIONS,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
    IndicatorDisplayModeChoices,
)
from economic_overview.services.economic_data import get_lag_for_mode_change_calculation


class _EconomicChartsCategoryDefaults(TypedDict):
    """Per-category default selection strings (no region prefix)."""

    growth_indicator: str
    inflation_indicator: str
    government_indicator: str
    production_indicator: str
    sales_indicator: str
    labour_indicator: str
    housing_indicator: str
    confidence_indicator: str


def _get_default_mode_for_indicator_type(
    location: EconomicDataLocationChoices,
    indicator_type: str,
) -> IndicatorDisplayModeChoices:
    """Look up ``default_mode`` for ``location`` + ``type``; Raw if missing."""
    indicator = (
        EconomicIndicatorInformationModel.objects.filter(
            location=location.value,
            type=indicator_type,
        )
        .only("default_mode")
        .first()
    )
    if indicator is None:
        return IndicatorDisplayModeChoices.RAW
    return IndicatorDisplayModeChoices(indicator.default_mode)


def _encode_indicator_selection(
    indicator_type: str,
    mode: IndicatorDisplayModeChoices,
    location: EconomicDataLocationChoices | None = None,
) -> str:
    """Encode a chart selection for form / URL values.

    Single-region: ``Type|MODE``. Europe curves: ``Location|Type|MODE``.
    """
    if location is None:
        return f"{indicator_type}|{mode.value}"
    return f"{location.value}|{indicator_type}|{mode.value}"


def _encode_eu_default_curves(indicator_type: str) -> str:
    """Comma-join DE/ES/IT/FR defaults, each with that country's DB default mode."""
    return ",".join(
        _encode_indicator_selection(
            indicator_type,
            _get_default_mode_for_indicator_type(country, indicator_type),
            country,
        )
        for country in ECONOMIC_CHARTS_EU_COUNTRIES
    )


def get_default_indicator_selections(
    location: EconomicDataLocationChoices,
) -> _EconomicChartsCategoryDefaults:
    """Chart category defaults for ``location`` using each indicator's DB mode.

    Confidence type comes from
    ``ECONOMIC_CHARTS_DEFAULT_CONFIDENCE_TYPE_BY_LOCATION`` (empty when absent).
    """
    confidence_type = ECONOMIC_CHARTS_DEFAULT_CONFIDENCE_TYPE_BY_LOCATION.get(location)
    return _EconomicChartsCategoryDefaults(
        growth_indicator=_encode_indicator_selection(
            "GDP", _get_default_mode_for_indicator_type(location, "GDP")
        ),
        inflation_indicator=_encode_indicator_selection(
            "Consumer Price Index",
            _get_default_mode_for_indicator_type(location, "Consumer Price Index"),
        ),
        government_indicator=_encode_indicator_selection(
            "Government Debt (% of GDP)",
            _get_default_mode_for_indicator_type(
                location, "Government Debt (% of GDP)"
            ),
        ),
        production_indicator=_encode_indicator_selection(
            "Industrial Production",
            _get_default_mode_for_indicator_type(location, "Industrial Production"),
        ),
        sales_indicator=_encode_indicator_selection(
            "Retail Sales",
            _get_default_mode_for_indicator_type(location, "Retail Sales"),
        ),
        labour_indicator=_encode_indicator_selection(
            "Unemployment Rate",
            _get_default_mode_for_indicator_type(location, "Unemployment Rate"),
        ),
        housing_indicator=_encode_indicator_selection(
            "Home Prices",
            _get_default_mode_for_indicator_type(location, "Home Prices"),
        ),
        confidence_indicator=(
            _encode_indicator_selection(
                confidence_type,
                _get_default_mode_for_indicator_type(location, confidence_type),
            )
            if confidence_type
            else ""
        ),
    )


def get_default_eu_indicator_selections() -> _EconomicChartsCategoryDefaults:
    """Europe defaults: DE / ES / IT / FR curves per category (DB default modes)."""
    return _EconomicChartsCategoryDefaults(
        growth_indicator=_encode_eu_default_curves("GDP"),
        inflation_indicator=_encode_eu_default_curves("Consumer Price Index"),
        government_indicator=_encode_eu_default_curves("Government Debt (% of GDP)"),
        production_indicator=_encode_eu_default_curves("Industrial Production"),
        sales_indicator=_encode_eu_default_curves("Retail Sales"),
        labour_indicator=_encode_eu_default_curves("Unemployment Rate"),
        housing_indicator=_encode_eu_default_curves("Home Prices"),
        confidence_indicator="",
    )


class _ChartIndicatorOption(TypedDict):
    """One selectable series in the charts multiselect."""

    type: str  # Series key: ``GDP`` or ``DE|GDP``
    name: str  # Display label
    default_mode: str  # IndicatorDisplayModeChoices value from the DB


class _IndicatorsByCategory(TypedDict):
    """Indicators by category for economic charts dropdown."""

    category: str  # Display label (Choices.label)
    indicators: list[_ChartIndicatorOption]


class _EconomicChartsDropdownValues(TypedDict):
    """Dropdown values for economic charts."""

    locations: list[str]  # Display labels (Choices.label)
    categories: list[str]  # Display labels (Choices.label)
    indicators_by_category: list[_IndicatorsByCategory]


def get_economic_charts_dropdown_values(
    location: EconomicDataLocationChoices,
) -> _EconomicChartsDropdownValues:
    """Get dropdown values for economic charts."""
    categories = EconomicDataCategoryChoices.get_labels()
    locations = [str(loc.label) for loc in ECONOMIC_CHARTS_LOCATIONS]

    indicators_by_category: list[_IndicatorsByCategory] = []
    for category in EconomicDataCategoryChoices.ordered():
        if location == EconomicDataLocationChoices.EU:
            options: list[_ChartIndicatorOption] = []
            for country in ECONOMIC_CHARTS_EU_COUNTRIES:
                category_indicators = EconomicIndicatorInformationModel.objects.filter(
                    category=category.value,
                    location=country.value,
                ).order_by("id")
                for indicator in category_indicators:
                    options.append(
                        _ChartIndicatorOption(
                            type=f"{country.value}|{indicator.type}",
                            name=f"{country.label} — {indicator.type}",
                            default_mode=indicator.default_mode,
                        )
                    )
            indicators_by_category.append(
                _IndicatorsByCategory(category=str(category.label), indicators=options)
            )
        else:
            category_indicators = EconomicIndicatorInformationModel.objects.filter(
                category=category.value, location=location.value
            ).order_by("id")
            indicators_by_category.append(
                _IndicatorsByCategory(
                    category=str(category.label),
                    indicators=[
                        _ChartIndicatorOption(
                            type=indicator.type,
                            name=indicator.type,
                            default_mode=indicator.default_mode,
                        )
                        for indicator in category_indicators
                    ],
                )
            )
    return _EconomicChartsDropdownValues(
        categories=categories,
        locations=locations,
        indicators_by_category=indicators_by_category,
    )


class EconomicChartsFrontData(TypedDict):
    """Front data from the charts form (GET query / selected_values JSON)."""

    region: str  # Display label (Choices.label) from the UI
    period_window: str  # ChartPeriodWindow value from the UI

    # Indicator selections are UI Type or Type|MODE display strings.
    us_growth_indicator: str
    us_inflation_indicator: str
    us_government_indicator: str
    us_production_indicator: str
    us_sales_indicator: str
    us_labour_indicator: str
    us_housing_indicator: str
    us_confidence_indicator: str
    eu_growth_indicator: str
    eu_inflation_indicator: str
    eu_government_indicator: str
    eu_production_indicator: str
    eu_sales_indicator: str
    eu_labour_indicator: str
    eu_housing_indicator: str
    eu_confidence_indicator: str
    fr_growth_indicator: str
    fr_inflation_indicator: str
    fr_government_indicator: str
    fr_production_indicator: str
    fr_sales_indicator: str
    fr_labour_indicator: str
    fr_housing_indicator: str
    fr_confidence_indicator: str
    jp_growth_indicator: str
    jp_inflation_indicator: str
    jp_government_indicator: str
    jp_production_indicator: str
    jp_sales_indicator: str
    jp_labour_indicator: str
    jp_housing_indicator: str
    jp_confidence_indicator: str


class _SelectedIndicatorsByCategory(TypedDict):
    """Selected Indicators by Category"""

    category: EconomicDataCategoryChoices
    selected_indicators: list[str]  # UI Type or Type|MODE display strings


def get_selected_indicators_by_category(
    location: EconomicDataLocationChoices,
    front_data: EconomicChartsFrontData,
) -> list[_SelectedIndicatorsByCategory]:
    """Get selected indicators and reorganize by category."""
    selected_indicators_by_category = []
    for category in EconomicDataCategoryChoices.ordered():
        key = f"{location.value.lower()}_{category.lower()}_indicator"
        raw_value = front_data.get(key, "")
        selected_indicators = [
            indicator.strip() for indicator in raw_value.split(",") if indicator.strip()
        ]
        selected_indicators_by_category.append(
            _SelectedIndicatorsByCategory(
                category=category,
                selected_indicators=selected_indicators,
            )
        )
    return selected_indicators_by_category


class _TimeSeriesPoint(NamedTuple):
    """One period/value observation (raw absolute or after Abs/QoQ/QoQy/YoY)."""

    period: date
    value: float


def _change_series_mode(
    points: list[_TimeSeriesPoint],
    frequency: EconomicPublicationFrequencyChoices,
    mode: IndicatorDisplayModeChoices,
) -> list[_TimeSeriesPoint]:
    """Change a raw absolute time series to Abs / QoQ / QoQy / YoY mode."""
    if not points:
        return []
    ordered = sorted(points, key=lambda item: item.period)
    if mode == IndicatorDisplayModeChoices.RAW:
        return ordered

    lag = get_lag_for_mode_change_calculation(frequency, mode.value)
    result: list[_TimeSeriesPoint] = []
    for index in range(lag, len(ordered)):
        curr = ordered[index]
        prev = ordered[index - lag]
        change = calculate_value_change(
            curr.value,
            prev.value,
            (
                ValueChangeType.ANNUALIZED_PERCENT
                if mode == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER
                else ValueChangeType.PERCENT
            ),
            annualized_ratio=(
                4 if mode == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER else None
            ),
        )
        if change is None:
            continue
        result.append(_TimeSeriesPoint(period=curr.period, value=change))
    return result


class ChartPeriodWindow(str, Enum):
    """Shared chart history window presets."""

    ONE_YEAR = "1Y"
    THREE_YEARS = "3Y"
    FIVE_YEARS = "5Y"
    TEN_YEARS = "10Y"
    MAX = "Max"


# Usage of dict: ChartPeriodWindow → years of history (None = Max).
_PERIOD_WINDOW_YEARS: dict[ChartPeriodWindow, int | None] = {
    ChartPeriodWindow.ONE_YEAR: 1,
    ChartPeriodWindow.THREE_YEARS: 3,
    ChartPeriodWindow.FIVE_YEARS: 5,
    ChartPeriodWindow.TEN_YEARS: 10,
    ChartPeriodWindow.MAX: None,
}


def _filter_time_series_by_period_window(
    time_series: list[_TimeSeriesPoint],
    period_window: ChartPeriodWindow,
) -> list[_TimeSeriesPoint]:
    """Drop points older than N years before the latest period (or keep all for Max)."""
    if not time_series:
        return []
    years = _PERIOD_WINDOW_YEARS[period_window]
    if years is None:
        return time_series
    max_period = max(point.period for point in time_series)
    # Approximate year cutoff: same month/day N years earlier
    try:
        cutoff = max_period.replace(year=max_period.year - years)
    except ValueError:
        # Feb 29 → Feb 28
        cutoff = max_period.replace(month=2, day=28, year=max_period.year - years)
    return [point for point in time_series if point.period >= cutoff]


class _SelectedIndicatorAndMode(TypedDict):
    """One selected indicator type with its Abs/QoQ/YoY mode and optional country."""

    type: str  # Indicator type display label from the UI
    mode: IndicatorDisplayModeChoices
    location: EconomicDataLocationChoices | None


class _SelectedIndicatorAndModeWithLocation(NamedTuple):
    """Selected indicator+mode with the concrete location whose series to load."""

    selected_indicator_and_mode: _SelectedIndicatorAndMode
    location: EconomicDataLocationChoices


class _IndicatorLocationTypeKey(NamedTuple):
    """Lookup key for an indicator row by location code and type."""

    location: str
    type: str


def _parse_selected_indicator_and_mode(raw: str) -> _SelectedIndicatorAndMode:
    """Parse ``[Location|]Type[|MODE]`` into type, mode, and optional location."""
    text = (raw or "").strip()
    if not text:
        return _SelectedIndicatorAndMode(
            type="", mode=IndicatorDisplayModeChoices.RAW, location=None
        )

    tokens = [token.strip() for token in text.split("|") if token.strip()]
    location_values = {choice.value for choice in EconomicDataLocationChoices}
    mode_values = {mode.value for mode in IndicatorDisplayModeChoices}

    location: EconomicDataLocationChoices | None = None
    if tokens and tokens[0] in location_values:
        location = EconomicDataLocationChoices(tokens.pop(0))

    mode = IndicatorDisplayModeChoices.RAW
    if tokens and tokens[-1] in mode_values:
        mode = IndicatorDisplayModeChoices(tokens.pop(-1))

    if len(tokens) != 1:
        raise ValueError(f"Invalid indicator selection: {raw}")
    return _SelectedIndicatorAndMode(type=tokens[0], mode=mode, location=location)


class _ChartDataPoint(TypedDict):
    """Chart data point."""

    period: str  # Display period label for the chart axis
    data_value: float
    indicator_name: str  # Series legend / indicator display label


class _EconomicChartsData(TypedDict):
    """Economic charts data."""

    category: str  # Display label (Choices.label)
    category_data: list[_ChartDataPoint]
    value_axis_label: (
        str  # Y-axis title, e.g. "Data Value (%)" / "Data Value (in bUSD)"
    )


_CHARTS_CACHE_ADAPTER = TypeAdapter(list[_EconomicChartsData])


def _build_charts_cache_fingerprint(
    location: EconomicDataLocationChoices,
    selected_indicators_by_category: list[_SelectedIndicatorsByCategory],
    period_window: ChartPeriodWindow,
) -> str:
    """Stable fingerprint for region / selections / period window."""
    selection_parts: list[str] = []
    for selection in selected_indicators_by_category:
        category_value = (
            selection["category"].value
            if isinstance(selection["category"], EconomicDataCategoryChoices)
            else str(selection["category"])
        )
        indicators = ",".join(selection.get("selected_indicators", []))
        selection_parts.append(f"{category_value}:{indicators}")
    selection_parts.sort()
    return f"{location.value}|{period_window.value}|{'|'.join(selection_parts)}"


def _format_period(
    period_date: date, frequency: EconomicPublicationFrequencyChoices
) -> str:
    """Format period based on frequency."""
    if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
        return period_date.strftime("%Y-%m")
    if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
        quarter = (period_date.month - 1) // 3 + 1
        return f"{period_date.year}Q{quarter}"
    if frequency == EconomicPublicationFrequencyChoices.ANNUAL:
        return str(period_date.year)
    return period_date.isoformat()


def _build_series_label(
    indicator: EconomicIndicatorInformationModel,
    mode: IndicatorDisplayModeChoices,
    *,
    include_location: bool = False,
) -> str:
    """Series legend label.

    Abs → documented base_unit paren from INDICATORS.md (base year / in M / …).
    QoQ / QoQy / YoY → always ``(in %)`` (transformed growth rates), never abs unit.
    When ``include_location`` is true, prefix with the country display label so
    multi-country series stay distinct.
    """
    if mode == IndicatorDisplayModeChoices.RAW:
        base_label = indicator.get_display_name()
    else:
        base_label = f"{indicator.type} (in %)"
    if not include_location:
        return base_label
    location_label = str(EconomicDataLocationChoices(indicator.location).label)
    return f"{location_label} — {base_label}"


def _attach_series_locations_to_selected_indicators_and_modes(
    region: EconomicDataLocationChoices,
    selected_indicators_and_modes: list[_SelectedIndicatorAndMode],
) -> list[_SelectedIndicatorAndModeWithLocation]:
    """Resolve the DB location to load for each selected indicator+mode.

    Uses the country on the selection when present; otherwise the page region.
    Europe requires an explicit country — selections without one are dropped.
    """
    with_locations: list[_SelectedIndicatorAndModeWithLocation] = []
    for selected_indicator_and_mode in selected_indicators_and_modes:
        series_location = selected_indicator_and_mode["location"]
        if series_location is None:
            if region == EconomicDataLocationChoices.EU:
                continue
            series_location = region
        with_locations.append(
            _SelectedIndicatorAndModeWithLocation(
                selected_indicator_and_mode=selected_indicator_and_mode,
                location=series_location,
            )
        )
    return with_locations


def _get_time_series_by_indicator_name(
    indicators: list[EconomicIndicatorInformationModel],
) -> dict[str, list[_TimeSeriesPoint]]:
    """Fetch raw absolute time series from the DB, keyed by indicator name."""
    # Usage of dict: keys are runtime indicator names from the DB query.
    time_series_by_indicator_name: dict[str, list[_TimeSeriesPoint]] = {
        indicator.name: [] for indicator in indicators
    }
    if not indicators:
        return time_series_by_indicator_name

    for data_row in economic_data.get_economic_data(
        indicator_names=[indicator.name for indicator in indicators]
    ):
        if data_row.period is None or data_row.data_value is None:
            continue
        indicator_name = data_row.indicator.name
        if indicator_name in time_series_by_indicator_name:
            time_series_by_indicator_name[indicator_name].append(
                _TimeSeriesPoint(
                    period=data_row.period, value=float(data_row.data_value)
                )
            )
    return time_series_by_indicator_name


class _CategoryChartSeries(NamedTuple):
    """Chart points plus the shared y-axis label for one category."""

    category_data: list[_ChartDataPoint]
    value_axis_label: str


def _build_value_axis_label(
    *,
    mode: IndicatorDisplayModeChoices | str,
    base_unit: str = "",
    base_currency: str = "",
) -> str:
    """Y-axis title for one economic-chart series."""
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    if (
        mode_value != IndicatorDisplayModeChoices.RAW
        or base_unit == IndicatorBaseUnitChoices.PERCENT
    ):
        return "Data Value (%)"
    if base_unit == IndicatorBaseUnitChoices.INDEX:
        return "Data Value"
    if base_unit in {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }:
        magnitude = IndicatorAmountMagnitudeChoices(base_unit)
        currency = (
            IndicatorBaseCurrencyChoices(base_currency) if base_currency else None
        )
        unit_label = (
            magnitude.value.lower()
            if currency is None
            else f"{magnitude.value.lower()}{currency.value}"
        )
        return f"Data Value (in {unit_label})"
    return "Data Value"


def _resolve_value_axis_label(
    axis_labels: list[str],
) -> str:
    """Use a shared axis title when all series agree; otherwise ``Data Value``."""
    unique_labels = list(dict.fromkeys(axis_labels))
    if len(unique_labels) == 1:
        return unique_labels[0]
    return "Data Value"


def _build_category_data_points(
    detailed_selection: list[_SelectedIndicatorAndModeWithLocation],
    indicator_by_location_type: dict[
        _IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ],
    time_series_by_indicator_name: dict[str, list[_TimeSeriesPoint]],
    period_window: ChartPeriodWindow,
) -> _CategoryChartSeries:
    """Change series mode, filter by period window, then format chart data points."""
    category_data: list[_ChartDataPoint] = []
    axis_labels: list[str] = []
    for item in detailed_selection:
        selected_indicator_and_mode = item.selected_indicator_and_mode
        indicator = indicator_by_location_type.get(
            _IndicatorLocationTypeKey(
                location=item.location.value,
                type=selected_indicator_and_mode["type"],
            )
        )
        if indicator is None:
            continue
        frequency = EconomicPublicationFrequencyChoices(indicator.frequency)
        mode = selected_indicator_and_mode["mode"]
        axis_labels.append(
            _build_value_axis_label(
                mode=mode,
                base_unit=indicator.base_unit,
                base_currency=indicator.base_currency,
            )
        )
        time_series_in_period_window = _filter_time_series_by_period_window(
            _change_series_mode(
                time_series_by_indicator_name.get(indicator.name, []),
                frequency,
                mode,
            ),
            period_window,
        )
        series_label = _build_series_label(
            indicator,
            mode,
            include_location=len({entry.location for entry in detailed_selection}) > 1,
        )
        for point in time_series_in_period_window:
            category_data.append(
                _ChartDataPoint(
                    period=_format_period(point.period, frequency),
                    data_value=point.value,
                    indicator_name=series_label,
                )
            )
    category_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return _CategoryChartSeries(
        category_data=category_data,
        value_axis_label=_resolve_value_axis_label(axis_labels),
    )


def _build_chart_data_for_one_category(
    category: EconomicDataCategoryChoices,
    region: EconomicDataLocationChoices,
    selected_raw: list[str],
    period_window: ChartPeriodWindow,
) -> _EconomicChartsData:
    """Build chart series payload for one category."""
    empty = _EconomicChartsData(
        category=str(category.label),
        category_data=[],
        value_axis_label="Data Value",
    )
    selected_indicators_and_modes: list[_SelectedIndicatorAndMode] = []
    for raw in selected_raw:
        parsed = _parse_selected_indicator_and_mode(raw)
        if parsed["type"]:
            selected_indicators_and_modes.append(parsed)
    if not selected_indicators_and_modes:
        return empty

    detailed_selection = _attach_series_locations_to_selected_indicators_and_modes(
        region, selected_indicators_and_modes
    )
    indicators = list(
        EconomicIndicatorInformationModel.objects.filter(
            category=category.value,
            location__in={item.location.value for item in detailed_selection},
            type__in={
                item.selected_indicator_and_mode["type"] for item in detailed_selection
            },
        )
    )
    if not indicators:
        return empty

    # Usage of dict: keys are runtime location×type pairs from the DB query.
    indicator_by_location_type: dict[
        _IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ] = {
        _IndicatorLocationTypeKey(
            location=indicator.location, type=indicator.type
        ): indicator
        for indicator in indicators
    }
    series = _build_category_data_points(
        detailed_selection,
        indicator_by_location_type,
        _get_time_series_by_indicator_name(indicators),
        period_window,
    )
    return _EconomicChartsData(
        category=str(category.label),
        category_data=series.category_data,
        value_axis_label=series.value_axis_label,
    )


def _build_economic_charts_data(
    location: EconomicDataLocationChoices,
    selected_indicators_by_category: list[_SelectedIndicatorsByCategory],
    period_window: ChartPeriodWindow,
) -> list[_EconomicChartsData]:
    """Build chart series payloads for all categories."""
    # Usage of dict: keys are chart categories from the request selections.
    selected_raw_by_category: dict[EconomicDataCategoryChoices, list[str]] = {
        selection["category"]: selection.get("selected_indicators", [])
        for selection in selected_indicators_by_category
    }
    return [
        _build_chart_data_for_one_category(
            category,
            location,
            selected_raw_by_category.get(category, []),
            period_window,
        )
        for category in EconomicDataCategoryChoices.ordered()
    ]


def get_economic_charts_data(
    location: EconomicDataLocationChoices,
    selected_indicators_by_category: list[_SelectedIndicatorsByCategory] = [],
    period_window: ChartPeriodWindow = ChartPeriodWindow.FIVE_YEARS,
) -> list[_EconomicChartsData]:
    """Get economic charts data for all categories.

    Europe plots each explicitly selected country×type curve. Abs / QoQ / YoY
    transforms are Redis-cached (versioned by table state).
    """
    fingerprint = _build_charts_cache_fingerprint(
        location, selected_indicators_by_category, period_window
    )
    cached = get_cached_economic_display(
        EconomicDisplayCacheType.CHARTS, fingerprint, _CHARTS_CACHE_ADAPTER
    )
    if cached is not None:
        return cached

    all_data = _build_economic_charts_data(
        location, selected_indicators_by_category, period_window
    )
    set_cached_economic_display(EconomicDisplayCacheType.CHARTS, fingerprint, all_data)
    return all_data
