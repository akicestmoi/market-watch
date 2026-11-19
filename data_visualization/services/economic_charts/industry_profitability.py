"""Build industry profitability ranking chart panels for economic charts."""

from enum import Enum
from typing import NamedTuple, TypedDict

from data_visualization.services.config import ChartPeriodWindow
from economic_overview.models.common import (
    INDICATOR_CURRENCY_SYMBOL_BY_CODE,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import EconomicDataCategoryChoices
from economic_overview.models.industry_profitability import (
    IndustryClassificationChoices,
    IndustryProfitabilityModel,
)
from economic_overview.services.config import (
    INDUSTRY_CLASSIFICATION_BY_LOCATION,
    INDUSTRY_CONTRIBUTION_CLASSIFICATION_BY_LOCATION,
    INDUSTRY_PROFITABILITY_CURRENCY_BY_LOCATION,
    INDUSTRY_PROFITABILITY_UNIT_BY_LOCATION,
)

DEFAULT_LINE_TOP_N = 5
DEFAULT_BAR_TOP_N = 20

# Matches ChartPeriodWindow history length (None = Max / all available years).
_LINE_CHART_HISTORY_YEARS_BY_PERIOD_WINDOW: dict[ChartPeriodWindow, int | None] = {
    ChartPeriodWindow.ONE_YEAR: 1,
    ChartPeriodWindow.THREE_YEARS: 3,
    ChartPeriodWindow.FIVE_YEARS: 5,
    ChartPeriodWindow.TEN_YEARS: 10,
    ChartPeriodWindow.MAX: None,
}

_VALUE_AXIS_MAGNITUDE_BY_UNIT: dict[IndicatorBaseUnitChoices, str] = {
    IndicatorBaseUnitChoices.K: "k",
    IndicatorBaseUnitChoices.M: "m",
    IndicatorBaseUnitChoices.B: "b",
}

_JP_DUAL_CLASSIFICATION_WARNING = (
    "Japan Contribution uses ESRI SNA economic-activity GVA; Turnover, "
    "Operating Profit, and Margin use the MOF corporate survey industry map. "
    "The two industry maps are not the same."
)


class IndustryProfitabilityRankBy(str, Enum):
    """Metric used to rank industries on the profitability charts."""

    TURNOVER = "turnover"
    OPERATING_PROFIT = "operating_profit"
    MARGIN = "margin"
    GVA = "gva"


_PROFITABILITY_LABEL_FOR_UI_RANKING: dict[IndustryProfitabilityRankBy, str] = {
    IndustryProfitabilityRankBy.TURNOVER: "Turnover",
    IndustryProfitabilityRankBy.OPERATING_PROFIT: "Operating Profit",
    IndustryProfitabilityRankBy.MARGIN: "Margin",
    IndustryProfitabilityRankBy.GVA: "GVA",
}


class IndustryProfitabilityRankByOption(TypedDict):
    """One selectable rank-by option for the charts UI."""

    value: str
    label: str


class IndustryProfitabilityObservation(TypedDict):
    """One industry-year figure with ranking metrics for client-side charts."""

    industry_code: str
    industry_label: str
    year: int
    turnover: float | None
    operating_profit: float | None
    gva: float | None
    margin: float | None


class IndustryProfitabilityPoint(TypedDict):
    """One chart point for an industry profitability series."""

    period: str
    data_value: float
    indicator_name: str
    unit_label: str


class IndustryProfitabilityPanel(TypedDict):
    """Line + bar payloads for one location's industry profitability rankings."""

    category: str
    panel_id: str
    line_title: str
    bar_title: str
    location: str
    classification_label: str
    contribution_classification_label: str
    source_label: str
    contribution_source_label: str
    as_of_year: int
    available_years: list[int]
    line_top_n: int
    bar_top_n: int
    rank_by: str
    rank_by_options: list[IndustryProfitabilityRankByOption]
    observations: list[IndustryProfitabilityObservation]
    contribution_observations: list[IndustryProfitabilityObservation]
    line_data: list[IndustryProfitabilityPoint]
    bar_data: list[IndustryProfitabilityPoint]
    value_axis_label: str
    description: str
    comparability_warning: str


def _format_profitability_value_axis_label(
    location: EconomicDataLocationChoices,
    rank_by: IndustryProfitabilityRankBy,
) -> str:
    """Axis label for the active rank-by metric."""
    if rank_by == IndustryProfitabilityRankBy.MARGIN:
        return "%"

    base_unit = INDUSTRY_PROFITABILITY_UNIT_BY_LOCATION[location]
    base_currency = INDUSTRY_PROFITABILITY_CURRENCY_BY_LOCATION[location]
    magnitude = _VALUE_AXIS_MAGNITUDE_BY_UNIT.get(base_unit, "")
    currency_symbol = INDICATOR_CURRENCY_SYMBOL_BY_CODE.get(
        IndicatorBaseCurrencyChoices(base_currency.value),
        str(base_currency.value),
    )
    return f"{magnitude}{currency_symbol}"


class _ProfitabilityChartTitles(NamedTuple):
    """Line and bar card titles for one rank-by metric."""

    line_title: str
    bar_title: str


def _get_profitability_chart_titles(
    rank_by: IndustryProfitabilityRankBy,
) -> _ProfitabilityChartTitles:
    """Return line and bar titles for the active rank-by metric."""
    metric_label = _PROFITABILITY_LABEL_FOR_UI_RANKING[rank_by]
    return _ProfitabilityChartTitles(
        line_title=f"Industry {metric_label} Trend",
        bar_title=f"Industry {metric_label} Ranking",
    )


def _calculate_profit_margin(
    turnover: float | None,
    operating_profit: float | None,
) -> float | None:
    """Operating profit as a percent of turnover when both prints exist."""
    if turnover is None or operating_profit is None or turnover == 0:
        return None
    return (operating_profit / turnover) * 100.0


def _list_available_years(
    observations: list[IndustryProfitabilityObservation],
) -> list[int]:
    """Distinct years present in observations, newest first."""
    years = sorted(
        {observation["year"] for observation in observations},
        reverse=True,
    )
    return years


def _list_top_industry_labels_for_year(
    observations: list[IndustryProfitabilityObservation],
    as_of_year: int,
    top_n: int,
    rank_by: IndustryProfitabilityRankBy,
) -> list[str]:
    """Industry labels ranked by the active metric in the as-of year."""
    ranked: list[tuple[float, str]] = []
    for observation in observations:
        if observation["year"] != as_of_year:
            continue
        metric_value = observation[rank_by.value]
        if metric_value is None:
            continue
        assert isinstance(metric_value, float)
        ranked.append((metric_value, observation["industry_label"]))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [industry_label for _metric, industry_label in ranked[:top_n]]


def _get_line_chart_period_window_start_year(
    as_of_year: int,
    period_window: ChartPeriodWindow,
) -> int | None:
    """Earliest year included in the line chart (None keeps all years through as-of)."""
    history_years = _LINE_CHART_HISTORY_YEARS_BY_PERIOD_WINDOW[period_window]
    if history_years is None:
        return None
    # Same cutoff rule as economic chart period windows: keep years >= as_of - N.
    return as_of_year - history_years


def _list_line_chart_points(
    observations: list[IndustryProfitabilityObservation],
    *,
    as_of_year: int,
    line_top_n: int,
    period_window: ChartPeriodWindow,
    unit_label: str,
    rank_by: IndustryProfitabilityRankBy,
) -> list[IndustryProfitabilityPoint]:
    """History for industries that rank top-N by the active metric in as-of year."""
    top_labels = _list_top_industry_labels_for_year(
        observations, as_of_year, line_top_n, rank_by
    )
    if not top_labels:
        return []
    top_label_set = set(top_labels)
    line_chart_period_window_start_year = _get_line_chart_period_window_start_year(
        as_of_year, period_window
    )
    line_data: list[IndustryProfitabilityPoint] = []
    for observation in observations:
        if observation["industry_label"] not in top_label_set:
            continue
        if observation["year"] > as_of_year:
            continue
        if (
            line_chart_period_window_start_year is not None
            and observation["year"] < line_chart_period_window_start_year
        ):
            continue
        metric_value = observation[rank_by.value]
        if metric_value is None:
            continue
        assert isinstance(metric_value, float)
        line_data.append(
            IndustryProfitabilityPoint(
                period=str(observation["year"]),
                data_value=metric_value,
                indicator_name=observation["industry_label"],
                unit_label=unit_label,
            )
        )
    line_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return line_data


def _list_bar_chart_points(
    observations: list[IndustryProfitabilityObservation],
    *,
    as_of_year: int,
    bar_top_n: int,
    unit_label: str,
    rank_by: IndustryProfitabilityRankBy,
) -> list[IndustryProfitabilityPoint]:
    """Top-N industries by the active metric for the as-of year (highest first)."""
    top_labels = _list_top_industry_labels_for_year(
        observations, as_of_year, bar_top_n, rank_by
    )
    metric_by_label: dict[str, float] = {}
    for observation in observations:
        if observation["year"] != as_of_year:
            continue
        if observation["industry_label"] not in top_labels:
            continue
        metric_value = observation[rank_by.value]
        if metric_value is None:
            continue
        assert isinstance(metric_value, float)
        metric_by_label[observation["industry_label"]] = metric_value
    bar_data: list[IndustryProfitabilityPoint] = []
    for industry_label in top_labels:
        metric_value = metric_by_label.get(industry_label)
        if metric_value is None:
            continue
        bar_data.append(
            IndustryProfitabilityPoint(
                period=str(as_of_year),
                data_value=metric_value,
                indicator_name=industry_label,
                unit_label=unit_label,
            )
        )
    return bar_data


class _IndustryProfitability(TypedDict):
    """Survey and contribution observations plus source labels for one location."""

    observations: list[IndustryProfitabilityObservation]
    contribution_observations: list[IndustryProfitabilityObservation]
    source_label: str
    contribution_source_label: str


def _list_observations_from_industry_figures(
    industry_figures: list[IndustryProfitabilityModel],
) -> list[IndustryProfitabilityObservation]:
    """Map persisted industry figures into lean chart observations."""
    observations: list[IndustryProfitabilityObservation] = []
    for profitability_figure in industry_figures:
        observations.append(
            IndustryProfitabilityObservation(
                industry_code=profitability_figure.industry_code,
                industry_label=profitability_figure.industry_label,
                year=profitability_figure.period.year,
                turnover=profitability_figure.turnover,
                operating_profit=profitability_figure.operating_profit,
                gva=profitability_figure.gva,
                margin=_calculate_profit_margin(
                    profitability_figure.turnover, profitability_figure.operating_profit
                ),
            )
        )
    return observations


def _get_industry_profitability(
    location: EconomicDataLocationChoices,
) -> _IndustryProfitability:
    """Return survey and contribution observations for one location."""
    survey_classification = INDUSTRY_CLASSIFICATION_BY_LOCATION[location]
    contribution_classification = INDUSTRY_CONTRIBUTION_CLASSIFICATION_BY_LOCATION[
        location
    ]
    survey_figures = list(
        IndustryProfitabilityModel.objects.filter(
            location=location.value,
            classification=survey_classification.value,
        ).order_by("-period", "industry_code")
    )
    if contribution_classification == survey_classification:
        contribution_figures = survey_figures
    else:
        contribution_figures = list(
            IndustryProfitabilityModel.objects.filter(
                location=location.value,
                classification=contribution_classification.value,
            ).order_by("-period", "industry_code")
        )
    observations = _list_observations_from_industry_figures(survey_figures)
    contribution_observations = _list_observations_from_industry_figures(
        contribution_figures
    )
    # Newest-first query, so index 0 is a recent industry-year.
    source_label = (
        str(EconomicDataSourceChoices(survey_figures[0].source).label)
        if survey_figures
        else ""
    )
    contribution_source_label = (
        str(EconomicDataSourceChoices(contribution_figures[0].source).label)
        if contribution_figures
        else source_label
    )
    return _IndustryProfitability(
        observations=observations,
        contribution_observations=contribution_observations,
        source_label=source_label,
        contribution_source_label=contribution_source_label,
    )


def _get_observations_for_rank_by(
    industry_profitability: _IndustryProfitability,
    rank_by: IndustryProfitabilityRankBy,
) -> list[IndustryProfitabilityObservation]:
    """Pick survey vs contribution observation set for the active rank-by."""
    if rank_by == IndustryProfitabilityRankBy.GVA:
        return industry_profitability["contribution_observations"]
    return industry_profitability["observations"]


def _get_effective_as_of_year(
    available_years: list[int],
    as_of_year: int | None,
) -> int:
    """Return the requested as-of year when present, else the newest available year."""
    if as_of_year in available_years:
        return as_of_year
    # Newest year is index 0.
    return available_years[0]


def _format_profitability_panel_description(
    *,
    survey_classification: IndustryClassificationChoices,
    contribution_classification: IndustryClassificationChoices,
    source_label: str,
    contribution_source_label: str,
) -> str:
    """Return the info-panel blurb for one industry profitability card."""
    return (
        "Rank industries by Turnover, Operating Profit, Margin "
        "(operating profit ÷ turnover), or GVA. "
        f"Survey map: {survey_classification.label} ({source_label}). "
        f"Contribution map: {contribution_classification.label} "
        f"({contribution_source_label}). "
        "Single-region only — levels are not cross-country comparable."
    )


def _list_rank_by_options_for_ui() -> list[IndustryProfitabilityRankByOption]:
    """Return rank-by dropdown options with UI labels."""
    return [
        IndustryProfitabilityRankByOption(
            value=option.value,
            label=_PROFITABILITY_LABEL_FOR_UI_RANKING[option],
        )
        for option in IndustryProfitabilityRankBy
    ]


def _get_comparability_warning_for_location(
    location: EconomicDataLocationChoices,
) -> str:
    """Return Japan dual-map warning text, or empty for other locations."""
    if location == EconomicDataLocationChoices.JP:
        return _JP_DUAL_CLASSIFICATION_WARNING
    return ""


def _get_industry_profitability_panel_payload(
    *,
    location: EconomicDataLocationChoices,
    industry_profitability: _IndustryProfitability,
    rank_by: IndustryProfitabilityRankBy,
    effective_as_of_year: int,
    available_years: list[int],
    line_top_n: int,
    bar_top_n: int,
    line_data: list[IndustryProfitabilityPoint],
    bar_data: list[IndustryProfitabilityPoint],
    unit_label: str,
) -> IndustryProfitabilityPanel:
    """Assemble the front payload for one industry profitability card."""
    survey_classification = IndustryClassificationChoices(
        INDUSTRY_CLASSIFICATION_BY_LOCATION[location].value
    )
    contribution_classification = IndustryClassificationChoices(
        INDUSTRY_CONTRIBUTION_CLASSIFICATION_BY_LOCATION[location].value
    )
    chart_titles = _get_profitability_chart_titles(rank_by)
    return IndustryProfitabilityPanel(
        category=str(EconomicDataCategoryChoices.BUSINESS.label),
        panel_id="industry-profitability",
        line_title=chart_titles.line_title,
        bar_title=chart_titles.bar_title,
        location=str(location.label),
        classification_label=str(survey_classification.label),
        contribution_classification_label=str(contribution_classification.label),
        source_label=industry_profitability["source_label"],
        contribution_source_label=industry_profitability["contribution_source_label"],
        as_of_year=effective_as_of_year,
        available_years=available_years,
        line_top_n=line_top_n,
        bar_top_n=bar_top_n,
        rank_by=rank_by.value,
        rank_by_options=_list_rank_by_options_for_ui(),
        observations=industry_profitability["observations"],
        contribution_observations=industry_profitability["contribution_observations"],
        line_data=line_data,
        bar_data=bar_data,
        value_axis_label=unit_label,
        description=_format_profitability_panel_description(
            survey_classification=survey_classification,
            contribution_classification=contribution_classification,
            source_label=industry_profitability["source_label"],
            contribution_source_label=industry_profitability[
                "contribution_source_label"
            ],
        ),
        comparability_warning=_get_comparability_warning_for_location(location),
    )


def _get_industry_profitability_panel(
    location: EconomicDataLocationChoices,
    *,
    period_window: ChartPeriodWindow = ChartPeriodWindow.TEN_YEARS,
    as_of_year: int | None = None,
    line_top_n: int = DEFAULT_LINE_TOP_N,
    bar_top_n: int = DEFAULT_BAR_TOP_N,
    rank_by: IndustryProfitabilityRankBy = IndustryProfitabilityRankBy.TURNOVER,
) -> IndustryProfitabilityPanel | None:
    """Return line + bar panels for one single-region charts location."""
    if location not in INDUSTRY_CLASSIFICATION_BY_LOCATION:
        return None
    industry_profitability = _get_industry_profitability(location)
    ranking_observations = _get_observations_for_rank_by(
        industry_profitability, rank_by
    )
    if not ranking_observations and not industry_profitability["observations"]:
        return None
    available_years = _list_available_years(
        ranking_observations
    ) or _list_available_years(industry_profitability["observations"])
    if not available_years:
        return None
    effective_as_of_year = _get_effective_as_of_year(available_years, as_of_year)
    line_top_n_at_least_one = max(1, line_top_n)
    bar_top_n_at_least_one = max(1, bar_top_n)
    unit_label = _format_profitability_value_axis_label(location, rank_by)
    line_data = _list_line_chart_points(
        ranking_observations,
        as_of_year=effective_as_of_year,
        line_top_n=line_top_n_at_least_one,
        period_window=period_window,
        unit_label=unit_label,
        rank_by=rank_by,
    )
    bar_data = _list_bar_chart_points(
        ranking_observations,
        as_of_year=effective_as_of_year,
        bar_top_n=bar_top_n_at_least_one,
        unit_label=unit_label,
        rank_by=rank_by,
    )
    if not line_data and not bar_data and not industry_profitability["observations"]:
        return None
    return _get_industry_profitability_panel_payload(
        location=location,
        industry_profitability=industry_profitability,
        rank_by=rank_by,
        effective_as_of_year=effective_as_of_year,
        available_years=available_years,
        line_top_n=line_top_n_at_least_one,
        bar_top_n=bar_top_n_at_least_one,
        line_data=line_data,
        bar_data=bar_data,
        unit_label=unit_label,
    )


def get_industry_profitability_panels(
    location: EconomicDataLocationChoices | None,
    *,
    cross_region: bool,
    period_window: ChartPeriodWindow = ChartPeriodWindow.TEN_YEARS,
    as_of_year: int | None = None,
    line_top_n: int = DEFAULT_LINE_TOP_N,
    bar_top_n: int = DEFAULT_BAR_TOP_N,
    rank_by: IndustryProfitabilityRankBy = IndustryProfitabilityRankBy.TURNOVER,
) -> list[IndustryProfitabilityPanel]:
    """Return industry profitability panels for the charts page (none on Cross-Region)."""
    if cross_region or location is None:
        return []
    panel = _get_industry_profitability_panel(
        location,
        period_window=period_window,
        as_of_year=as_of_year,
        line_top_n=line_top_n,
        bar_top_n=bar_top_n,
        rank_by=rank_by,
    )
    if panel is None:
        return []
    return [panel]
