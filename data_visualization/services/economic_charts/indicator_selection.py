"""Indicator selection defaults, front-form parsing, and multiselect catalogs."""

from typing import NamedTuple, TypedDict

from data_visualization.services.config import (
    CROSS_REGION_COMPARABILITY_WARNING_BY_SERIES_LABEL,
    CROSS_REGION_INFO_DESCRIPTION_BY_SERIES_LABEL,
    CROSS_REGION_INFO_LABEL_BY_LOCATION_BY_GROUP,
    CROSS_REGION_PREFERRED_INDICATORS_FOR_LINE_CHART_COMPARISON,
    ECONOMIC_CHARTS_CROSS_REGION_LABEL,
    ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS,
    ECONOMIC_CHARTS_DEFAULT_SERIES_LABELS,
    ECONOMIC_CHARTS_LOCATIONS,
    ECONOMIC_SUBCATEGORIES_BY_CATEGORY,
    ChartDefaultLocationScope,
    CrossRegionInfoGroup,
)
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    IndicatorDisplayModeChoices,
)
from economic_overview.services.config import (
    ANNUAL_GDP_GROWTH_SERIES_LABEL,
    VS_GDP_SERIES_LABELS,
)


class CategorySubcategoryPair(NamedTuple):
    """One charts pair: a category and the subcategory under it."""

    category: EconomicDataCategoryChoices
    subcategory: EconomicDataSubcategoryChoices


def list_category_subcategory_pairs() -> list[CategorySubcategoryPair]:
    """Return every configured category and subcategory chart slot, in display order."""
    category_subcategory_pairs: list[CategorySubcategoryPair] = []
    for category in EconomicDataCategoryChoices.ordered():
        for subcategory in ECONOMIC_SUBCATEGORIES_BY_CATEGORY[category]:
            category_subcategory_pairs.append(
                CategorySubcategoryPair(category=category, subcategory=subcategory)
            )
    return category_subcategory_pairs


