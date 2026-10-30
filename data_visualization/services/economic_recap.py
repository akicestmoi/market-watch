"""Build economic recap payloads and format indicator values for display."""

from collections import defaultdict
from typing import NamedTuple, TypedDict

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
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
    IndicatorDisplayModeChoices,
)


class _ScaledAmount(NamedTuple):
    """Value scaled so its absolute magnitude stays at most 999."""

    value: float
    magnitude: IndicatorAmountMagnitudeChoices
    currency: IndicatorBaseCurrencyChoices | None


def _format_amount_unit_label(
    magnitude: IndicatorAmountMagnitudeChoices,
    currency: IndicatorBaseCurrencyChoices | None = None,
) -> str:
    """Build a compact amount label such as ``bUSD`` or ``m``."""
    magnitude_label = magnitude.value.lower()
    if currency is None:
        return magnitude_label
    return f"{magnitude_label}{currency.value}"


def _scale_amount_for_display(
    value: float,
    amount_magnitude: IndicatorAmountMagnitudeChoices,
    base_currency: IndicatorBaseCurrencyChoices | None = None,
) -> _ScaledAmount:
    """Divide by 1_000 until ``abs(value) <= 999``, bumping K→M→B→T."""
    magnitude_order = IndicatorAmountMagnitudeChoices.ordered()
    scaled_magnitude = amount_magnitude
    scaled_value = float(value)
    while abs(scaled_value) > 999:
        next_magnitude_index = magnitude_order.index(scaled_magnitude) + 1
        if next_magnitude_index >= len(magnitude_order):
            break
        scaled_value /= 1000.0
        scaled_magnitude = magnitude_order[next_magnitude_index]
    return _ScaledAmount(
        value=scaled_value, magnitude=scaled_magnitude, currency=base_currency
    )


def _format_spaced_number(value: float, digits: int = 2) -> str:
    """Format with space thousands separators, e.g. ``1 234.56``."""
    sign = "-" if value < 0 else ""
    absolute_value = abs(value)
    formatted_number = f"{absolute_value:.{digits}f}"
    integer_part, _, decimal_part = formatted_number.partition(".")
    spaced_integer = ""
    digits_reversed = integer_part[::-1]
    for index, digit in enumerate(digits_reversed):
        if index and index % 3 == 0:
            spaced_integer += " "
        spaced_integer += digit
    spaced_integer = spaced_integer[::-1]
    if digits > 0:
        return f"{sign}{spaced_integer}.{decimal_part}"
    return f"{sign}{spaced_integer}"


def format_indicator_value(
    value: float | None,
    *,
    base_unit: str = "",
    base_currency: str = "",
    mode: IndicatorDisplayModeChoices | str = IndicatorDisplayModeChoices.RAW,
    include_unit_label: bool = True,
    digits: int = 2,
) -> str:
    """Format a single indicator value for UI / LLM display.

    Amounts append a parenthesis unit with currency (``(bUSD)``). Percent and
    growth modes append `` %`` (no parentheses). Index series have no unit suffix.
    """
    if value is None:
        return ""
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    if mode_value != IndicatorDisplayModeChoices.RAW:
        formatted_number = _format_spaced_number(value, digits=digits)
        return f"{formatted_number} %" if include_unit_label else formatted_number
    if base_unit == IndicatorBaseUnitChoices.PERCENT:
        formatted_number = _format_spaced_number(value, digits=digits)
        return f"{formatted_number} %" if include_unit_label else formatted_number
    if base_unit in {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }:
        scaled_amount = _scale_amount_for_display(
            value,
            IndicatorAmountMagnitudeChoices(base_unit),
            (IndicatorBaseCurrencyChoices(base_currency) if base_currency else None),
        )
        formatted_number = _format_spaced_number(scaled_amount.value, digits=digits)
        if not include_unit_label:
            return formatted_number
        unit_label = _format_amount_unit_label(
            scaled_amount.magnitude, scaled_amount.currency
        )
        return f"{formatted_number} ({unit_label})"
    # INDEX or undocumented blank unit — number only.
    return _format_spaced_number(value, digits=digits)


def _format_recap_row_unit_parenthesis(
    indicators: list[EconomicIndicatorInformationModel],
    *,
    mode: IndicatorDisplayModeChoices = IndicatorDisplayModeChoices.RAW,
) -> str:
    """parenthesis unit / base-year suffix for a cross-location recap row title.

    When locations disagree on base year or amount unit, join with `` / `` and
    include short location codes (e.g. ``(in mUSD / bJPY)``,
    ``(base year: 2010 US / 2025 FR)``).
    """
    if mode != IndicatorDisplayModeChoices.RAW:
        return "(in %)"
    if not indicators:
        return ""

    base_units = {indicator.base_unit for indicator in indicators}
    if IndicatorBaseUnitChoices.PERCENT in base_units and len(base_units) == 1:
        return "(in %)"
    if IndicatorBaseUnitChoices.INDEX in base_units:
        base_years_with_locations = [
            (indicator.base_year, indicator.location)
            for indicator in indicators
            if indicator.base_year is not None
        ]
        if not base_years_with_locations:
            return ""
        unique_base_years = {year for year, _ in base_years_with_locations}
        if len(unique_base_years) == 1:
            return f"(base year: {base_years_with_locations[0][0]})"
        base_year_parts = [
            f"{base_year} {location}"
            for base_year, location in base_years_with_locations
            if base_year is not None
        ]
        return f"(base year: {' / '.join(base_year_parts)})"

    amount_unit_labels: list[str] = []
    for indicator in indicators:
        amount_unit_label = indicator.get_amount_unit_label()
        if amount_unit_label is None:
            continue
        amount_unit_labels.append(amount_unit_label)
    if not amount_unit_labels:
        return ""
    unique_amount_unit_labels = list(dict.fromkeys(amount_unit_labels))
    return f"(in {' / '.join(unique_amount_unit_labels)})"


