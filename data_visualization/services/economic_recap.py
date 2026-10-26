"""Build economic recap payloads for the visualization UI."""

from typing import Literal, TypedDict

from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorBaseUnitChoices,
)

# Enough points for YoY on monthly series (12+ lookback + a few for Prev).
_RECAP_HISTORY_LIMIT = 16


class EconomicRecapHistoryPoint(TypedDict):
    """Single history point for on-the-fly Abs/QoQ/YoY transforms."""

    period: str  # Display period label
    period_date: str  # ISO date string for the UI
    value: float


class EconomicRecapItem(TypedDict):
    """Economic recap item."""

    category: EconomicDataCategoryChoices
    location: EconomicDataLocationChoices
    name: str
    display_name: str
    frequency: EconomicPublicationFrequencyChoices
    base_year: int | None
    base_unit: IndicatorBaseUnitChoices | Literal[""]
    current: float | None
    previous: float | None
    change: float | None
    period: str | None  # Display period label
    history: list[EconomicRecapHistoryPoint]


def get_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> dict[str, list[EconomicRecapItem]]:
    """Get economic recap data."""
    indicators = EconomicIndicatorInformationModel.objects.all().order_by("id")
    economic_data: dict[EconomicDataCategoryChoices, list[EconomicRecapItem]] = {}

    for indicator in indicators:
        category = EconomicDataCategoryChoices(indicator.category)
        if category not in economic_data:
            economic_data[category] = []

        for location in locations:
            records = list(
                EconomicDataModel.objects.filter(
                    indicator=indicator,
                    indicator__location=location,
                    data_value__isnull=False,
                    period__isnull=False,
                ).order_by("-period")[:_RECAP_HISTORY_LIMIT]
            )

            curr, prev = (records + [None, None])[:2]
            curr_value = getattr(curr, "data_value", None)
            prev_value = getattr(prev, "data_value", None)
            period = curr.get_period_display() if curr else None
            change = (
                curr_value - prev_value
                if curr_value is not None and prev_value is not None
                else None
            )
            history: list[EconomicRecapHistoryPoint] = [
                {
                    "period": record.get_period_display() or "",
                    "period_date": record.period.isoformat(),
                    "value": float(record.data_value),
                }
                for record in reversed(records)
                if record.period is not None and record.data_value is not None
            ]

            economic_data[category].append(
                EconomicRecapItem(
                    category=category,
                    location=location,
                    name=indicator.type,
                    display_name=indicator.display_name(),
                    frequency=EconomicPublicationFrequencyChoices(indicator.frequency),
                    base_year=indicator.base_year,
                    base_unit=(
                        IndicatorBaseUnitChoices(indicator.base_unit)
                        if indicator.base_unit
                        else ""
                    ),
                    current=curr_value,
                    previous=prev_value,
                    change=change,
                    period=period,
                    history=history,
                )
            )

    # Front table iterates dict insertion order — match category.ordered().
    # JSON keys are category codes (str); TextChoices serialize via default=str.
    ordered_economic_data: dict[str, list[EconomicRecapItem]] = {}
    for category in EconomicDataCategoryChoices.ordered():
        if category in economic_data:
            ordered_economic_data[category.value] = economic_data[category]
    for category_key, items in economic_data.items():
        if category_key.value not in ordered_economic_data:
            ordered_economic_data[category_key.value] = items
    return ordered_economic_data