def _format_chart_selection_query_suffix(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> str:
    """Return the form key suffix for one category and subcategory, without the region."""
    return f"{category.value.lower()}_{subcategory.value.lower()}_indicator"


class SelectedIndicatorsByCategorySubcategory(TypedDict):
    """Selected indicators for one category/subcategory chart."""

    category: EconomicDataCategoryChoices
    subcategory: EconomicDataSubcategoryChoices
    selected_indicators: list[str]  # UI Type or Type|MODE display strings


def get_selected_indicators_by_category_subcategory(
    region_key: str,
    # Usage of dict: keys are '{region}_{category}_{subcategory}_indicator' query params.
    front_data: dict[str, str],
) -> list[SelectedIndicatorsByCategorySubcategory]:
    """Return chart selections from the front form for every category and subcategory."""
    selected_indicators_by_chart: list[SelectedIndicatorsByCategorySubcategory] = []
    for category_subcategory_pair in list_category_subcategory_pairs():
        category = category_subcategory_pair.category
        subcategory = category_subcategory_pair.subcategory
        selection_key = (
            f"{region_key}_"
            f"{_format_chart_selection_query_suffix(category, subcategory)}"
        )
        selection_value = front_data.get(selection_key, "")
        selected_indicators = [
            indicator.strip()
            for indicator in selection_value.split(",")
            if indicator.strip()
        ]
        selected_indicators_by_chart.append(
            SelectedIndicatorsByCategorySubcategory(
                category=category,
                subcategory=subcategory,
                selected_indicators=selected_indicators,
            )
        )
    return selected_indicators_by_chart


def _get_default_mode_for_series_label(
    location: EconomicDataLocationChoices,
    series_label: str,
) -> IndicatorDisplayModeChoices:
    """Return the stored default display mode for a location and series label.

    Raw is used when no indicator exists for that location and series label.
    """
    indicator = (
        EconomicIndicatorInformationModel.objects.filter(
            location=location.value,
            series_label=series_label,
        )
        .only("default_mode")
        .first()
    )
    if indicator is None:
        return IndicatorDisplayModeChoices.RAW
    return IndicatorDisplayModeChoices(indicator.default_mode)


def _encode_indicator_selection(
    series_label: str,
    mode: IndicatorDisplayModeChoices,
    location: EconomicDataLocationChoices | None = None,
) -> str:
    """Encode a chart selection for form / URL values.

    Single-region: 'Type|MODE'. Cross-Region curves: 'Location|Type|MODE'.
    """
    if location is None:
        return f"{series_label}|{mode.value}"
    return f"{location.value}|{series_label}|{mode.value}"


def _does_series_label_exist_in_all_cross_region_locations(
    series_label: str,
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> bool:
    """Return whether every Cross-Region location has a visible series of this label."""
    for country in ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS:
        if not EconomicIndicatorInformationModel.objects.filter(
            location=country.value,
            series_label=series_label,
            category=category.value,
            subcategory=subcategory.value,
            is_hidden=False,
        ).exists():
            return False
    return True


def _encode_cross_region_default_selection(
    series_label: str,
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> str:
    """Encode a generic Cross-Region 'series label|MODE' when every location has it.

    Country expansion happens later from the Countries multi-select.
    """
    if not _does_series_label_exist_in_all_cross_region_locations(
        series_label, category, subcategory
    ):
        return ""
    return _encode_indicator_selection(
        series_label,
        _get_default_mode_for_series_label(
            EconomicDataLocationChoices.US, series_label
        ),
    )


def _get_default_series_labels_for_chart(
    location: EconomicDataLocationChoices,
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> list[str]:
    """Resolve the default series label(s) for one category/subcategory chart."""
    location_specific_series_labels = ECONOMIC_CHARTS_DEFAULT_SERIES_LABELS.get(
        (category, subcategory, location)
    )
    if location_specific_series_labels is not None:
        return list(location_specific_series_labels)
    all_location_series_labels = ECONOMIC_CHARTS_DEFAULT_SERIES_LABELS.get(
        (category, subcategory, ChartDefaultLocationScope.ALL)
    )
    return (
        list(all_location_series_labels)
        if all_location_series_labels is not None
        else []
    )


def _encode_default_selection_for_chart(
    location: EconomicDataLocationChoices | None,
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
    *,
    cross_region: bool = False,
) -> str:
    """Encode the default selection string for one chart slot (empty when absent)."""
    # Cross-Region has no single country, so resolve defaults as if the chart were US
    # (then the shared ALL entry). The value is still encoded without a location prefix.
    lookup_location = EconomicDataLocationChoices.US if cross_region else location
    if lookup_location is None:
        return ""
    series_labels = _get_default_series_labels_for_chart(
        lookup_location, category, subcategory
    )
    if not series_labels:
        return ""
    encoded_selections: list[str] = []
    for series_label in series_labels:
        if cross_region:
            encoded_selection = _encode_cross_region_default_selection(
                series_label, category, subcategory
            )
            if encoded_selection:
                encoded_selections.append(encoded_selection)
            continue
        if not EconomicIndicatorInformationModel.objects.filter(
            location=lookup_location.value,
            series_label=series_label,
            category=category.value,
            subcategory=subcategory.value,
            is_hidden=False,
        ).exists():
            continue
        encoded_selections.append(
            _encode_indicator_selection(
                series_label,
                _get_default_mode_for_series_label(lookup_location, series_label),
            )
        )
    return ",".join(encoded_selections)


def get_default_indicator_selections(
    location: EconomicDataLocationChoices,
) -> dict[str, str]:
    """Return chart defaults for one location, keyed by the form field suffix."""
    # Usage of dict: keys are the closed set of category/subcategory query suffixes.
    default_selections: dict[str, str] = {
        _format_chart_selection_query_suffix(
            category_subcategory_pair.category, category_subcategory_pair.subcategory
        ): (
            _encode_default_selection_for_chart(
                location,
                category_subcategory_pair.category,
                category_subcategory_pair.subcategory,
            )
        )
        for category_subcategory_pair in list_category_subcategory_pairs()
    }
    return default_selections


def get_default_cross_region_indicator_selections() -> dict[str, str]:
    """Return Cross-Region defaults as Type|MODE when the type exists everywhere."""
    # Usage of dict: keys are the closed set of category/subcategory query suffixes.
    default_selections: dict[str, str] = {
        _format_chart_selection_query_suffix(
            category_subcategory_pair.category, category_subcategory_pair.subcategory
        ): (
            _encode_default_selection_for_chart(
                None,
                category_subcategory_pair.category,
                category_subcategory_pair.subcategory,
                cross_region=True,
            )
        )
        for category_subcategory_pair in list_category_subcategory_pairs()
    }
    return default_selections


def _format_eu_cross_region_info_section(
    fr_description: str,
    description_by_location: dict[str, str],
) -> str:
    """Build the EU block of a Cross-Region info note from DE / ES / IT text."""
    eu_label_by_location = CROSS_REGION_INFO_LABEL_BY_LOCATION_BY_GROUP[
        CrossRegionInfoGroup.EU
    ]
    eu_descriptions = [
        description_by_location.get(location.value, "").strip()
        for location in eu_label_by_location
    ]
    non_empty_eu_descriptions = [
        description for description in eu_descriptions if description
    ]
    if not non_empty_eu_descriptions:
        return "No series description available."
    # The first EU description is the shared text when Germany, Spain, and Italy match.
    shared_eu_description = non_empty_eu_descriptions[0]
    if all(
        description == shared_eu_description
        for description in non_empty_eu_descriptions
    ):
        if fr_description and shared_eu_description == fr_description:
            return "Germany, Spain, and Italy use the same series as France."
        return f"Germany, Spain, and Italy: {shared_eu_description}"
    eu_lines: list[str] = []
    for location, location_label in eu_label_by_location.items():
        location_description = description_by_location.get(location.value, "").strip()
        if not location_description:
            continue
        eu_lines.append(f"{location_label}: {location_description}")
    return "\n".join(eu_lines) if eu_lines else "No series description available."


def _build_cross_region_info_description(
    series_label: str,
    description_by_location: dict[str, str],
) -> str:
    """Resolve the Cross-Region 'i' panel text as US / FR / JP / EU sections.

    Hand-tuned notes in 'CROSS_REGION_INFO_DESCRIPTION_BY_SERIES_LABEL' win when present;
    otherwise each region's seeded description is assembled into the same layout.
    """
    curated_description = CROSS_REGION_INFO_DESCRIPTION_BY_SERIES_LABEL.get(
        series_label
    )
    if curated_description:
        return curated_description
    core_label_by_location = CROSS_REGION_INFO_LABEL_BY_LOCATION_BY_GROUP[
        CrossRegionInfoGroup.CORE
    ]
    core_lines: list[str] = []
    for location, location_label in core_label_by_location.items():
        location_description = description_by_location.get(location.value, "").strip()
        core_lines.append(
            f"{location_label}: "
            f"{location_description or 'No series description available.'}"
        )
    fr_description = description_by_location.get(
        EconomicDataLocationChoices.FR.value, ""
    ).strip()
    eu_description = _format_eu_cross_region_info_section(
        fr_description, description_by_location
    )
    return "\n".join([*core_lines, f"EU: {eu_description}"])


def get_indicator_for_line_chart_comparison(
    candidates: list[EconomicIndicatorInformationModel],
    *,
    cross_region: bool,
) -> EconomicIndicatorInformationModel | None:
    """Return the indicator to plot for one location and series label.

    Candidates share a location and series label and are ordered by id. Single-country
    charts use the lowest id. Cross-Region uses the full name listed in
    'CROSS_REGION_PREFERRED_INDICATORS_FOR_LINE_CHART_COMPARISON' when one of the
    candidates matches (e.g. France's hidden monthly Eurostat unemployment); otherwise
    the lowest id.
    """
    if not candidates:
        return None
    if not cross_region:
        # Candidates are ordered by id; the lowest id wins for single-region charts.
        return candidates[0]
    # Candidates for one location and series label share category and subcategory.
    # The first candidate keys the cross-region preferred-indicator lookup.
    template_candidate = candidates[0]
    preferred_indicator = (
        CROSS_REGION_PREFERRED_INDICATORS_FOR_LINE_CHART_COMPARISON.get(
            (
                EconomicDataLocationChoices(template_candidate.location),
                EconomicDataCategoryChoices(template_candidate.category),
                EconomicDataSubcategoryChoices(template_candidate.subcategory),
            )
        )
    )
    if preferred_indicator is not None:
        for candidate in candidates:
            if candidate.full_name == preferred_indicator:
                return candidate
    # No preferred match: candidates are ordered by id, so the lowest id wins.
    return candidates[0]


class _ChartMultiselectIndicator(TypedDict):
    """One indicator entry in the charts multiselect."""

    series_label: str  # Series key such as 'GDP'. Cross-Region selections do not prefix a location.
    name: str  # Display label
    default_mode: str  # IndicatorDisplayModeChoices value from the DB
    measure_type: str  # IndicatorMeasureTypeChoices value (gates FLOW YTD modes)
    expansion_relation: str  # COMPONENT / RELATED / empty
    supports_vs_gdp: bool
    description: str  # Bubble blurb for the chart info toolbox
    comparability_warning: str  # Cross-Region caveat; empty when none


class _IndicatorsByCategorySubcategory(TypedDict):
    """Indicators for one category/subcategory charts dropdown."""

    category: str  # Display label (Choices.label)
    subcategory: str  # Display label (Choices.label)
    indicators: list[_ChartMultiselectIndicator]


class EconomicChartsDropdownValues(TypedDict):
    """Location, category, and indicator options for the economic charts page."""

    locations: list[str]  # Display labels (Choices.label)
    categories: list[str]  # Display labels (Choices.label)
    indicators_by_category_subcategory: list[_IndicatorsByCategorySubcategory]


def _get_chart_multiselect_indicator(
    *,
    series_label: str,
    sample_indicator: EconomicIndicatorInformationModel,
    description: str,
    comparability_warning: str = "",
) -> _ChartMultiselectIndicator:
    """Return one charts-multiselect indicator from a sample and info-panel text."""
    return _ChartMultiselectIndicator(
        series_label=series_label,
        name=series_label,
        default_mode=sample_indicator.default_mode,
        measure_type=sample_indicator.measure_type,
        expansion_relation=sample_indicator.expansion_relation or "",
        supports_vs_gdp=series_label in VS_GDP_SERIES_LABELS,
        description=description,
        comparability_warning=comparability_warning,
    )


def _list_single_location_chart_multiselect_indicators(
    location: EconomicDataLocationChoices,
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> list[_ChartMultiselectIndicator]:
    """Return charts-multiselect indicators for one country chart slot."""
    # Circular: indicator_selection ↔ indicator_breakdown ↔ line_charts
    from data_visualization.services.economic_charts.indicator_breakdown import (
        is_composition_owned_series,
    )

    multiselect_indicators: list[_ChartMultiselectIndicator] = []
    seen_series_labels: set[str] = set()
    for indicator in EconomicIndicatorInformationModel.objects.filter(
        category=category.value,
        subcategory=subcategory.value,
        location=location.value,
        is_hidden=False,
    ).order_by("id"):
        if indicator.series_label == ANNUAL_GDP_GROWTH_SERIES_LABEL:
            continue
        if is_composition_owned_series(indicator):
            continue
        if indicator.series_label in seen_series_labels:
            continue
        seen_series_labels.add(indicator.series_label)
        multiselect_indicators.append(
            _get_chart_multiselect_indicator(
                series_label=indicator.series_label,
                sample_indicator=indicator,
                description=indicator.description or "",
            )
        )
    return multiselect_indicators


class _CrossRegionSeriesLabelIndex(NamedTuple):
    """Cross-region chart multiselect index keyed by series label."""

    locations_by_series_label: dict[str, set[str]]
    candidates_by_series_label_and_location: dict[
        str, dict[str, list[EconomicIndicatorInformationModel]]
    ]


def _build_cross_region_series_label_index(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> _CrossRegionSeriesLabelIndex:
    """Index visible cross-region series labels and per-location indicator candidates."""
    # Usage of dict: series label → locations that have a visible series with that label.
    locations_by_series_label: dict[str, set[str]] = {}
    # Usage of dict: series label → location code → id-ordered candidates.
    candidates_by_series_label_and_location: dict[
        str, dict[str, list[EconomicIndicatorInformationModel]]
    ] = {}
    for country in ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS:
        for indicator in EconomicIndicatorInformationModel.objects.filter(
            category=category.value,
            subcategory=subcategory.value,
            location=country.value,
            is_hidden=False,
        ).order_by("id"):
            if indicator.series_label == ANNUAL_GDP_GROWTH_SERIES_LABEL:
                # Recap-only derived line; no chartable Raw history.
                continue
            locations_by_series_label.setdefault(indicator.series_label, set()).add(
                country.value
            )
            candidates_by_series_label_and_location.setdefault(
                indicator.series_label, {}
            ).setdefault(country.value, []).append(indicator)
    return _CrossRegionSeriesLabelIndex(
        locations_by_series_label=locations_by_series_label,
        candidates_by_series_label_and_location=candidates_by_series_label_and_location,
    )


def _append_cross_region_chart_multiselect_indicator(
    multiselect_indicators: list[_ChartMultiselectIndicator],
    *,
    series_label: str,
    location_candidates: dict[str, list[EconomicIndicatorInformationModel]],
) -> None:
    """Append one cross-region multiselect option when every country is chartable."""
    # Circular: indicator_selection ↔ indicator_breakdown ↔ line_charts
    from data_visualization.services.economic_charts.indicator_breakdown import (
        is_composition_owned_series,
    )

    # US supplies default_mode / measure_type for the shared Cross-Region option.
    us_sample = get_indicator_for_line_chart_comparison(
        location_candidates.get(EconomicDataLocationChoices.US.value, []),
        cross_region=True,
    )
    if us_sample is None or is_composition_owned_series(us_sample):
        return
    # Usage of dict: location code → series description for the info panel.
    description_by_location: dict[str, str] = {}
    for country in ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS:
        comparison_indicator = get_indicator_for_line_chart_comparison(
            location_candidates.get(country.value, []),
            cross_region=True,
        )
        description_by_location[country.value] = (
            (comparison_indicator.description or "") if comparison_indicator else ""
        )
    multiselect_indicators.append(
        _get_chart_multiselect_indicator(
            series_label=series_label,
            sample_indicator=us_sample,
            description=_build_cross_region_info_description(
                series_label, description_by_location
            ),
            comparability_warning=(
                CROSS_REGION_COMPARABILITY_WARNING_BY_SERIES_LABEL.get(series_label, "")
            ),
        )
    )


def _list_cross_region_chart_multiselect_indicators(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> list[_ChartMultiselectIndicator]:
    """Return charts-multiselect indicators present in every Cross-Region country."""
    series_label_index = _build_cross_region_series_label_index(category, subcategory)
    cross_region_location_codes = {
        country.value for country in ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS
    }
    multiselect_indicators: list[_ChartMultiselectIndicator] = []
    for (
        series_label,
        locations_with_series_label,
    ) in series_label_index.locations_by_series_label.items():
        if locations_with_series_label != cross_region_location_codes:
            continue
        _append_cross_region_chart_multiselect_indicator(
            multiselect_indicators,
            series_label=series_label,
            location_candidates=series_label_index.candidates_by_series_label_and_location[
                series_label
            ],
        )
    return multiselect_indicators


def get_economic_charts_dropdown_values(
    *,
    cross_region: bool,
    location: EconomicDataLocationChoices | None,
) -> EconomicChartsDropdownValues:
    """Return location, category, and indicator options for the economic charts page."""
    indicators_by_category_subcategory: list[_IndicatorsByCategorySubcategory] = []
    for category, subcategory in list_category_subcategory_pairs():
        if cross_region:
            multiselect_indicators = _list_cross_region_chart_multiselect_indicators(
                category, subcategory
            )
        else:
            assert location is not None
            multiselect_indicators = _list_single_location_chart_multiselect_indicators(
                location, category, subcategory
            )
        indicators_by_category_subcategory.append(
            _IndicatorsByCategorySubcategory(
                category=str(category.label),
                subcategory=str(subcategory.label),
                indicators=multiselect_indicators,
            )
        )
    return EconomicChartsDropdownValues(
        categories=EconomicDataCategoryChoices.get_labels(),
        locations=[
            str(chart_location.label) for chart_location in ECONOMIC_CHARTS_LOCATIONS
        ]
        + [ECONOMIC_CHARTS_CROSS_REGION_LABEL],
        indicators_by_category_subcategory=indicators_by_category_subcategory,
    )
