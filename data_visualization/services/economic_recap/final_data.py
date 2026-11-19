"""Build and cache the economic recap payload (and hidden Nominal GDP cells)."""

from pydantic import TypeAdapter

from data_visualization.services.cache import (
    EconomicDisplayCacheType,
    get_cached_economic_display,
    set_cached_economic_display,
)
from data_visualization.services.economic_recap.table_content import (
    EconomicRecapItem,
    build_recap_item_from_economic_data_values,
    get_real_gdp_series_by_location,
    get_realized_annual_gdp_growth_series_by_location,
    get_time_series_by_indicator_id,
    group_indicators_by_recap_line,
    list_recap_lines_with_items,
)
from data_visualization.services.economic_recap.table_structure import (
    EconomicRecapCategoryGroup,
    list_economic_recap_category_groups,
)
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicIndicatorInformationModel,
)

_RECAP_CACHE_ADAPTER = TypeAdapter(list[EconomicRecapCategoryGroup])


def _build_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> list[EconomicRecapCategoryGroup]:
    """Build the economic recap for the requested locations."""
    indicators = list(
        EconomicIndicatorInformationModel.objects.filter(
            location__in=[location.value for location in locations],
            is_hidden=False,
        ).order_by("id")
    )
    line_grouping = group_indicators_by_recap_line(indicators)
    time_series_by_indicator_id = get_time_series_by_indicator_id(
        [indicator.id for indicator in indicators]
    )
    real_gdp_series = get_real_gdp_series_by_location(
        indicators, time_series_by_indicator_id
    )
    realized_annual_series_by_location = (
        get_realized_annual_gdp_growth_series_by_location(locations)
    )
    recap_lines_by_key = list_recap_lines_with_items(
        line_grouping,
        locations,
        time_series_by_indicator_id,
        real_gdp_series,
        realized_annual_series_by_location,
    )
    return list_economic_recap_category_groups(recap_lines_by_key)


def get_economic_recap_data(
    locations: list[EconomicDataLocationChoices],
) -> list[EconomicRecapCategoryGroup]:
    """Get economic recap data.

    Lines are keyed by the series label when that label is unique per location
    (so US/FR/JP GDP share one line). Duplicate series labels in the same
    location use the full name instead. Each line includes exactly one cell
    per requested location.

    Results are Redis-cached (versioned by economic-data / indicator table state).
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


_NOMINAL_GDP_SERIES_LABEL = "Nominal GDP"
_NOMINAL_GDP_CACHE_ADAPTER = TypeAdapter(list[EconomicRecapItem])


def get_nominal_gdp_recap_items(
    locations: list[EconomicDataLocationChoices],
) -> list[EconomicRecapItem]:
    """Return hidden Nominal GDP cells for live vsGDP (never shown as recap lines).

    Cached separately from the visible recap so expand math can divide
    nominal outstanding / flow levels by Nominal GDP without listing it.
    Real printed levels use the visible Real GDP series instead.
    """
    fingerprint = "nominal_gdp:" + ",".join(
        sorted(location.value for location in locations)
    )
    cached = get_cached_economic_display(
        EconomicDisplayCacheType.RECAP, fingerprint, _NOMINAL_GDP_CACHE_ADAPTER
    )
    if cached is not None:
        return cached

    indicators = list(
        EconomicIndicatorInformationModel.objects.filter(
            location__in=[location.value for location in locations],
            series_label=_NOMINAL_GDP_SERIES_LABEL,
            is_hidden=True,
        ).order_by("id")
    )
    time_series_by_indicator_id = get_time_series_by_indicator_id(
        [indicator.id for indicator in indicators]
    )
    # Usage of dict: keys are location codes; at most one Nominal GDP per location.
    indicator_by_location: dict[str, EconomicIndicatorInformationModel] = {
        indicator.location: indicator for indicator in indicators
    }
    nominal_gdp_items: list[EconomicRecapItem] = []
    for location in locations:
        indicator = indicator_by_location.get(location.value)
        if indicator is None:
            continue
        nominal_gdp_items.append(
            build_recap_item_from_economic_data_values(
                indicator,
                location,
                _NOMINAL_GDP_SERIES_LABEL,
                time_series_by_indicator_id.get(indicator.id, []),
            )
        )
    set_cached_economic_display(
        EconomicDisplayCacheType.RECAP, fingerprint, nominal_gdp_items
    )
    return nominal_gdp_items
