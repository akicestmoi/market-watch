"""Build economic recap payloads for the visualization UI."""

from collections import defaultdict
from typing import Literal, NamedTuple, TypedDict

from pydantic import TypeAdapter

from data_visualization.services.cache import (
    EconomicDisplayCacheType,
    get_cached_economic_display,
    set_cached_economic_display,
)
from data_visualization.services.config import TIME_SERIES_HISTORY_WINDOW
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorBaseUnitChoices,
)


class RecapRowKey(NamedTuple):
    """Identity of one aligned recap table row."""

    category: EconomicDataCategoryChoices
    row_name: str


class IndicatorAtLocation(NamedTuple):
    """One indicator contributing a cell on a recap row."""

    location: EconomicDataLocationChoices
    indicator: EconomicIndicatorInformationModel


class RecapRowGrouping(NamedTuple):
    """Indicators grouped by recap row, plus a template indicator per row."""

    # Usage of dict: keys are runtime (category, row_name) pairs from the DB.
    indicators_at_locations_for_row: dict[RecapRowKey, list[IndicatorAtLocation]]
    # Usage of dict: keys are the same row keys; value is the first indicator seen.
    template_indicator_by_row: dict[RecapRowKey, EconomicIndicatorInformationModel]


def _group_indicators_by_recap_row(
    indicators: list[EconomicIndicatorInformationModel],
) -> RecapRowGrouping:
    """Group indicators into cross-location recap rows (shared type or unique name)."""
    # Usage of dict: keys are runtime (type, location) pairs from the DB query.
    type_count_in_location: dict[tuple[str, str], int] = defaultdict(int)
    for indicator in indicators:
        type_count_in_location[(indicator.type, indicator.location)] += 1

    # Usage of dict: keys are runtime row keys from the DB query.
    indicators_at_locations_for_row: dict[RecapRowKey, list[IndicatorAtLocation]] = (
        defaultdict(list)
    )
    template_indicator_by_row: dict[RecapRowKey, EconomicIndicatorInformationModel] = {}
    for indicator in indicators:
        # Shared type across countries when unique in-location; else name (e.g. Tankan).
        row_name = (
            indicator.name
            if type_count_in_location[(indicator.type, indicator.location)] > 1
            else indicator.type
        )
        row_key = RecapRowKey(
            category=EconomicDataCategoryChoices(indicator.category),
            row_name=row_name,
        )
        indicators_at_locations_for_row[row_key].append(
            IndicatorAtLocation(
                location=EconomicDataLocationChoices(indicator.location),
                indicator=indicator,
            )
        )
        template_indicator_by_row.setdefault(row_key, indicator)
    return RecapRowGrouping(
        indicators_at_locations_for_row=indicators_at_locations_for_row,
        template_indicator_by_row=template_indicator_by_row,
    )


def _get_time_series_by_indicator_id(
    indicator_ids: list[int],
) -> dict[
    int, list[EconomicDataModel]
]:  # Usage of dict: keys are runtime indicator PKs.
    """Fetch newest-first absolute observations (capped at TIME_SERIES_HISTORY_WINDOW)."""
    if not indicator_ids:
        return {}
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]] = defaultdict(list)
    observation_rows = (
        EconomicDataModel.objects.filter(
            indicator_id__in=indicator_ids,
            data_value__isnull=False,
            period__isnull=False,
        )
        .select_related("indicator")
        .order_by("indicator_id", "-period")
        .iterator(chunk_size=2000)
    )
    for observation_row in observation_rows:
        indicator_pk = observation_row.indicator.pk
        time_series_rows = time_series_by_indicator_id[indicator_pk]
        if len(time_series_rows) >= TIME_SERIES_HISTORY_WINDOW:
            continue
        time_series_rows.append(observation_row)
    return time_series_by_indicator_id


class EconomicRecapTimeSeriesPoint(TypedDict):
    """One absolute observation for client-side Abs/QoQ/QoQy/YoY transforms."""

    period: str  # Display period label
    period_date: str  # ISO date string for the UI
    value: float


class EconomicRecapItem(TypedDict):
    """One location cell in the economic recap table."""

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
    time_series: list[EconomicRecapTimeSeriesPoint]


def _build_time_series_from_records(
    records: list[EconomicDataModel],
) -> list[EconomicRecapTimeSeriesPoint]:
    """Build chronological time-series points from newest-first observation rows."""
    return [
        {
            "period": record.get_period_display() or "",
            "period_date": record.period.isoformat(),
            "value": float(record.data_value),
        }
        for record in reversed(records)
        if record.period is not None and record.data_value is not None
    ]