class _RecapRowKey(NamedTuple):
    """Identity of one aligned recap table row."""

    category: EconomicDataCategoryChoices
    row_name: str


class _IndicatorAtLocation(NamedTuple):
    """One indicator contributing a cell on a recap row."""

    location: EconomicDataLocationChoices
    indicator: EconomicIndicatorInformationModel


class _RecapRowGrouping(NamedTuple):
    """Indicators grouped by recap row, plus a template indicator per row."""

    # Usage of dict: keys are runtime (category, row_name) pairs from the DB.
    indicators_at_locations_for_row: dict[_RecapRowKey, list[_IndicatorAtLocation]]
    # Usage of dict: keys are the same row keys; value is the first indicator seen.
    template_indicator_by_row: dict[_RecapRowKey, EconomicIndicatorInformationModel]


def _group_indicators_by_recap_row(
    indicators: list[EconomicIndicatorInformationModel],
) -> _RecapRowGrouping:
    """Group indicators into cross-location recap rows (shared type or unique name)."""
    # Usage of dict: keys are runtime (type, location) pairs from the DB query.
    type_count_in_location: dict[tuple[str, str], int] = defaultdict(int)
    for indicator in indicators:
        type_count_in_location[(indicator.type, indicator.location)] += 1

    # Usage of dict: keys are runtime row keys from the DB query.
    indicators_at_locations_for_row: dict[_RecapRowKey, list[_IndicatorAtLocation]] = (
        defaultdict(list)
    )
    template_indicator_by_row: dict[_RecapRowKey, EconomicIndicatorInformationModel] = (
        {}
    )
    for indicator in indicators:
        # Shared type across countries when unique in-location; else name (e.g. Tankan).
        row_name = (
            indicator.name
            if type_count_in_location[(indicator.type, indicator.location)] > 1
            else indicator.type
        )
        recap_row_key = _RecapRowKey(
            category=EconomicDataCategoryChoices(indicator.category),
            row_name=row_name,
        )
        indicators_at_locations_for_row[recap_row_key].append(
            _IndicatorAtLocation(
                location=EconomicDataLocationChoices(indicator.location),
                indicator=indicator,
            )
        )
        template_indicator_by_row.setdefault(recap_row_key, indicator)
    return _RecapRowGrouping(
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
        observation_time_series = time_series_by_indicator_id[indicator_pk]
        if len(observation_time_series) >= TIME_SERIES_HISTORY_WINDOW:
            continue
        observation_time_series.append(observation_row)
    return time_series_by_indicator_id


class _EconomicRecapTimeSeriesPoint(TypedDict):
    """One absolute observation for client-side Abs/QoQ/QoQy/YoY transforms."""

    period: str  # Display period label
    period_date: str  # ISO date string for the UI
    value: float


class _EconomicRecapItem(TypedDict):
    """One location cell in the economic recap table."""

    category: EconomicDataCategoryChoices
    location: EconomicDataLocationChoices
    name: str
    display_name: str
    frequency: EconomicPublicationFrequencyChoices
    base_year: int | None
    base_unit: IndicatorBaseUnitChoices | None
    base_currency: IndicatorBaseCurrencyChoices | None
    default_mode: IndicatorDisplayModeChoices
    current: float | None
    previous: float | None
    change: float | None
    period: str | None  # Display period label
    time_series: list[_EconomicRecapTimeSeriesPoint]


def _build_time_series_from_observation_rows(
    observation_rows: list[EconomicDataModel],
) -> list[_EconomicRecapTimeSeriesPoint]:
    """Build chronological time-series points from newest-first observation rows."""
    return [
        _EconomicRecapTimeSeriesPoint(
            period=observation_row.get_period_display() or "",
            period_date=observation_row.period.isoformat(),
            value=float(observation_row.data_value),
        )
        for observation_row in reversed(observation_rows)
        if observation_row.period is not None and observation_row.data_value is not None
    ]


def _build_recap_item_from_observation_rows(
    indicator: EconomicIndicatorInformationModel,
    location: EconomicDataLocationChoices,
    row_name: str,
    observation_rows: list[EconomicDataModel],
) -> _EconomicRecapItem:
    """Build one location cell from prefetched newest-first observation rows."""
    padded_observation_rows = observation_rows + [None, None]
    current_observation = padded_observation_rows[0]
    previous_observation = padded_observation_rows[1]
    current_value = (
        current_observation.data_value if current_observation is not None else None
    )
    previous_value = (
        previous_observation.data_value if previous_observation is not None else None
    )
    period_display = (
        current_observation.get_period_display()
        if current_observation is not None
        else None
    )
    value_change = (
        current_value - previous_value
        if current_value is not None and previous_value is not None
        else None
    )
    return _EconomicRecapItem(
        category=EconomicDataCategoryChoices(indicator.category),
        location=location,
        name=row_name,
        display_name=indicator.get_display_name(),
        frequency=EconomicPublicationFrequencyChoices(indicator.frequency),
        base_year=indicator.base_year,
        base_unit=(
            IndicatorBaseUnitChoices(indicator.base_unit)
            if indicator.base_unit
            else None
        ),
        base_currency=(
            IndicatorBaseCurrencyChoices(indicator.base_currency)
            if indicator.base_currency
            else None
        ),
        default_mode=IndicatorDisplayModeChoices(indicator.default_mode),
        current=current_value,
        previous=previous_value,
        change=value_change,
        period=period_display,
        time_series=_build_time_series_from_observation_rows(observation_rows),
    )


def _build_recap_items_for_one_row(
    recap_row_key: _RecapRowKey,
    indicators_at_locations: list[_IndicatorAtLocation],
    template_indicator: EconomicIndicatorInformationModel,
    locations: list[EconomicDataLocationChoices],
    # Usage of dict: keys are runtime indicator primary keys from the DB query.
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]],
) -> list[_EconomicRecapItem]:
    """Build one cell per requested location for a single recap row."""
    present_indicators = [entry.indicator for entry in indicators_at_locations]
    indicator_default_display_mode = IndicatorDisplayModeChoices(
        template_indicator.default_mode
    )
    unit_parenthesis = _format_recap_row_unit_parenthesis(
        present_indicators, mode=indicator_default_display_mode
    )
    display_name = (
        f"{template_indicator.type} {unit_parenthesis}".strip()
        if unit_parenthesis
        else template_indicator.type
    )
    frequency = EconomicPublicationFrequencyChoices(template_indicator.frequency)
    base_year = template_indicator.base_year
    base_unit: IndicatorBaseUnitChoices | None = (
        IndicatorBaseUnitChoices(template_indicator.base_unit)
        if template_indicator.base_unit
        else None
    )
    base_currency = (
        IndicatorBaseCurrencyChoices(template_indicator.base_currency)
        if template_indicator.base_currency
        else None
    )
    recap_items: list[_EconomicRecapItem] = []
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
                _EconomicRecapItem(
                    category=recap_row_key.category,
                    location=location,
                    name=recap_row_key.row_name,
                    display_name=display_name,
                    frequency=frequency,
                    base_year=base_year,
                    base_unit=base_unit,
                    base_currency=base_currency,
                    default_mode=indicator_default_display_mode,
                    current=None,
                    previous=None,
                    change=None,
                    period=None,
                    time_series=[],
                )
            )
            continue
        recap_item = _build_recap_item_from_observation_rows(
            indicator_for_location,
            location,
            recap_row_key.row_name,
            time_series_by_indicator_id.get(indicator_for_location.id, []),
        )
        recap_item["display_name"] = display_name
        recap_item["default_mode"] = indicator_default_display_mode
        recap_items.append(recap_item)
    return recap_items


