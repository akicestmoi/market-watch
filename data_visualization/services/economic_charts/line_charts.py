"""Line-chart payloads: windowing, Cross-Region alignment, and cached plot data."""

from datetime import date
from typing import NamedTuple, TypedDict

from dateutil.relativedelta import relativedelta
from django.db.models import Q
from pydantic import TypeAdapter

from core.services.time_series_calculation import TimeSeriesPoint
from data_visualization.services.cache import (
    EconomicDisplayCacheType,
    get_cached_economic_display,
    set_cached_economic_display,
)
from data_visualization.services.config import (
    CHART_PERIOD_WINDOW_YEARS,
    CROSS_REGION_PREFERRED_INDICATORS_FOR_LINE_CHART_COMPARISON,
    CROSS_REGION_TIME_SERIES_ALIGNMENT_FOR_LINE_CHART_COMPARISON,
    ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS,
    YTD_CHART_MODES,
    ChartPeriodWindow,
    CrossRegionTimeSeriesAlignment,
)
from data_visualization.services.economic_charts.indicator_selection import (
    CategorySubcategoryPair,
    SelectedIndicatorsByCategorySubcategory,
    get_indicator_for_line_chart_comparison,
    list_category_subcategory_pairs,
)
from data_visualization.services.economic_recap.table_content import (
    format_amount_unit_label,
    get_indicator_price_basis,
)
from data_visualization.services.time_series import (
    build_vs_gdp_time_series,
    build_year_to_date_cumulative_time_series,
    build_ytd_vs_gdp_time_series,
    build_ytd_yoy_time_series,
    change_series_mode,
    collapse_ytd_time_series_to_annual_points,
    convert_points_to_period_level,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
    IndicatorMeasureTypeChoices,
    IndicatorPriceBasisChoices,
)
from economic_overview.services.config import ANNUALIZED_ABS_LEVEL_TICKERS


def _get_quarter_start(period: date) -> date:
    """Return the first day of the calendar quarter that contains 'period'."""
    quarter_month = ((period.month - 1) // 3) * 3 + 1
    return date(period.year, quarter_month, 1)


def format_period(
    period_date: date, frequency: EconomicPublicationFrequencyChoices
) -> str:
    """Return the axis label for one period at the series publication frequency."""
    if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
        return period_date.strftime("%Y-%m")
    if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
        quarter = (period_date.month - 1) // 3 + 1
        return f"{period_date.year}Q{quarter}"
    if frequency == EconomicPublicationFrequencyChoices.ANNUAL:
        return str(period_date.year)
    return period_date.isoformat()


def _format_series_legend_label(
    indicator: EconomicIndicatorInformationModel,
    mode: IndicatorDisplayModeChoices,
    *,
    include_location: bool = False,
) -> str:
    """Return the series legend label.

    A short mode tag is appended when the mode is not Raw.

    Raw keeps the bare display name (index base-year paren when present). Percent
    and amount units stay off the name (Y-axis / tooltips carry them). Growth
    modes use the plain type. When 'include_location' is true, prefix with the
    country display label so multi-country series stay distinct.
    """
    if mode in {
        IndicatorDisplayModeChoices.RAW,
        IndicatorDisplayModeChoices.VS_GDP,
    }:
        base_label = indicator.get_display_name()
    else:
        base_label = indicator.series_label
    # Raw keeps the bare name; every other mode appends its choice value.
    labeled = (
        base_label
        if mode == IndicatorDisplayModeChoices.RAW
        else f"{base_label} ({mode.value})"
    )
    if not include_location:
        return labeled
    location_label = str(EconomicDataLocationChoices(indicator.location).label)
    return f"{location_label} — {labeled}"


def filter_time_series_by_period_window(
    time_series: list[TimeSeriesPoint],
    period_window: ChartPeriodWindow,
) -> list[TimeSeriesPoint]:
    """Drop points older than the window before the latest period, or keep all for Max."""
    if not time_series:
        return []
    history_years = CHART_PERIOD_WINDOW_YEARS[period_window]
    if history_years is None:
        return time_series
    max_period = max(point.period for point in time_series)
    # Approximate year cutoff: same month and day, that many years earlier.
    try:
        cutoff = max_period.replace(year=max_period.year - history_years)
    except ValueError:
        # 29 February becomes 28 February when the earlier year is not a leap year.
        cutoff = max_period.replace(
            month=2, day=28, year=max_period.year - history_years
        )
    return [point for point in time_series if point.period >= cutoff]


def _format_value_axis_label(
    *,
    mode: IndicatorDisplayModeChoices,
    base_unit: IndicatorBaseUnitChoices | None = None,
    base_currency: IndicatorBaseCurrencyChoices | None = None,
    price_basis: IndicatorPriceBasisChoices | None = None,
    base_year: int | None = None,
) -> str:
    """Return the Y-axis title for one economic chart series.

    Prefer the unit wording alone ('%', 'in b€', '% of nominal GDP'). Index
    series use 'Index Level' with the base year when it is known. Levels with
    no amount or index unit keep 'Data Value'.
    """
    if mode in {
        IndicatorDisplayModeChoices.VS_GDP,
        IndicatorDisplayModeChoices.YTD_VS_GDP,
    }:
        if price_basis == IndicatorPriceBasisChoices.REAL:
            return "% of real GDP"
        return "% of nominal GDP"
    if (
        mode
        not in {
            IndicatorDisplayModeChoices.RAW,
            IndicatorDisplayModeChoices.YTD_RAW,
        }
        or base_unit == IndicatorBaseUnitChoices.PERCENT
    ):
        if (
            base_unit == IndicatorBaseUnitChoices.PERCENT
            and price_basis == IndicatorPriceBasisChoices.NOMINAL
        ):
            return "% of nominal GDP"
        if (
            base_unit == IndicatorBaseUnitChoices.PERCENT
            and price_basis == IndicatorPriceBasisChoices.REAL
        ):
            return "% of real GDP"
        return "%"
    if base_unit == IndicatorBaseUnitChoices.INDEX:
        if base_year is not None:
            return f"Index Level (base year: {base_year})"
        return "Index Level"
    if base_unit in {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }:
        unit_label = format_amount_unit_label(
            IndicatorAmountMagnitudeChoices(base_unit),
            base_currency,
        )
        return f"in {unit_label}"
    return "Data Value"


def _get_value_axis_label(
    axis_labels: list[str],
) -> str:
    """Return the shared axis title when all series agree; otherwise 'Data Value'."""
    unique_labels = list(dict.fromkeys(axis_labels))
    if len(unique_labels) == 1:
        # All series share one axis title; index 0 is that shared label.
        return unique_labels[0]
    return "Data Value"


def _extract_unit_label_from_axis_label(axis_label: str) -> str:
    """Pull the compact unit fragment out of a Y-axis title for tooltips."""
    if not axis_label or axis_label == "Data Value":
        return ""
    if axis_label.startswith("Index Level"):
        return ""
    return axis_label


def _parse_base_unit(base_unit: str) -> IndicatorBaseUnitChoices | None:
    """Return the stored unit as an enum, or None when the series has no unit."""
    if not base_unit:
        return None
    return IndicatorBaseUnitChoices(base_unit)


def _parse_base_currency(base_currency: str) -> IndicatorBaseCurrencyChoices | None:
    """Return the stored currency as an enum, or None when the series has none."""
    if not base_currency:
        return None
    return IndicatorBaseCurrencyChoices(base_currency)


def get_time_series_by_indicator_id(
    indicators: list[EconomicIndicatorInformationModel],
) -> dict[int, list[TimeSeriesPoint]]:
    """Fetch raw absolute time series from the DB, keyed by indicator id.

    Keying by id (not name) avoids merging points when two indicators share a name.
    """
    # Usage of dict: keys are runtime indicator ids from the DB query.
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]] = {
        indicator.id: [] for indicator in indicators
    }
    if not indicators:
        return time_series_by_indicator_id

    for economic_data_value in (
        EconomicDataModel.objects.filter(
            indicator_id__in=time_series_by_indicator_id.keys(),
            period__isnull=False,
            data_value__isnull=False,
        )
        .select_related("indicator")
        .order_by("period")
    ):
        time_series_by_indicator_id[economic_data_value.indicator.pk].append(
            TimeSeriesPoint(
                period=economic_data_value.period,
                value=float(economic_data_value.data_value),
            )
        )
    return time_series_by_indicator_id


