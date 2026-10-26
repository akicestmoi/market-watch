"""Build economic chart series payloads for the visualization UI."""

from datetime import date
from enum import Enum
from typing import NamedTuple, TypedDict

import economic_overview.services.economic_data as economic_data
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


class ChartSeriesMode(str, Enum):
    """Series transform mode for economic charts."""

    ABS = "ABS"
    QOQ = "QOQ"
    YOY = "YOY"


def encode_indicator_selection(indicator_type: str, mode: ChartSeriesMode) -> str:
    """Encode type + mode as Type|MODE for chart form / URL selection values."""
    if mode == ChartSeriesMode.ABS:
        return f"{indicator_type}|{ChartSeriesMode.ABS.value}"
    return f"{indicator_type}|{mode.value}"


class IndicatorsByCategory(TypedDict):
    """Indicators by category for economic charts dropdown."""

    category: str  # Display label (Choices.label)
    indicators: list[str]  # Indicator type display labels


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
    locations = EconomicDataLocationChoices.get_labels()

    indicators_by_category = []
    for category in EconomicDataCategoryChoices.ordered():
        category_indicators = EconomicIndicatorInformationModel.objects.filter(
            category=category.value, location=location.value
        ).order_by("id")
        indicators_by_category.append(
            {
                "category": str(category.label),
                "indicators": [indicator.type for indicator in category_indicators],
            }
        )
    return EconomicChartsDropdownValues(
        categories=categories,
        locations=locations,
        indicators_by_category=indicators_by_category,
    )


class EconomicChartsFrontData(TypedDict):
    """Front data from the charts form (GET query / selected_values JSON)."""

    zone: str  # Display label (Choices.label) from the UI
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
    zone_prefix = location.value.lower()
    selected_indicators_by_category = []
    for category in EconomicDataCategoryChoices.ordered():
        key = f"{zone_prefix}_{category.lower()}_indicator"
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


class ChartLevelPoint(NamedTuple):
    """One absolute or transformed chart observation."""

    period: date
    value: float


def _get_lag_for_mode(
    frequency: EconomicPublicationFrequencyChoices, mode: ChartSeriesMode
) -> int:
    """Points to look back for QoQ/YoY given publication frequency."""
    if mode == ChartSeriesMode.ABS:
        return 0
    if mode == ChartSeriesMode.QOQ:
        if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
            return 3
        if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
            return 1
        return 1  # ANNUAL: QoQ treated as YoY
    # YOY
    if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
        return 12
    if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
        return 4
    return 1


def _compute_pct_change(curr: float, prev: float) -> float | None:
    """Return percent change from ``prev`` to ``curr``, or None if undefined."""
    if prev == 0:
        return None
    return (curr - prev) / prev * 100


def _transform_level_series(
    points: list[ChartLevelPoint],
    frequency: EconomicPublicationFrequencyChoices,
    mode: ChartSeriesMode,
) -> list[ChartLevelPoint]:
    """Transform absolute level points into Abs/QoQ/YoY series."""
    if not points:
        return []
    ordered = sorted(points, key=lambda item: item.period)
    if mode == ChartSeriesMode.ABS:
        return ordered

    lag = _get_lag_for_mode(frequency, mode)
    result: list[ChartLevelPoint] = []
    for index in range(lag, len(ordered)):
        curr = ordered[index]
        prev = ordered[index - lag]
        change = _compute_pct_change(curr.value, prev.value)
        if change is None:
            continue
        result.append(ChartLevelPoint(period=curr.period, value=change))
    return result


class ChartPeriodWindow(str, Enum):
    """Shared chart history window presets."""

    ONE_YEAR = "1Y"
    THREE_YEARS = "3Y"
    FIVE_YEARS = "5Y"
    TEN_YEARS = "10Y"
    MAX = "Max"


_PERIOD_WINDOW_YEARS: dict[ChartPeriodWindow, int | None] = {
    ChartPeriodWindow.ONE_YEAR: 1,
    ChartPeriodWindow.THREE_YEARS: 3,
    ChartPeriodWindow.FIVE_YEARS: 5,
    ChartPeriodWindow.TEN_YEARS: 10,
    ChartPeriodWindow.MAX: None,
}