class _EconomicRecapCategoryGroup(TypedDict):
    """One category section of the economic recap table (ordered payload)."""

    category: EconomicDataCategoryChoices
    # Named ``rows`` (not ``items``) so Django templates do not resolve ``dict.items``.
    rows: list[_EconomicRecapItem]


_RECAP_CACHE_ADAPTER = TypeAdapter(list[_EconomicRecapCategoryGroup])


def _build_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> list[_EconomicRecapCategoryGroup]:
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
    recap_rows_by_key: list[tuple[_RecapRowKey, list[_EconomicRecapItem]]] = []
    for (
        recap_row_key,
        indicators_at_locations,
    ) in row_grouping.indicators_at_locations_for_row.items():
        recap_rows_by_key.append(
            (
                recap_row_key,
                _build_recap_items_for_one_row(
                    recap_row_key,
                    indicators_at_locations,
                    row_grouping.template_indicator_by_row[recap_row_key],
                    locations,
                    time_series_by_indicator_id,
                ),
            )
        )

    # Front table iterates categories in EconomicDataCategoryChoices.ordered() order.
    economic_data_by_category: list[_EconomicRecapCategoryGroup] = []
    for category in EconomicDataCategoryChoices.ordered():
        category_recap_items = [
            recap_item
            for recap_row_key, recap_items in recap_rows_by_key
            if recap_row_key.category == category
            for recap_item in recap_items
        ]
        if category_recap_items:
            economic_data_by_category.append(
                _EconomicRecapCategoryGroup(
                    category=category, rows=category_recap_items
                )
            )
    return economic_data_by_category


def get_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> list[_EconomicRecapCategoryGroup]:
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