def aggregate_monthly_points_to_quarterly_mean(
    points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Average monthly values into one point per calendar quarter (quarter start).

    Partial quarters keep the mean of the months that are already available.
    """
    if not points:
        return []
    # Usage of dict: quarter-start → monthly values inside that quarter.
    values_by_quarter: dict[date, list[float]] = {}
    for point in points:
        quarter_start = _get_quarter_start(point.period)
        values_by_quarter.setdefault(quarter_start, []).append(point.value)
    return [
        TimeSeriesPoint(
            period=quarter_start,
            value=sum(quarter_values) / len(quarter_values),
        )
        for quarter_start, quarter_values in sorted(values_by_quarter.items())
    ]


def interpolate_points_to_monthly(
    points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Linearly fill month-start points between sparse observation dates."""
    if not points:
        return []
    ordered_points = sorted(points, key=lambda point: point.period)
    if len(ordered_points) == 1:
        # A single observation is repeated at its month start; no span to interpolate.
        only_point = ordered_points[0]
        return [
            TimeSeriesPoint(
                period=date(only_point.period.year, only_point.period.month, 1),
                value=only_point.value,
            )
        ]
    # Usage of dict: month-start → observed or interpolated value.
    value_by_month: dict[date, float] = {}
    for left_index in range(len(ordered_points) - 1):
        left_point = ordered_points[left_index]
        right_point = ordered_points[left_index + 1]
        left_month = date(left_point.period.year, left_point.period.month, 1)
        right_month = date(right_point.period.year, right_point.period.month, 1)
        value_by_month[left_month] = left_point.value
        months_between = (right_month.year - left_month.year) * 12 + (
            right_month.month - left_month.month
        )
        if months_between <= 0:
            continue
        for step in range(1, months_between):
            month_period = left_month + relativedelta(months=step)
            weight = step / months_between
            value_by_month[month_period] = (
                left_point.value + (right_point.value - left_point.value) * weight
            )
        value_by_month[right_month] = right_point.value
    return [
        TimeSeriesPoint(period=month_period, value=month_value)
        for month_period, month_value in sorted(value_by_month.items())
    ]


class _AlignedCrossRegionSeries(NamedTuple):
    """Cross-Region points after frequency alignment, and the frequency they use."""

    points: list[TimeSeriesPoint]
    frequency: EconomicPublicationFrequencyChoices


def align_cross_region_time_series(
    points: list[TimeSeriesPoint],
    *,
    source_frequency: EconomicPublicationFrequencyChoices,
    series_label: str,
) -> _AlignedCrossRegionSeries:
    """Align points to a shared cadence for Cross-Region line-chart comparison."""
    alignment = CROSS_REGION_TIME_SERIES_ALIGNMENT_FOR_LINE_CHART_COMPARISON.get(
        series_label
    )
    if alignment is None:
        return _AlignedCrossRegionSeries(points=points, frequency=source_frequency)
    match alignment:
        case CrossRegionTimeSeriesAlignment.MEAN:
            if source_frequency != EconomicPublicationFrequencyChoices.MONTHLY:
                return _AlignedCrossRegionSeries(
                    points=points, frequency=source_frequency
                )
            return _AlignedCrossRegionSeries(
                points=aggregate_monthly_points_to_quarterly_mean(points),
                frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            )
        case CrossRegionTimeSeriesAlignment.LINEAR_INTERPOLATION:
            if source_frequency == EconomicPublicationFrequencyChoices.MONTHLY:
                return _AlignedCrossRegionSeries(
                    points=points, frequency=source_frequency
                )
            return _AlignedCrossRegionSeries(
                points=interpolate_points_to_monthly(points),
                frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            )


# Series labels used as the vsGDP denominator (hidden nominal, visible real).
_NOMINAL_GDP_SERIES_LABEL = "Nominal GDP"
_REAL_GDP_SERIES_LABEL = "Real GDP"


class _SelectedIndicatorAndMode(TypedDict):
    """One selected series label with its Raw/QoQ/YoY mode and optional country."""

    series_label: str  # Indicator type display label from the UI
    mode: IndicatorDisplayModeChoices
    location: EconomicDataLocationChoices | None


def _parse_selected_indicator_and_mode(
    raw_selection: str,
) -> _SelectedIndicatorAndMode:
    """Parse '[Location|]Type[|MODE]' into type, mode, and an optional location."""
    selection_text = (raw_selection or "").strip()
    if not selection_text:
        return _SelectedIndicatorAndMode(
            series_label="", mode=IndicatorDisplayModeChoices.RAW, location=None
        )

    tokens = [token.strip() for token in selection_text.split("|") if token.strip()]
    location_values = {choice.value for choice in EconomicDataLocationChoices}
    mode_values = {mode.value for mode in IndicatorDisplayModeChoices}

    location: EconomicDataLocationChoices | None = None
    # Selection may start with a location (e.g. FR|GDP|YOY); index 0 is that location.
    if tokens and tokens[0] in location_values:
        location = EconomicDataLocationChoices(tokens.pop(0))

    mode = IndicatorDisplayModeChoices.RAW
    # Selection may end with a display mode; index -1 is that mode when present.
    if tokens and tokens[-1] in mode_values:
        mode = IndicatorDisplayModeChoices(tokens.pop(-1))

    if len(tokens) != 1:
        raise ValueError(f"Invalid indicator selection: {raw_selection}")
    # What remains after removing optional location and mode is the series label.
    return _SelectedIndicatorAndMode(
        series_label=tokens[0], mode=mode, location=location
    )


class _SelectedIndicatorAndModeWithLocation(NamedTuple):
    """Selected indicator+mode with the concrete location whose series to load."""

    selected_indicator_and_mode: _SelectedIndicatorAndMode
    location: EconomicDataLocationChoices


class _IndicatorLocationTypeKey(NamedTuple):
    """Lookup key for an indicator by location code and type."""

    location: str
    series_label: str


def _attach_series_locations_to_selected_indicators_and_modes(
    region: EconomicDataLocationChoices | None,
    selected_indicators_and_modes: list[_SelectedIndicatorAndMode],
    *,
    cross_region: bool,
    countries: list[EconomicDataLocationChoices] | None = None,
) -> list[_SelectedIndicatorAndModeWithLocation]:
    """Return the DB location to load for each selected indicator+mode.

    Single-region uses the page region when the selection has no country.
    Cross-Region expands generic 'Type|MODE' selections across 'countries'
    (default: every Cross-Region location). Selections that already start with
    a location code (e.g. 'FR|GDP|YOY') keep that country when it is still in
    the active country set.
    """
    active_countries = (
        list(countries)
        if countries is not None
        else list(ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS)
    )
    active_country_codes = {country.value for country in active_countries}
    with_locations: list[_SelectedIndicatorAndModeWithLocation] = []
    for selected_indicator_and_mode in selected_indicators_and_modes:
        series_location = selected_indicator_and_mode["location"]
        if series_location is None:
            if cross_region:
                for country in active_countries:
                    with_locations.append(
                        _SelectedIndicatorAndModeWithLocation(
                            selected_indicator_and_mode=selected_indicator_and_mode,
                            location=country,
                        )
                    )
                continue
            assert region is not None
            series_location = region
        elif cross_region and series_location.value not in active_country_codes:
            continue
        with_locations.append(
            _SelectedIndicatorAndModeWithLocation(
                selected_indicator_and_mode=selected_indicator_and_mode,
                location=series_location,
            )
        )
    return with_locations


class ChartDataPoint(TypedDict):
    """One plotted point on an economic chart."""

    period: str  # Display period label for the chart axis
    data_value: float
    indicator_name: str  # Series legend / indicator display label
    unit_label: str  # Compact unit for hover tooltips


class _CategoryChartSeries(NamedTuple):
    """Chart points plus the shared y-axis label for one category."""

    category_data: list[ChartDataPoint]
    value_axis_label: str


class GdpSeriesMeta(NamedTuple):
    """Ticker and stored unit for one location's GDP series."""

    ticker: str
    base_unit: IndicatorBaseUnitChoices | None


class _GdpSeriesForLocation(NamedTuple):
    """GDP points and ticker/unit meta for one location."""

    points: list[TimeSeriesPoint]
    meta: GdpSeriesMeta


class _GdpSeriesMaps(NamedTuple):
    """Nominal and real GDP series keyed by location for vsGDP modes."""

    # Usage of dict: location code → Nominal GDP points.
    nominal_series_by_location: dict[str, list[TimeSeriesPoint]]
    # Usage of dict: location code → Nominal GDP ticker and unit.
    nominal_meta_by_location: dict[str, GdpSeriesMeta]
    # Usage of dict: location code → Real GDP points.
    real_series_by_location: dict[str, list[TimeSeriesPoint]]
    # Usage of dict: location code → Real GDP ticker and unit.
    real_meta_by_location: dict[str, GdpSeriesMeta]


_EMPTY_GDP_SERIES_MAPS = _GdpSeriesMaps(
    nominal_series_by_location={},
    nominal_meta_by_location={},
    real_series_by_location={},
    real_meta_by_location={},
)


class _DisplayModeTimeSeries(NamedTuple):
    """Points after vsGDP / YTD transforms, and the frequency to plot them at."""

    points: list[TimeSeriesPoint]
    frequency: EconomicPublicationFrequencyChoices


def _get_gdp_series_for_location(
    location_code: str,
    price_basis: IndicatorPriceBasisChoices | None,
    gdp_series_maps: _GdpSeriesMaps,
) -> _GdpSeriesForLocation:
    """Return the matching Nominal or Real GDP series for one location."""
    missing_gdp_series_meta = GdpSeriesMeta(ticker="", base_unit=None)
    if price_basis == IndicatorPriceBasisChoices.REAL:
        return _GdpSeriesForLocation(
            points=gdp_series_maps.real_series_by_location.get(location_code, []),
            meta=gdp_series_maps.real_meta_by_location.get(
                location_code, missing_gdp_series_meta
            ),
        )
    return _GdpSeriesForLocation(
        points=gdp_series_maps.nominal_series_by_location.get(location_code, []),
        meta=gdp_series_maps.nominal_meta_by_location.get(
            location_code, missing_gdp_series_meta
        ),
    )


def _get_required_gdp_base_unit(
    gdp_series: _GdpSeriesForLocation,
    *,
    location_code: str,
) -> IndicatorBaseUnitChoices:
    """Return the GDP series unit, or raise when it is missing."""
    gdp_unit = gdp_series.meta.base_unit
    if gdp_unit is None:
        raise ValueError(
            f"GDP base_unit is missing for location {location_code!r} "
            f"(ticker={gdp_series.meta.ticker!r})."
        )
    return gdp_unit


def _get_time_series_for_vs_gdp_display_mode(
    source_points: list[TimeSeriesPoint],
    *,
    indicator: EconomicIndicatorInformationModel,
    frequency: EconomicPublicationFrequencyChoices,
    location_code: str,
    gdp_series_maps: _GdpSeriesMaps,
) -> _DisplayModeTimeSeries:
    """Return outstanding / GDP points for vsGDP mode."""
    gdp_series = _get_gdp_series_for_location(
        location_code,
        get_indicator_price_basis(indicator.series_label),
        gdp_series_maps,
    )
    return _DisplayModeTimeSeries(
        points=build_vs_gdp_time_series(
            source_points,
            outstanding_ticker=indicator.ticker,
            outstanding_unit=_parse_base_unit(indicator.base_unit),
            outstanding_measure_type=IndicatorMeasureTypeChoices(
                indicator.measure_type
            ),
            outstanding_frequency=frequency,
            gdp_points=gdp_series.points,
            gdp_ticker=gdp_series.meta.ticker,
            gdp_unit=_get_required_gdp_base_unit(
                gdp_series, location_code=location_code
            ),
        ),
        frequency=frequency,
    )


def _get_time_series_for_ytd_display_mode(
    source_points: list[TimeSeriesPoint],
    *,
    indicator: EconomicIndicatorInformationModel,
    mode: IndicatorDisplayModeChoices,
    frequency: EconomicPublicationFrequencyChoices,
    location_code: str,
    gdp_series_maps: _GdpSeriesMaps,
) -> _DisplayModeTimeSeries:
    """Return year-to-date points (cumulative, vsGDP, or YoY) as annual series."""
    period_level_points = convert_points_to_period_level(
        source_points,
        is_annualized=indicator.ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
    )
    if mode == IndicatorDisplayModeChoices.YTD_VS_GDP:
        if indicator.base_unit == IndicatorBaseUnitChoices.PERCENT:
            ytd_points = build_year_to_date_cumulative_time_series(
                period_level_points, frequency=frequency
            )
        else:
            if not indicator.base_unit:
                raise ValueError(
                    f"Indicator base_unit is missing for YTD vs GDP "
                    f"(ticker={indicator.ticker!r})."
                )
            gdp_series = _get_gdp_series_for_location(
                location_code,
                get_indicator_price_basis(indicator.series_label),
                gdp_series_maps,
            )
            ytd_points = build_ytd_vs_gdp_time_series(
                source_points,
                outstanding_ticker=indicator.ticker,
                outstanding_unit=indicator.base_unit,
                outstanding_frequency=frequency,
                gdp_points=gdp_series.points,
                gdp_ticker=gdp_series.meta.ticker,
                gdp_unit=_get_required_gdp_base_unit(
                    gdp_series, location_code=location_code
                ),
            )
    else:
        ytd_points = build_year_to_date_cumulative_time_series(
            period_level_points, frequency=frequency
        )
    # YTDYoY compares each cumulative value to the same period a year earlier,
    # then collapses to one point per calendar year for the annual axis.
    if mode == IndicatorDisplayModeChoices.YTD_YOY:
        return _DisplayModeTimeSeries(
            points=collapse_ytd_time_series_to_annual_points(
                build_ytd_yoy_time_series(ytd_points)
            ),
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
    # YTD modes always plot one point per calendar year on the X-axis.
    return _DisplayModeTimeSeries(
        points=collapse_ytd_time_series_to_annual_points(ytd_points),
        frequency=EconomicPublicationFrequencyChoices.ANNUAL,
    )


def _get_time_series_for_display_mode(
    source_points: list[TimeSeriesPoint],
    *,
    indicator: EconomicIndicatorInformationModel,
    mode: IndicatorDisplayModeChoices,
    frequency: EconomicPublicationFrequencyChoices,
    location_code: str,
    gdp_series_maps: _GdpSeriesMaps,
) -> _DisplayModeTimeSeries:
    """Apply vsGDP / YTD transforms for one series before period-window filtering."""
    if (
        mode == IndicatorDisplayModeChoices.VS_GDP
        and indicator.base_unit != IndicatorBaseUnitChoices.PERCENT
    ):
        return _get_time_series_for_vs_gdp_display_mode(
            source_points,
            indicator=indicator,
            frequency=frequency,
            location_code=location_code,
            gdp_series_maps=gdp_series_maps,
        )
    if mode in YTD_CHART_MODES:
        return _get_time_series_for_ytd_display_mode(
            source_points,
            indicator=indicator,
            mode=mode,
            frequency=frequency,
            location_code=location_code,
            gdp_series_maps=gdp_series_maps,
        )
    return _DisplayModeTimeSeries(points=source_points, frequency=frequency)


def _format_chart_series_legend_label(
    indicator: EconomicIndicatorInformationModel,
    mode: IndicatorDisplayModeChoices,
    detailed_selection: list[_SelectedIndicatorAndModeWithLocation],
    *,
    legend_location_only: bool,
) -> str:
    """Return the legend label for one plotted series."""
    if legend_location_only:
        return str(EconomicDataLocationChoices(indicator.location).label)
    return _format_series_legend_label(
        indicator,
        mode,
        include_location=len({entry.location for entry in detailed_selection}) > 1,
    )


def _get_aligned_source_points_for_chart(
    source_points: list[TimeSeriesPoint],
    *,
    frequency: EconomicPublicationFrequencyChoices,
    series_label: str,
    legend_location_only: bool,
) -> _DisplayModeTimeSeries:
    """Align Cross-Region cadences when needed; otherwise return points unchanged."""
    if not legend_location_only:
        return _DisplayModeTimeSeries(points=source_points, frequency=frequency)
    aligned_series = align_cross_region_time_series(
        source_points,
        source_frequency=frequency,
        series_label=series_label,
    )
    return _DisplayModeTimeSeries(
        points=aligned_series.points, frequency=aligned_series.frequency
    )


class _SelectionChartPoints(NamedTuple):
    """Plotted points and Y-axis label for one selected series."""

    chart_data_points: list[ChartDataPoint]
    series_axis_label: str


def _list_windowed_chart_data_points(
    display_mode_time_series: _DisplayModeTimeSeries,
    *,
    mode: IndicatorDisplayModeChoices,
    period_window: ChartPeriodWindow,
    series_legend_label: str,
    series_unit_label: str,
) -> list[ChartDataPoint]:
    """Apply mode change and period window, then format chart data points."""
    time_series_in_period_window = filter_time_series_by_period_window(
        change_series_mode(
            display_mode_time_series.points,
            display_mode_time_series.frequency,
            mode,
        ),
        period_window,
    )
    return [
        ChartDataPoint(
            period=format_period(point.period, display_mode_time_series.frequency),
            data_value=point.value,
            indicator_name=series_legend_label,
            unit_label=series_unit_label,
        )
        for point in time_series_in_period_window
    ]


def _get_indicator_for_chart_selection(
    selection_with_location: _SelectedIndicatorAndModeWithLocation,
    indicator_by_location_and_series_label: dict[
        _IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ],
) -> EconomicIndicatorInformationModel | None:
    """Return the chart indicator for one selection, or None when missing."""
    selected = selection_with_location.selected_indicator_and_mode
    return indicator_by_location_and_series_label.get(
        _IndicatorLocationTypeKey(
            location=selection_with_location.location.value,
            series_label=selected["series_label"],
        )
    )


def _format_indicator_value_axis_label(
    indicator: EconomicIndicatorInformationModel,
    mode: IndicatorDisplayModeChoices,
) -> str:
    """Return the Y-axis title for one indicator and display mode."""
    return _format_value_axis_label(
        mode=mode,
        base_unit=_parse_base_unit(indicator.base_unit),
        base_currency=_parse_base_currency(indicator.base_currency),
        price_basis=get_indicator_price_basis(indicator.series_label),
        base_year=indicator.base_year,
    )


def _list_chart_data_points_for_selection(
    selection_with_location: _SelectedIndicatorAndModeWithLocation,
    *,
    indicator_by_location_and_series_label: dict[
        _IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    period_window: ChartPeriodWindow,
    gdp_series_maps: _GdpSeriesMaps,
    detailed_selection: list[_SelectedIndicatorAndModeWithLocation],
    legend_location_only: bool,
) -> _SelectionChartPoints | None:
    """Return plotted points and the Y-axis label for one selection, or None."""
    indicator = _get_indicator_for_chart_selection(
        selection_with_location, indicator_by_location_and_series_label
    )
    if indicator is None:
        return None
    mode = selection_with_location.selected_indicator_and_mode["mode"]
    series_axis_label = _format_indicator_value_axis_label(indicator, mode)
    aligned_source = _get_aligned_source_points_for_chart(
        time_series_by_indicator_id.get(indicator.id, []),
        frequency=EconomicPublicationFrequencyChoices(indicator.frequency),
        series_label=indicator.series_label,
        legend_location_only=legend_location_only,
    )
    display_mode_time_series = _get_time_series_for_display_mode(
        aligned_source.points,
        indicator=indicator,
        mode=mode,
        frequency=aligned_source.frequency,
        location_code=selection_with_location.location.value,
        gdp_series_maps=gdp_series_maps,
    )
    return _SelectionChartPoints(
        chart_data_points=_list_windowed_chart_data_points(
            display_mode_time_series,
            mode=mode,
            period_window=period_window,
            series_legend_label=_format_chart_series_legend_label(
                indicator,
                mode,
                detailed_selection,
                legend_location_only=legend_location_only,
            ),
            series_unit_label=_extract_unit_label_from_axis_label(series_axis_label),
        ),
        series_axis_label=series_axis_label,
    )


def _build_category_data_points(
    detailed_selection: list[_SelectedIndicatorAndModeWithLocation],
    indicator_by_location_and_series_label: dict[
        _IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ],
    time_series_by_indicator_id: dict[int, list[TimeSeriesPoint]],
    period_window: ChartPeriodWindow,
    gdp_series_maps: _GdpSeriesMaps,
    *,
    legend_location_only: bool = False,
) -> _CategoryChartSeries:
    """Format chart points for every selection after mode and period-window filters."""
    category_data: list[ChartDataPoint] = []
    axis_labels: list[str] = []
    for selection_with_location in detailed_selection:
        selection_chart = _list_chart_data_points_for_selection(
            selection_with_location,
            indicator_by_location_and_series_label=(
                indicator_by_location_and_series_label
            ),
            time_series_by_indicator_id=time_series_by_indicator_id,
            period_window=period_window,
            gdp_series_maps=gdp_series_maps,
            detailed_selection=detailed_selection,
            legend_location_only=legend_location_only,
        )
        if selection_chart is None:
            continue
        axis_labels.append(selection_chart.series_axis_label)
        category_data.extend(selection_chart.chart_data_points)
    category_data.sort(
        key=lambda point: (point["period"], point["indicator_name"]),
        reverse=True,
    )
    return _CategoryChartSeries(
        category_data=category_data,
        value_axis_label=_get_value_axis_label(axis_labels),
    )


class EconomicChartsData(TypedDict):
    """Economic charts data for one category/subcategory chart."""

    category: str  # Display label (Choices.label)
    subcategory: str  # Display label (Choices.label)
    category_data: list[ChartDataPoint]
    value_axis_label: str  # Y-axis title, e.g. "%" / "in b$" / "Index Level"


_CHARTS_CACHE_ADAPTER = TypeAdapter(list[EconomicChartsData])


def _list_parsed_selected_indicators_and_modes(
    selected_raw: list[str],
) -> list[_SelectedIndicatorAndMode]:
    """Parse raw selection strings, dropping blanks."""
    selected_indicators_and_modes: list[_SelectedIndicatorAndMode] = []
    for raw_selection in selected_raw:
        parsed_selection = _parse_selected_indicator_and_mode(raw_selection)
        if parsed_selection["series_label"]:
            selected_indicators_and_modes.append(parsed_selection)
    return selected_indicators_and_modes


def _get_indicator_visibility_filter(*, cross_region: bool) -> Q:
    """Return the ORM visibility filter for chart indicator loading.

    Cross-Region also keeps hidden twins listed for line-chart comparison
    (e.g. France monthly Eurostat unemployment).
    """
    visibility_filter = Q(is_hidden=False)
    if not cross_region:
        return visibility_filter
    preferred_hidden_indicators_filter = Q()
    for (
        preferred_location,
        preferred_category,
        preferred_subcategory,
    ), preferred_full_name in (
        CROSS_REGION_PREFERRED_INDICATORS_FOR_LINE_CHART_COMPARISON.items()
    ):
        preferred_hidden_indicators_filter |= Q(
            is_hidden=True,
            location=preferred_location.value,
            category=preferred_category.value,
            subcategory=preferred_subcategory.value,
            full_name=preferred_full_name,
        )
    return Q(is_hidden=False) | preferred_hidden_indicators_filter


def _get_indicators_by_location_and_series_label(
    indicators: list[EconomicIndicatorInformationModel],
    *,
    cross_region: bool,
) -> dict[_IndicatorLocationTypeKey, EconomicIndicatorInformationModel]:
    """Return one chart indicator per location and series label."""
    # Usage of dict: location×series label → id-ordered candidates.
    candidates_by_location_and_series_label: dict[
        _IndicatorLocationTypeKey, list[EconomicIndicatorInformationModel]
    ] = {}
    for indicator in indicators:
        location_series_key = _IndicatorLocationTypeKey(
            location=indicator.location, series_label=indicator.series_label
        )
        candidates_by_location_and_series_label.setdefault(
            location_series_key, []
        ).append(indicator)
    # Usage of dict: keys are runtime location×series label pairs from the DB query.
    indicator_by_location_and_series_label: dict[
        _IndicatorLocationTypeKey, EconomicIndicatorInformationModel
    ] = {}
    for (
        location_series_key,
        candidates,
    ) in candidates_by_location_and_series_label.items():
        comparison_indicator = get_indicator_for_line_chart_comparison(
            candidates,
            cross_region=cross_region,
        )
        if comparison_indicator is not None:
            indicator_by_location_and_series_label[location_series_key] = (
                comparison_indicator
            )
    return indicator_by_location_and_series_label


class _GdpSeriesMapForLocations(NamedTuple):
    """One GDP series label as points and meta maps keyed by location."""

    # Usage of dict: location code → GDP points.
    series_by_location: dict[str, list[TimeSeriesPoint]]
    # Usage of dict: location code → GDP ticker and unit.
    meta_by_location: dict[str, GdpSeriesMeta]


def _get_one_gdp_series_map_for_locations(
    location_codes: set[str],
    *,
    series_label: str,
    is_hidden: bool,
) -> _GdpSeriesMapForLocations:
    """Load one GDP series label into points and meta maps keyed by location."""
    # Usage of dict: location code → GDP points.
    series_by_location: dict[str, list[TimeSeriesPoint]] = {}
    # Usage of dict: location code → GDP ticker and unit.
    meta_by_location: dict[str, GdpSeriesMeta] = {}
    gdp_indicators = list(
        EconomicIndicatorInformationModel.objects.filter(
            location__in=location_codes,
            series_label=series_label,
            is_hidden=is_hidden,
        ).order_by("id")
    )
    gdp_series_by_id = get_time_series_by_indicator_id(gdp_indicators)
    for gdp_indicator in gdp_indicators:
        series_by_location[gdp_indicator.location] = gdp_series_by_id.get(
            gdp_indicator.id, []
        )
        meta_by_location[gdp_indicator.location] = GdpSeriesMeta(
            ticker=gdp_indicator.ticker,
            base_unit=_parse_base_unit(gdp_indicator.base_unit),
        )
    return _GdpSeriesMapForLocations(
        series_by_location=series_by_location,
        meta_by_location=meta_by_location,
    )


def _get_gdp_series_maps_for_locations(
    location_codes: set[str],
) -> _GdpSeriesMaps:
    """Load Nominal and Real GDP series for the selected locations."""
    nominal_series_by_location, nominal_meta_by_location = (
        _get_one_gdp_series_map_for_locations(
            location_codes,
            series_label=_NOMINAL_GDP_SERIES_LABEL,
            is_hidden=True,
        )
    )
    real_series_by_location, real_meta_by_location = (
        _get_one_gdp_series_map_for_locations(
            location_codes,
            series_label=_REAL_GDP_SERIES_LABEL,
            is_hidden=False,
        )
    )
    return _GdpSeriesMaps(
        nominal_series_by_location=nominal_series_by_location,
        nominal_meta_by_location=nominal_meta_by_location,
        real_series_by_location=real_series_by_location,
        real_meta_by_location=real_meta_by_location,
    )


def _does_selection_need_vs_gdp(
    detailed_selection: list[_SelectedIndicatorAndModeWithLocation],
) -> bool:
    """Return whether any selected mode needs Nominal or Real GDP series."""
    return any(
        selection_with_location.selected_indicator_and_mode["mode"]
        in {
            IndicatorDisplayModeChoices.VS_GDP,
            IndicatorDisplayModeChoices.YTD_VS_GDP,
        }
        for selection_with_location in detailed_selection
    )


def _list_chart_indicators_for_slot(
    *,
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
    selected_locations: set[str],
    selected_series_labels: set[str],
    cross_region: bool,
) -> list[EconomicIndicatorInformationModel]:
    """Load visible (and Cross-Region preferred-hidden) indicators for one slot."""
    return list(
        EconomicIndicatorInformationModel.objects.filter(
            _get_indicator_visibility_filter(cross_region=cross_region),
            category=category.value,
            subcategory=subcategory.value,
            location__in=selected_locations,
            series_label__in=selected_series_labels,
        ).order_by("id")
    )


def _list_detailed_selections_for_chart_slot(
    region: EconomicDataLocationChoices | None,
    selected_raw: list[str],
    *,
    cross_region: bool,
    countries: list[EconomicDataLocationChoices] | None,
) -> list[_SelectedIndicatorAndModeWithLocation]:
    """Parse raw selections and attach the locations whose series to load."""
    selected_indicators_and_modes = _list_parsed_selected_indicators_and_modes(
        selected_raw
    )
    if not selected_indicators_and_modes:
        return []
    if cross_region and len(selected_indicators_and_modes) > 1:
        # Cross-Region shows one series label across countries.
        selected_indicators_and_modes = selected_indicators_and_modes[:1]
    return _attach_series_locations_to_selected_indicators_and_modes(
        region,
        selected_indicators_and_modes,
        cross_region=cross_region,
        countries=countries,
    )


def _get_empty_economic_charts_data(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
) -> EconomicChartsData:
    """Return an empty chart payload for one category and subcategory."""
    return EconomicChartsData(
        category=str(category.label),
        subcategory=str(subcategory.label),
        category_data=[],
        value_axis_label="Data Value",
    )


def _get_economic_charts_data_from_category_series(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
    category_chart_series: _CategoryChartSeries,
) -> EconomicChartsData:
    """Wrap category chart points into the per-slot charts payload."""
    return EconomicChartsData(
        category=str(category.label),
        subcategory=str(subcategory.label),
        category_data=category_chart_series.category_data,
        value_axis_label=category_chart_series.value_axis_label,
    )


def _build_chart_data_for_one_category_subcategory(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
    region: EconomicDataLocationChoices | None,
    selected_raw: list[str],
    period_window: ChartPeriodWindow,
    *,
    cross_region: bool,
    countries: list[EconomicDataLocationChoices] | None = None,
) -> EconomicChartsData:
    """Build the chart series payload for one category and subcategory."""
    empty_chart = _get_empty_economic_charts_data(category, subcategory)
    detailed_selection = _list_detailed_selections_for_chart_slot(
        region, selected_raw, cross_region=cross_region, countries=countries
    )
    if not detailed_selection:
        return empty_chart
    selected_locations = {
        selection_with_location.location.value
        for selection_with_location in detailed_selection
    }
    indicators = _list_chart_indicators_for_slot(
        category=category,
        subcategory=subcategory,
        selected_locations=selected_locations,
        selected_series_labels={
            selection_with_location.selected_indicator_and_mode["series_label"]
            for selection_with_location in detailed_selection
        },
        cross_region=cross_region,
    )
    if not indicators:
        return empty_chart
    indicator_by_key = _get_indicators_by_location_and_series_label(
        indicators, cross_region=cross_region
    )
    gdp_series_maps = (
        _get_gdp_series_maps_for_locations(selected_locations)
        if _does_selection_need_vs_gdp(detailed_selection)
        else _EMPTY_GDP_SERIES_MAPS
    )
    return _get_economic_charts_data_from_category_series(
        category,
        subcategory,
        _build_category_data_points(
            detailed_selection,
            indicator_by_key,
            get_time_series_by_indicator_id(list(indicator_by_key.values())),
            period_window,
            gdp_series_maps,
            legend_location_only=cross_region,
        ),
    )


def _build_charts_cache_fingerprint(
    location_key: str,
    selected_indicators_by_chart: list[SelectedIndicatorsByCategorySubcategory],
    period_window: ChartPeriodWindow,
    *,
    countries_key: str = "",
) -> str:
    """Return a stable cache key for region, countries, selections, and period window."""
    selection_parts: list[str] = []
    for selection in selected_indicators_by_chart:
        category_value = selection["category"].value
        subcategory_value = selection["subcategory"].value
        indicators = ",".join(selection.get("selected_indicators", []))
        selection_parts.append(f"{category_value}:{subcategory_value}:{indicators}")
    selection_parts.sort()
    return (
        f"{location_key}|{countries_key}|{period_window.value}|"
        f"{'|'.join(selection_parts)}"
    )


def _build_economic_charts_data(
    location: EconomicDataLocationChoices | None,
    selected_indicators_by_chart: list[SelectedIndicatorsByCategorySubcategory],
    period_window: ChartPeriodWindow,
    *,
    cross_region: bool,
    countries: list[EconomicDataLocationChoices] | None = None,
) -> list[EconomicChartsData]:
    """Build chart series payloads for every category and subcategory slot."""
    # Usage of dict: keys are category/subcategory pairs from the request.
    selected_raw_by_chart: dict[CategorySubcategoryPair, list[str]] = {
        CategorySubcategoryPair(
            category=selection["category"],
            subcategory=selection["subcategory"],
        ): selection.get("selected_indicators", [])
        for selection in selected_indicators_by_chart
    }
    return [
        _build_chart_data_for_one_category_subcategory(
            category_subcategory_pair.category,
            category_subcategory_pair.subcategory,
            location,
            selected_raw_by_chart.get(category_subcategory_pair, []),
            period_window,
            cross_region=cross_region,
            countries=countries,
        )
        for category_subcategory_pair in list_category_subcategory_pairs()
    ]


def get_economic_charts_data(
    location: EconomicDataLocationChoices | None,
    selected_indicators_by_chart: (
        list[SelectedIndicatorsByCategorySubcategory] | None
    ) = None,
    period_window: ChartPeriodWindow = ChartPeriodWindow.TEN_YEARS,
    *,
    cross_region: bool = False,
    countries: list[EconomicDataLocationChoices] | None = None,
) -> list[EconomicChartsData]:
    """Return economic charts data for every category and subcategory slot.

    Cross-Region expands generic Type|MODE selections across 'countries'. Raw /
    QoQ / YoY transforms are Redis-cached (versioned by table state).
    """
    if selected_indicators_by_chart is None:
        selected_indicators_by_chart = []
    fingerprint_location = (
        "CROSS" if cross_region else (location.value if location is not None else "")
    )
    active_countries = (
        list(countries)
        if countries is not None
        else list(ECONOMIC_CHARTS_CROSS_REGION_LOCATIONS)
    )
    countries_key = (
        ",".join(country.value for country in active_countries) if cross_region else ""
    )
    fingerprint = _build_charts_cache_fingerprint(
        fingerprint_location,
        selected_indicators_by_chart,
        period_window,
        countries_key=countries_key,
    )
    cached_charts_data = get_cached_economic_display(
        EconomicDisplayCacheType.CHARTS, fingerprint, _CHARTS_CACHE_ADAPTER
    )
    if cached_charts_data is not None:
        return cached_charts_data

    economic_charts_data = _build_economic_charts_data(
        location,
        selected_indicators_by_chart,
        period_window,
        cross_region=cross_region,
        countries=active_countries if cross_region else None,
    )
    set_cached_economic_display(
        EconomicDisplayCacheType.CHARTS, fingerprint, economic_charts_data
    )
    return economic_charts_data
