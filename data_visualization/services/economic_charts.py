"""Build economic chart series payloads for the visualization UI."""

from datetime import date
from enum import Enum
from typing import NamedTuple, TypedDict

from pydantic import TypeAdapter

import economic_overview.services.economic_data as economic_data
from core.services import ValueChangeOutput, calculate_value_change
from data_visualization.services.cache import (
    EconomicDisplayCacheType,
    get_cached_economic_display,
    set_cached_economic_display,
)
from data_visualization.services.config import (
    ECONOMIC_CHARTS_EU_COUNTRIES,
    ECONOMIC_CHARTS_LOCATIONS,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


class ChartSeriesMode(str, Enum):
    """Series transform mode for economic charts / recap display."""

    ABS = "ABS"
    QOQ = "QOQ"
    QOQY = "QOQY"  # Annualized QoQ (display label: QoQy)
    YOY = "YOY"


class EconomicChartsCategoryDefaults(TypedDict):
    """Per-category default selection strings (no region prefix)."""

    growth_indicator: str
    inflation_indicator: str
    government_indicator: str
    production_indicator: str
    sales_indicator: str
    labour_indicator: str
    housing_indicator: str
    confidence_indicator: str


def encode_indicator_selection(
    indicator_type: str,
    mode: ChartSeriesMode,
    location: EconomicDataLocationChoices | None = None,
) -> str:
    """Encode a chart selection for form / URL values.

    Single-region: ``Type|MODE``. Europe curves: ``Location|Type|MODE``.
    """
    if location is None:
        return f"{indicator_type}|{mode.value}"
    return f"{location.value}|{indicator_type}|{mode.value}"


def _encode_eu_default_curves(indicator_type: str, mode: ChartSeriesMode) -> str:
    """Comma-join DE/ES/IT/FR ``Location|Type|MODE`` defaults for one type."""
    return ",".join(
        encode_indicator_selection(indicator_type, mode, country)
        for country in ECONOMIC_CHARTS_EU_COUNTRIES
    )


def get_default_indicator_selections(
    confidence_type: str | None = None,
) -> EconomicChartsCategoryDefaults:
    """Shared chart category defaults; ``confidence_type`` varies by location.

    Pass ``None`` when the location has no confidence series (e.g. Europe default).
    """
    return EconomicChartsCategoryDefaults(
        growth_indicator=encode_indicator_selection("GDP", ChartSeriesMode.YOY),
        inflation_indicator=encode_indicator_selection(
            "Consumer Price Index", ChartSeriesMode.YOY
        ),
        government_indicator=encode_indicator_selection(
            "Government Debt (% of GDP)", ChartSeriesMode.ABS
        ),
        production_indicator=encode_indicator_selection(
            "Industrial Production", ChartSeriesMode.ABS
        ),
        sales_indicator=encode_indicator_selection("Retail Sales", ChartSeriesMode.YOY),
        labour_indicator=encode_indicator_selection(
            "Unemployment Rate", ChartSeriesMode.ABS
        ),
        housing_indicator=encode_indicator_selection(
            "Home Prices", ChartSeriesMode.ABS
        ),
        confidence_indicator=(
            encode_indicator_selection(confidence_type, ChartSeriesMode.ABS)
            if confidence_type
            else ""
        ),
    )


def get_default_eu_indicator_selections() -> EconomicChartsCategoryDefaults:
    """Europe defaults: DE / ES / IT / FR curves per category."""
    return EconomicChartsCategoryDefaults(
        growth_indicator=_encode_eu_default_curves("GDP", ChartSeriesMode.YOY),
        inflation_indicator=_encode_eu_default_curves(
            "Consumer Price Index", ChartSeriesMode.YOY
        ),
        government_indicator=_encode_eu_default_curves(
            "Government Debt (% of GDP)", ChartSeriesMode.ABS
        ),
        production_indicator=_encode_eu_default_curves(
            "Industrial Production", ChartSeriesMode.ABS
        ),
        sales_indicator=_encode_eu_default_curves("Retail Sales", ChartSeriesMode.YOY),
        labour_indicator=_encode_eu_default_curves(
            "Unemployment Rate", ChartSeriesMode.ABS
        ),
        housing_indicator=_encode_eu_default_curves("Home Prices", ChartSeriesMode.ABS),
        confidence_indicator="",
    )


class ChartIndicatorOption(TypedDict):
    """One selectable series in the charts multiselect."""

    type: str  # Series key: ``GDP`` or ``DE|GDP``
    name: str  # Display label


class IndicatorsByCategory(TypedDict):
    """Indicators by category for economic charts dropdown."""

    category: str  # Display label (Choices.label)
    indicators: list[ChartIndicatorOption]


class EconomicChartsDropdownValues(TypedDict):
    """Dropdown values for economic charts."""

    locations: list[str]  # Display labels (Choices.label)
    categories: list[str]  # Display labels (Choices.label)
    indicators_by_category: list[IndicatorsByCategory]


def get_economic_charts_dropdown_values(
    location: EconomicDataLocationChoices,
) -> EconomicChartsDropdownValues:
    """Get dropdown values for economic charts."""
    categories = EconomicDataCategoryChoices.get_labels()
    locations = [str(loc.label) for loc in ECONOMIC_CHARTS_LOCATIONS]

    indicators_by_category: list[IndicatorsByCategory] = []
    for category in EconomicDataCategoryChoices.ordered():
        if location == EconomicDataLocationChoices.EU:
            options: list[ChartIndicatorOption] = []
            for country in ECONOMIC_CHARTS_EU_COUNTRIES:
                category_indicators = EconomicIndicatorInformationModel.objects.filter(
                    category=category.value,
                    location=country.value,
                ).order_by("id")
                for indicator in category_indicators:
                    options.append(
                        ChartIndicatorOption(
                            type=f"{country.value}|{indicator.type}",
                            name=f"{country.label} — {indicator.type}",
                        )
                    )
            indicators_by_category.append(
                IndicatorsByCategory(category=str(category.label), indicators=options)
            )
        else:
            category_indicators = EconomicIndicatorInformationModel.objects.filter(
                category=category.value, location=location.value
            ).order_by("id")
            indicators_by_category.append(
                IndicatorsByCategory(
                    category=str(category.label),
                    indicators=[
                        ChartIndicatorOption(type=indicator.type, name=indicator.type)
                        for indicator in category_indicators
                    ],
                )
            )
    return EconomicChartsDropdownValues(
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


class SelectedIndicatorsByCategory(TypedDict):
    """Selected Indicators by Category"""

    category: EconomicDataCategoryChoices
    selected_indicators: list[str]  # UI Type or Type|MODE display strings


def get_selected_indicators_by_category(
    location: EconomicDataLocationChoices,
    front_data: EconomicChartsFrontData,
) -> list[SelectedIndicatorsByCategory]:
    """Get selected indicators and reorganize by category."""
    selected_indicators_by_category = []
    for category in EconomicDataCategoryChoices.ordered():
        key = f"{location.value.lower()}_{category.lower()}_indicator"
        raw_value = front_data.get(key, "")
        selected_indicators = [
            indicator.strip() for indicator in raw_value.split(",") if indicator.strip()
        ]
        selected_indicators_by_category.append(
            SelectedIndicatorsByCategory(
                category=category,
                selected_indicators=selected_indicators,
            )
        )
    return selected_indicators_by_category


class TimeSeriesPoint(NamedTuple):
    """One period/value observation (raw absolute or after Abs/QoQ/QoQy/YoY)."""

    period: date
    value: float


def _get_lag_for_mode(
    frequency: EconomicPublicationFrequencyChoices, mode: ChartSeriesMode
) -> int:
    """Points to look back for QoQ / QoQy / YoY given publication frequency."""
    if mode == ChartSeriesMode.ABS:
        return 0
    if mode in (ChartSeriesMode.QOQ, ChartSeriesMode.QOQY):
        if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
            return 3
        if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
            return 1
        return 1  # ANNUAL: QoQ / QoQy treated as YoY lag
    # YOY
    if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
        return 12
    if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
        return 4
    return 1


def _change_series_mode(
    points: list[TimeSeriesPoint],
    frequency: EconomicPublicationFrequencyChoices,
    mode: ChartSeriesMode,
) -> list[TimeSeriesPoint]:
    """Change a raw absolute time series to Abs / QoQ / QoQy / YoY mode."""
    if not points:
        return []
    ordered = sorted(points, key=lambda item: item.period)
    if mode == ChartSeriesMode.ABS:
        return ordered

    lag = _get_lag_for_mode(frequency, mode)
    result: list[TimeSeriesPoint] = []
    for index in range(lag, len(ordered)):
        curr = ordered[index]
        prev = ordered[index - lag]
        change = calculate_value_change(
            curr.value,
            prev.value,
            (
                ValueChangeOutput.ANNUALIZED_PERCENT
                if mode == ChartSeriesMode.QOQY
                else ValueChangeOutput.PERCENT
            ),
            annualized_ratio=4 if mode == ChartSeriesMode.QOQY else None,
        )
        if change is None:
            continue
        result.append(TimeSeriesPoint(period=curr.period, value=change))
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
    time_series: list[TimeSeriesPoint],
    period_window: ChartPeriodWindow,
) -> list[TimeSeriesPoint]:
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


class SelectedIndicatorAndMode(TypedDict):
    """One selected indicator type with its Abs/QoQ/YoY mode and optional country."""

    type: str  # Indicator type display label from the UI
    mode: ChartSeriesMode
    location: EconomicDataLocationChoices | None


class SelectedIndicatorAndModeWithLocation(NamedTuple):
    """Selected indicator+mode with the concrete location whose series to load."""

    selected_indicator_and_mode: SelectedIndicatorAndMode
    location: EconomicDataLocationChoices


class IndicatorLocationTypeKey(NamedTuple):
    """Lookup key for an indicator row by location code and type."""

    location: str
    type: str


def _parse_selected_indicator_and_mode(raw: str) -> SelectedIndicatorAndMode:
    """Parse ``[Location|]Type[|MODE]`` into type, mode, and optional location."""
    text = (raw or "").strip()
    if not text:
        return SelectedIndicatorAndMode(
            type="", mode=ChartSeriesMode.ABS, location=None
        )

    tokens = [token.strip() for token in text.split("|") if token.strip()]
    location_values = {choice.value for choice in EconomicDataLocationChoices}
    mode_values = {mode.value for mode in ChartSeriesMode}

    location: EconomicDataLocationChoices | None = None
    if tokens and tokens[0] in location_values:
        location = EconomicDataLocationChoices(tokens.pop(0))

    mode = ChartSeriesMode.ABS
    if tokens and tokens[-1].upper() in mode_values:
        mode = ChartSeriesMode(tokens.pop(-1).upper())

    if len(tokens) != 1:
        raise ValueError(f"Invalid indicator selection: {raw}")
    return SelectedIndicatorAndMode(type=tokens[0], mode=mode, location=location)


class ChartDataPoint(TypedDict):
    """Chart data point."""

    period: str  # Display period label for the chart axis
    data_value: float
    indicator_name: str  # Series legend / indicator display label


class EconomicChartsData(TypedDict):
    """Economic charts data."""

    category: str  # Display label (Choices.label)
    category_data: list[ChartDataPoint]


_CHARTS_CACHE_ADAPTER = TypeAdapter(list[EconomicChartsData])


def _build_charts_cache_fingerprint(
    location: EconomicDataLocationChoices,
    selected_indicators_by_category: list[SelectedIndicatorsByCategory],
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
    mode: ChartSeriesMode,
    *,
    include_location: bool = False,
) -> str:
    """Series legend label.

    Abs → documented base_unit paren from INDICATORS.md (base year / in M / …).
    QoQ / QoQy / YoY → always ``(in %)`` (transformed growth rates), never abs unit.
    When ``include_location`` is true, prefix with the country display label so
    multi-country series stay distinct.
    """
    if mode == ChartSeriesMode.ABS:
        base_label = indicator.display_name()
    else:
        base_label = f"{indicator.type} (in %)"
    if not include_location:
        return base_label
    location_label = str(EconomicDataLocationChoices(indicator.location).label)
    return f"{location_label} — {base_label}"


def _attach_series_locations_to_selected_indicators_and_modes(
    region: EconomicDataLocationChoices,
    selected_indicators_and_modes: list[SelectedIndicatorAndMode],
) -> list[SelectedIndicatorAndModeWithLocation]:
    """Resolve the DB location to load for each selected indicator+mode.

    Uses the country on the selection when present; otherwise the page region.
    Europe requires an explicit country — selections without one are dropped.
    """
    with_locations: list[SelectedIndicatorAndModeWithLocation] = []
    for selected_indicator_and_mode in selected_indicators_and_modes:
        series_location = selected_indicator_and_mode["location"]
        if series_location is None:
            if region == EconomicDataLocationChoices.EU:
                continue
            series_location = region
        with_locations.append(
            SelectedIndicatorAndModeWithLocation(
                selected_indicator_and_mode=selected_indicator_and_mode,
                location=series_location,
            )
        )
    return with_locations


def _get_time_series_by_indicator_name(
    indicators: list[EconomicIndicatorInformationModel],
) -> dict[str, list[TimeSeriesPoint]]:
    """Fetch raw absolute time series from the DB, keyed by indicator name."""
    # Usage of dict: keys are runtime indicator names from the DB query.
    time_series_by_indicator_name: dict[str, list[TimeSeriesPoint]] = {
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
                TimeSeriesPoint(
                    period=data_row.period, value=float(data_row.data_value)
                )
            )
    return time_series_by_indicator_name


def _build_category_data_points(
    detailed_selection: list[SelectedIndicatorAndModeWithLocation],
    indicator_by_location_type: dict[
        IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ],
    time_series_by_indicator_name: dict[str, list[TimeSeriesPoint]],
    period_window: ChartPeriodWindow,
) -> list[ChartDataPoint]:
    """Change series mode, filter by period window, then format chart data points."""
    category_data: list[ChartDataPoint] = []
    for item in detailed_selection:
        selected_indicator_and_mode = item.selected_indicator_and_mode
        indicator = indicator_by_location_type.get(
            IndicatorLocationTypeKey(
                location=item.location.value,
                type=selected_indicator_and_mode["type"],
            )
        )
        if indicator is None:
            continue
        frequency = EconomicPublicationFrequencyChoices(indicator.frequency)
        time_series_in_period_window = _filter_time_series_by_period_window(
            _change_series_mode(
                time_series_by_indicator_name.get(indicator.name, []),
                frequency,
                selected_indicator_and_mode["mode"],
            ),
            period_window,
        )
        series_label = _build_series_label(
            indicator,
            selected_indicator_and_mode["mode"],
            include_location=len({entry.location for entry in detailed_selection}) > 1,
        )
        for point in time_series_in_period_window:
            category_data.append(
                ChartDataPoint(
                    period=_format_period(point.period, frequency),
                    data_value=point.value,
                    indicator_name=series_label,
                )
            )
    category_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return category_data


def _build_chart_data_for_one_category(
    category: EconomicDataCategoryChoices,
    region: EconomicDataLocationChoices,
    selected_raw: list[str],
    period_window: ChartPeriodWindow,
) -> EconomicChartsData:
    """Build chart series payload for one category."""
    empty = EconomicChartsData(category=str(category.label), category_data=[])
    selected_indicators_and_modes: list[SelectedIndicatorAndMode] = []
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
        IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ] = {
        IndicatorLocationTypeKey(
            location=indicator.location, type=indicator.type
        ): indicator
        for indicator in indicators
    }
    return EconomicChartsData(
        category=str(category.label),
        category_data=_build_category_data_points(
            detailed_selection,
            indicator_by_location_type,
            _get_time_series_by_indicator_name(indicators),
            period_window,
        ),
    )


def _build_economic_charts_data(
    location: EconomicDataLocationChoices,
    selected_indicators_by_category: list[SelectedIndicatorsByCategory],
    period_window: ChartPeriodWindow,
) -> list[EconomicChartsData]:
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
    selected_indicators_by_category: list[SelectedIndicatorsByCategory] = [],
    period_window: ChartPeriodWindow = ChartPeriodWindow.FIVE_YEARS,
) -> list[EconomicChartsData]:
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
