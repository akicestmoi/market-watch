"""Economic charts page view."""

import json
from typing import NamedTuple

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from data_visualization.services.config import (
    ECONOMIC_CHARTS_CROSS_REGION_LABEL,
    ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS,
    ChartPeriodWindow,
)
from data_visualization.services.economic_charts import (
    indicator_breakdown,
    indicator_selection,
    industry_profitability,
    line_charts,
    trade_rankings,
)
from data_visualization.services.economic_charts.indicator_breakdown import (
    CompositionChartPanel,
)
from data_visualization.services.economic_charts.indicator_selection import (
    EconomicChartsDropdownValues,
)
from data_visualization.services.economic_charts.industry_profitability import (
    IndustryProfitabilityPanel,
)
from data_visualization.services.economic_charts.line_charts import EconomicChartsData
from data_visualization.services.economic_charts.trade_rankings import (
    TradeRankingChartsPanel,
)
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import EconomicDataCategoryChoices


def _get_economic_charts_default_values() -> dict[str, str]:
    """Return default GET param values for the economic charts page."""
    us_defaults = indicator_selection.get_default_indicator_selections(
        EconomicDataLocationChoices.US,
    )
    cross_defaults = indicator_selection.get_default_cross_region_indicator_selections()
    fr_defaults = indicator_selection.get_default_indicator_selections(
        EconomicDataLocationChoices.FR,
    )
    jp_defaults = indicator_selection.get_default_indicator_selections(
        EconomicDataLocationChoices.JP,
    )
    # Usage of dict: GET param names mapped to default string values.
    return {
        "region": EconomicDataLocationChoices.US.value,
        "period_window": ChartPeriodWindow.TEN_YEARS.value,
        **{f"us_{key}": value for key, value in us_defaults.items()},
        **{f"cross_{key}": value for key, value in cross_defaults.items()},
        **{f"fr_{key}": value for key, value in fr_defaults.items()},
        **{f"jp_{key}": value for key, value in jp_defaults.items()},
    }


class _EconomicChartsRegionSelection(NamedTuple):
    """Charts region for a single-country location, or Cross-Region."""

    selected_region: str
    location: EconomicDataLocationChoices | None
    cross_region: bool
    region_key: str


def _get_economic_charts_region_selection(
    requested_region: str,
) -> _EconomicChartsRegionSelection:
    """Map the region query param to a single-country or Cross-Region charts view."""
    if requested_region == ECONOMIC_CHARTS_CROSS_REGION_LABEL:
        return _EconomicChartsRegionSelection(
            selected_region=ECONOMIC_CHARTS_CROSS_REGION_LABEL,
            location=None,
            cross_region=True,
            region_key="cross",
        )

    location: EconomicDataLocationChoices | None = None
    if requested_region in EconomicDataLocationChoices.values:
        location = EconomicDataLocationChoices(requested_region)
    else:
        try:
            location = EconomicDataLocationChoices.from_label(requested_region)
        except ValueError:
            location = None
    if location is None:
        raise ValueError(
            f"Invalid economic charts region {requested_region!r}; "
            "use a location code (e.g. US, FR) or Cross-Region."
        )
    return _EconomicChartsRegionSelection(
        selected_region=str(location.label),
        location=location,
        cross_region=False,
        region_key=location.value.lower(),
    )


def _parse_economic_charts_selected_countries(
    request: HttpRequest,
) -> list[EconomicDataLocationChoices]:
    """Parse cross-region country checklist from GET, or use all configured codes."""
    available_cross_countries = list(ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS)
    available_cross_country_codes = {
        country.value for country in available_cross_countries
    }
    raw_countries = (request.GET.get("countries") or "").strip()
    if raw_countries:
        requested_country_codes = [
            code.strip() for code in raw_countries.split(",") if code.strip()
        ]
        selected_countries = [
            EconomicDataLocationChoices(code)
            for code in requested_country_codes
            if code in available_cross_country_codes
        ]
        if not selected_countries:
            selected_countries = list(available_cross_countries)
    else:
        selected_countries = list(available_cross_countries)
    return selected_countries


class _EconomicChartsPageState(NamedTuple):
    """Parsed GET state for the economic charts page."""

    # Usage of dict: front-end GET param bag and selected control values.
    front_data: dict[str, str]
    selected_values: dict[str, str]
    region_selection: _EconomicChartsRegionSelection
    period_window: ChartPeriodWindow
    selected_countries: list[EconomicDataLocationChoices]
    # Usage of dict: template error_messages keys by field name.
    errors: dict[str, str]