def _apply_period_window(
    points: list[ChartLevelPoint],
    period_window: ChartPeriodWindow,
) -> list[ChartLevelPoint]:
    """Keep points within N years of the latest period (or all for Max)."""
    if not points:
        return []
    years = _PERIOD_WINDOW_YEARS.get(period_window, 10)
    if years is None:
        return points
    max_period = max(point.period for point in points)
    # Approximate year cutoff: same month/day N years earlier
    try:
        cutoff = max_period.replace(year=max_period.year - years)
    except ValueError:
        # Feb 29 → Feb 28
        cutoff = max_period.replace(month=2, day=28, year=max_period.year - years)
    return [point for point in points if point.period >= cutoff]


class SelectedIndicator(TypedDict):
    """Selected indicator with transform mode."""

    type: str  # Indicator type display label from the UI
    mode: ChartSeriesMode


def _parse_indicator_selection(raw: str) -> SelectedIndicator:
    """Parse `Type` or `Type|MODE` into type + mode (default ABS when no mode)."""
    text = (raw or "").strip()
    if not text:
        return SelectedIndicator(type="", mode=ChartSeriesMode.ABS)
    if "|" in text:
        indicator_type, mode = text.split("|", 1)
        return SelectedIndicator(
            type=indicator_type.strip(),
            mode=ChartSeriesMode(mode.strip().upper()),
        )
    return SelectedIndicator(type=text, mode=ChartSeriesMode.ABS)


class ChartDataPoint(TypedDict):
    """Chart data point."""

    period: str  # Display period label for the chart axis
    data_value: float
    indicator_name: str  # Series legend / indicator display label


class EconomicChartsData(TypedDict):
    """Economic charts data."""

    category: str  # Display label (Choices.label)
    category_data: list[ChartDataPoint]


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
) -> str:
    """Series legend label.

    Abs → documented base_unit paren from INDICATORS.md (base year / in M / …).
    QoQ / YoY → always ``(in %)`` (transformed growth rates), never abs unit.
    """
    if mode == ChartSeriesMode.ABS:
        return indicator.display_name()
    return f"{indicator.type} (in %)"


def get_economic_charts_data(
    location: EconomicDataLocationChoices,
    selected_indicators_by_category: list[SelectedIndicatorsByCategory] = [],
    period_window: ChartPeriodWindow = ChartPeriodWindow.FIVE_YEARS,
) -> list[EconomicChartsData]:
    """Get economic charts data for all categories."""
    all_data = []
    for category in EconomicDataCategoryChoices.ordered():
        indicators = EconomicIndicatorInformationModel.objects.filter(
            category=category.value, location=location.value
        )
        selected_raw: list[str] = []
        for selection in selected_indicators_by_category:
            if selection.get("category") == category:
                selected_raw = selection.get("selected_indicators", [])
                break

        parsed_selections: list[SelectedIndicator] = []
        for raw in selected_raw:
            parsed = _parse_indicator_selection(raw)
            if parsed["type"]:
                parsed_selections.append(parsed)

        if not parsed_selections:
            all_data.append(
                EconomicChartsData(category=str(category.label), category_data=[])
            )
            continue

        selected_types = [item["type"] for item in parsed_selections]
        indicators = indicators.filter(type__in=selected_types)
        indicator_by_type = {indicator.type: indicator for indicator in indicators}
        if not indicator_by_type:
            all_data.append(
                EconomicChartsData(category=str(category.label), category_data=[])
            )
            continue

        economic_data_rows = economic_data.get_economic_data(
            indicator_names=[ind.name for ind in indicator_by_type.values()]
        )

        levels_by_type: dict[str, list[ChartLevelPoint]] = {
            type_name: [] for type_name in indicator_by_type
        }
        for data in economic_data_rows:
            if data.period is None or data.data_value is None:
                continue
            type_name = data.indicator.type
            if type_name in levels_by_type:
                levels_by_type[type_name].append(
                    ChartLevelPoint(period=data.period, value=float(data.data_value))
                )

        category_data: list[ChartDataPoint] = []
        for selection in parsed_selections:
            indicator = indicator_by_type.get(selection["type"])
            if indicator is None:
                continue
            frequency = EconomicPublicationFrequencyChoices(indicator.frequency)
            transformed = _transform_level_series(
                levels_by_type.get(selection["type"], []),
                frequency,
                selection["mode"],
            )
            windowed = _apply_period_window(transformed, period_window)
            label = _build_series_label(indicator, selection["mode"])
            for point in windowed:
                category_data.append(
                    {
                        "period": _format_period(point.period, frequency),
                        "data_value": point.value,
                        "indicator_name": label,
                    }
                )

        category_data.sort(
            key=lambda x: (x["period"], x["indicator_name"]), reverse=True
        )
        all_data.append(
            EconomicChartsData(
                category=str(category.label), category_data=category_data
            )
        )

    return all_data