def _build_recap_item_from_records(
    indicator: EconomicIndicatorInformationModel,
    location: EconomicDataLocationChoices,
    row_name: str,
    records: list[EconomicDataModel],
) -> EconomicRecapItem:
    """Build one location cell from prefetched newest-first observation rows."""
    curr, prev = (records + [None, None])[:2]
    curr_value = getattr(curr, "data_value", None)
    prev_value = getattr(prev, "data_value", None)
    period = curr.get_period_display() if curr else None
    change = (
        curr_value - prev_value
        if curr_value is not None and prev_value is not None
        else None
    )
    return EconomicRecapItem(
        category=EconomicDataCategoryChoices(indicator.category),
        location=location,
        name=row_name,
        display_name=indicator.display_name(),
        frequency=EconomicPublicationFrequencyChoices(indicator.frequency),
        base_year=indicator.base_year,
        base_unit=(
            IndicatorBaseUnitChoices(indicator.base_unit) if indicator.base_unit else ""
        ),
        current=curr_value,
        previous=prev_value,
        change=change,
        period=period,
        time_series=_build_time_series_from_records(records),
    )


def _build_recap_items_for_one_row(
    row_key: RecapRowKey,
    indicators_at_locations: list[IndicatorAtLocation],
    template_indicator: EconomicIndicatorInformationModel,
    locations: list[EconomicDataLocationChoices],
    # Usage of dict: keys are runtime indicator primary keys from the DB query.
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]],
) -> list[EconomicRecapItem]:
    """Build one cell per requested location for a single recap row."""
    display_name = template_indicator.display_name()
    frequency = EconomicPublicationFrequencyChoices(template_indicator.frequency)
    base_year = template_indicator.base_year
    base_unit: IndicatorBaseUnitChoices | Literal[""] = (
        IndicatorBaseUnitChoices(template_indicator.base_unit)
        if template_indicator.base_unit
        else ""
    )
    recap_items: list[EconomicRecapItem] = []
    for location in locations:
        indicator_for_location = next(
            (
                entry.indicator
                for entry in indicators_at_locations
                if entry.location == location
            ),
            None,
        )
        if indicator_for_location is None:
            # Placeholder so every location column stays aligned in the row.
            recap_items.append(
                EconomicRecapItem(
                    category=row_key.category,
                    location=location,
                    name=row_key.row_name,
                    display_name=display_name,
                    frequency=frequency,
                    base_year=base_year,
                    base_unit=base_unit,
                    current=None,
                    previous=None,
                    change=None,
                    period=None,
                    time_series=[],
                )
            )
            continue
        recap_items.append(
            _build_recap_item_from_records(
                indicator_for_location,
                location,
                row_key.row_name,
                time_series_by_indicator_id.get(indicator_for_location.id, []),
            )
        )
    return recap_items


class EconomicRecapCategoryGroup(TypedDict):
    """One category section of the economic recap table (ordered payload)."""

    category: EconomicDataCategoryChoices
    # Named ``rows`` (not ``items``) so Django templates do not resolve ``dict.items``.
    rows: list[EconomicRecapItem]


_RECAP_CACHE_ADAPTER = TypeAdapter(list[EconomicRecapCategoryGroup])


def _build_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> list[EconomicRecapCategoryGroup]:
    """Build economic recap rows for the requested locations."""
    indicators = list(
        EconomicIndicatorInformationModel.objects.filter(
            location__in=[location.value for location in locations]
        ).order_by("id")
    )
    row_grouping = _group_indicators_by_recap_row(indicators)
    time_series_by_indicator_id = _get_time_series_by_indicator_id(
        [indicator.id for indicator in indicators]
    )

    # Preserve indicator discovery order (first id that defined each row).
    row_items: list[tuple[RecapRowKey, list[EconomicRecapItem]]] = []
    for (
        row_key,
        indicators_at_locations,
    ) in row_grouping.indicators_at_locations_for_row.items():
        row_items.append(
            (
                row_key,
                _build_recap_items_for_one_row(
                    row_key,
                    indicators_at_locations,
                    row_grouping.template_indicator_by_row[row_key],
                    locations,
                    time_series_by_indicator_id,
                ),
            )
        )

    # Front table iterates categories in EconomicDataCategoryChoices.ordered() order.
    economic_data_by_category: list[EconomicRecapCategoryGroup] = []
    for category in EconomicDataCategoryChoices.ordered():
        category_items = [
            item
            for row_key, items in row_items
            if row_key.category == category
            for item in items
        ]
        if category_items:
            economic_data_by_category.append(
                EconomicRecapCategoryGroup(category=category, rows=category_items)
            )
    return economic_data_by_category


def get_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> list[EconomicRecapCategoryGroup]:
    """Get economic recap data.

    Rows are keyed by indicator ``type`` when that type is unique per location
    (so US/FR/JP GDP share one row). Duplicate types in the same location use
    ``name`` instead. Each row includes exactly one cell per requested location.

    Results are Redis-cached (versioned by observation/indicator table state).
    """
    fingerprint = ",".join(sorted(location.value for location in locations))
    cached = get_cached_economic_display(
        EconomicDisplayCacheType.RECAP, fingerprint, _RECAP_CACHE_ADAPTER
    )
    if cached is not None:
        return cached

    economic_recap_data = _build_economic_recap_data(locations)
    set_cached_economic_display(
        EconomicDisplayCacheType.RECAP, fingerprint, economic_recap_data
    )
    return economic_recap_data