def _parse_economic_charts_page_state(
    request: HttpRequest,
    default_values: dict[str, str],
) -> _EconomicChartsPageState:
    """Parse query params into front-end state for economic charts."""
    # Usage of dict: front-end GET param bag for the charts page.
    front_data = {
        key: request.GET.get(key, default_values[key]) for key in default_values.keys()
    }
    # Usage of dict: template error_messages keys by field name.
    errors: dict[str, str] = {}
    selected_values = {**front_data}
    requested_region = selected_values.get("region", default_values["region"])
    region_selection = _get_economic_charts_region_selection(requested_region)
    # Keep the wire value (US / FR / JP / Cross-Region) in selected_values so
    # filter reloads never round-trip a display label such as 'Japan'.
    if region_selection.cross_region:
        region_param = ECONOMIC_CHARTS_CROSS_REGION_LABEL
    else:
        assert region_selection.location is not None
        region_param = region_selection.location.value
    selected_values["region"] = region_param
    front_data["region"] = region_param

    period_window = ChartPeriodWindow(
        selected_values.get("period_window", default_values["period_window"])
    )
    selected_countries = _parse_economic_charts_selected_countries(request)
    selected_values["countries"] = ",".join(
        country.value for country in selected_countries
    )
    return _EconomicChartsPageState(
        front_data=front_data,
        selected_values=selected_values,
        region_selection=region_selection,
        period_window=period_window,
        selected_countries=selected_countries,
        errors=errors,
    )


class _EconomicChartsPanelPayload(NamedTuple):
    """Dropdown and chart panel payloads for the economic charts template."""

    dropdown_values: EconomicChartsDropdownValues
    economic_data: list[EconomicChartsData]
    composition_panels: list[CompositionChartPanel]
    industry_profitability_panels: list[IndustryProfitabilityPanel]
    trade_ranking_panels: list[TradeRankingChartsPanel]


def _load_economic_charts_panel_payload(
    page_state: _EconomicChartsPageState,
) -> _EconomicChartsPanelPayload:
    """Load dropdown options and chart panel data for economic charts."""
    region_selection = page_state.region_selection
    dropdown_values = indicator_selection.get_economic_charts_dropdown_values(
        cross_region=region_selection.cross_region,
        location=region_selection.location,
    )
    selected_indicators_by_chart = (
        indicator_selection.get_selected_indicators_by_category_subcategory(
            region_selection.region_key,
            page_state.front_data,
        )
    )
    economic_data = line_charts.get_economic_charts_data(
        region_selection.location,
        selected_indicators_by_chart,
        period_window=page_state.period_window,
        cross_region=region_selection.cross_region,
        countries=(
            page_state.selected_countries if region_selection.cross_region else None
        ),
    )
    composition_panels = indicator_breakdown.get_composition_chart_panels(
        region_selection.location,
        page_state.period_window,
        cross_region=region_selection.cross_region,
    )
    industry_profitability_panels = (
        industry_profitability.get_industry_profitability_panels(
            region_selection.location,
            cross_region=region_selection.cross_region,
            period_window=page_state.period_window,
        )
    )
    trade_ranking_panels = trade_rankings.get_trade_ranking_panels(
        region_selection.location,
        cross_region=region_selection.cross_region,
    )
    return _EconomicChartsPanelPayload(
        dropdown_values=dropdown_values,
        economic_data=economic_data,
        composition_panels=composition_panels,
        industry_profitability_panels=industry_profitability_panels,
        trade_ranking_panels=trade_ranking_panels,
    )


# Usage of dict: Django template context for the economic charts page.
def _build_economic_charts_template_context(
    page_state: _EconomicChartsPageState,
    panel_payload: _EconomicChartsPanelPayload,
) -> dict:
    """Assemble template context for the economic charts page."""
    available_cross_countries = list(ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS)
    # Usage of dict: Django template context for the economic charts page.
    context: dict = {
        "region": page_state.region_selection.selected_region,
        "period_window": page_state.period_window.value,
        "period_window_options": [
            period_window_option.value for period_window_option in ChartPeriodWindow
        ],
        "dropdown_values": json.dumps(panel_payload.dropdown_values, default=str),
        "economic_data": json.dumps(panel_payload.economic_data, default=str),
        "composition_panels": json.dumps(panel_payload.composition_panels, default=str),
        "industry_profitability_panels": json.dumps(
            panel_payload.industry_profitability_panels, default=str
        ),
        "trade_ranking_panels": json.dumps(
            panel_payload.trade_ranking_panels, default=str
        ),
        "categories": json.dumps(EconomicDataCategoryChoices.get_labels()),
        "selected_values": json.dumps(page_state.selected_values),
        "cross_region_countries": json.dumps(
            [
                {"code": country.value, "label": str(country.label)}
                for country in available_cross_countries
            ]
        ),
        "selected_countries": json.dumps(
            [country.value for country in page_state.selected_countries]
        ),
    }
    if page_state.errors:
        context["error_messages"] = json.dumps(page_state.errors)
    return context


def economic_charts_view(request: HttpRequest) -> HttpResponse:
    """Economic Charts View."""
    # Same category/subcategory stack across regions. Cross-Region overlays
    # US/FR/JP/DE/ES/IT when the type exists in every location.
    default_values = _get_economic_charts_default_values()
    page_state = _parse_economic_charts_page_state(request, default_values)
    panel_payload = _load_economic_charts_panel_payload(page_state)
    context = _build_economic_charts_template_context(page_state, panel_payload)
    return render(request, "data_visualization/economic_charts.html", context)
