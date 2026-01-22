from datetime import date
from typing import List, TypedDict

import economic_overview.services.economic_data_services as economic_data_services
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicIndicatorInformationModel,
)


class IndicatorsByCategory(TypedDict):
    """Indicators by category for economic charts dropdown."""

    category: str
    indicators: List[str]


class EconomicChartsDropdownValues(TypedDict):
    """Dropdown values for economic charts."""

    locations: List[str]
    categories: List[str]
    indicators_by_category: List[IndicatorsByCategory]


def get_economic_charts_dropdown_values(
    location: str,
) -> EconomicChartsDropdownValues:
    """Get dropdown values for economic charts."""
    location_value = location
    for loc in EconomicDataLocationChoices.ordered():
        if str(loc.label) == location or loc.value == location:
            location_value = loc.value
            break

    categories = [
        str(category.label) for category in EconomicDataCategoryChoices.ordered()
    ]
    locations = [str(loc.label) for loc in EconomicDataLocationChoices.ordered()]

    indicators_by_category = []
    for category in EconomicDataCategoryChoices.ordered():
        category_indicators = EconomicIndicatorInformationModel.objects.filter(
            category=category.value, location=location_value
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
    """Front data."""

    zone: str
    us_growth_indicator: str
    us_inflation_indicator: str
    us_government_indicator: str
    us_labour_indicator: str
    us_housing_indicator: str
    us_production_indicator: str
    us_confidence_indicator: str
    us_sales_indicator: str
    fr_growth_indicator: str
    fr_inflation_indicator: str
    fr_government_indicator: str
    fr_labour_indicator: str
    fr_housing_indicator: str
    fr_production_indicator: str
    fr_confidence_indicator: str
    fr_sales_indicator: str
    jp_growth_indicator: str
    jp_inflation_indicator: str
    jp_government_indicator: str
    jp_labour_indicator: str
    jp_housing_indicator: str
    jp_production_indicator: str
    jp_confidence_indicator: str
    jp_sales_indicator: str


class SelectedIndicatorsByCategory(TypedDict):
    """Selected Indicators by Category"""

    category: EconomicDataCategoryChoices
    selected_indicators: List[str]


def get_selected_indicators_by_category(
    zone: str,
    front_data: EconomicChartsFrontData,
) -> List[SelectedIndicatorsByCategory]:
    """Get selected indicators and reorganize by category."""
    zone_value = zone.lower()
    for location in EconomicDataLocationChoices.ordered():
        if str(location.label) == zone:
            zone_value = location.value.lower()
            break

    selected_indicators_by_category = []
    for category in EconomicDataCategoryChoices.ordered():
        key = f"{zone_value}_{category.lower()}_indicator"
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


def _format_period(period_date: date, frequency: str) -> str:
    """Format period based on frequency."""
    if frequency == "MONTHLY":
        return period_date.strftime("%Y-%m")
    elif frequency == "QUARTERLY":
        quarter = (period_date.month - 1) // 3 + 1
        return f"{period_date.year}Q{quarter}"
    elif frequency == "ANNUAL":
        return str(period_date.year)
    return period_date.isoformat()


class ChartDataPoint(TypedDict):
    """Chart data point."""

    period: str
    data_value: float
    indicator_name: str


class EconomicChartsData(TypedDict):
    """Economic charts data."""

    category: str
    category_data: List[ChartDataPoint]


def get_economic_charts_data(
    location: str,
    selected_indicators_by_category: List[SelectedIndicatorsByCategory] = [],
) -> List[EconomicChartsData]:
    """Get economic charts data for all categories."""
    location_value = location
    for loc in EconomicDataLocationChoices.ordered():
        if str(loc.label) == location or loc.value == location:
            location_value = loc.value
            break

    all_data = []
    for category in EconomicDataCategoryChoices.ordered():
        indicators = EconomicIndicatorInformationModel.objects.filter(
            category=category.value, location=location_value
        )
        selected_indicators = []
        for selection in selected_indicators_by_category:
            if selection.get("category") == category:
                selected_indicators = selection.get("selected_indicators", [])
                break

        if not selected_indicators:
            all_data.append(
                EconomicChartsData(category=str(category.label), category_data=[])
            )
            continue

        indicators = indicators.filter(type__in=selected_indicators)
        indicator_names = [indicator.name for indicator in indicators]
        if not indicator_names:
            all_data.append(
                EconomicChartsData(category=str(category.label), category_data=[])
            )
            continue

        economic_data = economic_data_services.get_economic_data(
            indicator_names=indicator_names
        )

        category_data = []
        for data in economic_data:
            if data.period and data.data_value is not None:
                period_str = _format_period(data.period, data.indicator.frequency)
                category_data.append(
                    {
                        "period": period_str,
                        "data_value": float(data.data_value),
                        "indicator_name": data.indicator.type,
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
