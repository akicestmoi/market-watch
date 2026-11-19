"""Economic display transforms for charts and recap (YTD, vsGDP, MoM/YoY).

Maps publication frequency and indicator display modes onto the generic
helpers in 'core.services.time_series_calculation'.
"""

from datetime import date
from typing import NamedTuple

from core.services.time_series_calculation import (
    TimeSeriesPoint,
    YearToDateStep,
    average_points_by_calendar_year,
    build_percent_change_vs_lookback_period,
    build_ratio_percent_time_series,
    build_same_period_year_over_year_percent_time_series,
)
from core.services.time_series_calculation import (
    build_year_to_date_cumulative_time_series as build_ytd_cumulative_with_step,
)
from core.services.time_series_calculation import (
    collapse_to_latest_point_per_calendar_year,
    convert_annualized_levels_to_period_amounts,
    scale_value_by_thousand_powers,
    sum_points_by_calendar_year,
)
from economic_overview.models.common import (
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
    IndicatorMeasureTypeChoices,
)
from economic_overview.services.config import ANNUALIZED_ABS_LEVEL_TICKERS
from economic_overview.services.economic_data import get_lookback_months_for_mode_change

# YTD ladder step for each publication frequency.
YTD_STEP_BY_FREQUENCY: dict[EconomicPublicationFrequencyChoices, YearToDateStep] = {
    EconomicPublicationFrequencyChoices.MONTHLY: YearToDateStep.MONTHLY,
    EconomicPublicationFrequencyChoices.QUARTERLY: YearToDateStep.QUARTERLY,
    EconomicPublicationFrequencyChoices.ANNUAL: YearToDateStep.ANNUAL,
}

_MODES_WITHOUT_SERIES_TRANSFORM: frozenset[IndicatorDisplayModeChoices] = frozenset(
    {
        IndicatorDisplayModeChoices.RAW,
        IndicatorDisplayModeChoices.VS_GDP,
        IndicatorDisplayModeChoices.YTD_VS_GDP,
        IndicatorDisplayModeChoices.YTD_RAW,
        IndicatorDisplayModeChoices.YTD_YOY,
        IndicatorDisplayModeChoices.REL_QOQ,
        IndicatorDisplayModeChoices.REL_YOY,
        IndicatorDisplayModeChoices.CONTR_QOQ,
        IndicatorDisplayModeChoices.CONTR_YOY,
        IndicatorDisplayModeChoices.YTD_REL_QOQ,
        IndicatorDisplayModeChoices.YTD_REL_YOY,
        IndicatorDisplayModeChoices.YTD_CONTR_QOQ,
        IndicatorDisplayModeChoices.YTD_CONTR_YOY,
    }
)

_AMOUNT_BASE_UNITS: frozenset[str] = frozenset(
    {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }
)


def _get_year_to_date_step(
    frequency: EconomicPublicationFrequencyChoices,
) -> YearToDateStep:
    """Return the YTD ladder step for the indicator publication frequency."""
    return YTD_STEP_BY_FREQUENCY.get(frequency, YearToDateStep.ANNUAL)


def scale_amount_between_magnitudes(
    value: float,
    from_magnitude: IndicatorAmountMagnitudeChoices,
    to_magnitude: IndicatorAmountMagnitudeChoices,
) -> float:
    """Convert an amount between K / M / B / T magnitudes."""
    magnitude_order = IndicatorAmountMagnitudeChoices.ordered()
    return scale_value_by_thousand_powers(
        value,
        power_difference=magnitude_order.index(from_magnitude)
        - magnitude_order.index(to_magnitude),
    )


def convert_points_to_period_level(
    points: list[TimeSeriesPoint],
    *,
    is_annualized: bool,
) -> list[TimeSeriesPoint]:
    """Turn SAAR / annualized quarterly levels into one-period amounts (÷4)."""
    if not is_annualized:
        return points
    return convert_annualized_levels_to_period_amounts(points, periods_per_year=4)


def change_series_mode(
    points: list[TimeSeriesPoint],
    frequency: EconomicPublicationFrequencyChoices,
    mode: IndicatorDisplayModeChoices,
) -> list[TimeSeriesPoint]:
    """Change a raw absolute time series to Raw / MoM / QoQ / QoQy / YoY.

    Callers that want vsGDP must pass an already-scaled share series;
    those modes are treated like Raw (identity on the incoming points).
    """
    if not points:
        return []
    ordered_points = sorted(points, key=lambda point: point.period)
    if mode in _MODES_WITHOUT_SERIES_TRANSFORM:
        # Rel / Contr need a parent series; charts keep Raw levels for those modes.
        # YTD modes are pre-transformed by the caller before this helper runs.
        return ordered_points
    lookback_months = get_lookback_months_for_mode_change(frequency, mode)
    if lookback_months <= 0:
        return ordered_points
    annualized_ratio = (
        4.0 if mode == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER else None
    )
    return build_percent_change_vs_lookback_period(
        ordered_points,
        lookback_months=lookback_months,
        annualized_ratio=annualized_ratio,
    )


def build_year_to_date_cumulative_time_series(
    points: list[TimeSeriesPoint],
    *,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[TimeSeriesPoint]:
    """Return running calendar year-to-date sums for the indicator frequency."""
    return build_ytd_cumulative_with_step(
        points, step=_get_year_to_date_step(frequency)
    )


def collapse_ytd_time_series_to_annual_points(
    ytd_points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Return the latest year-to-date total of each calendar year on an annual axis."""
    return collapse_to_latest_point_per_calendar_year(ytd_points)


def build_ytd_yoy_time_series(
    ytd_points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Return YoY of year-to-date levels vs the same period prior year."""
    return build_same_period_year_over_year_percent_time_series(ytd_points)


def _required_observations_for_complete_calendar_year(
    period_points: list[TimeSeriesPoint],
) -> int | None:
    """Infer 4 (quarterly) or 12 (monthly) complete-year observation counts."""
    # Usage of dict: calendar year → number of intra-year observations.
    observation_count_by_year: dict[int, int] = {}
    for point in period_points:
        observation_count_by_year[point.period.year] = (
            observation_count_by_year.get(point.period.year, 0) + 1
        )
    observation_counts = list(observation_count_by_year.values())
    if 4 in observation_counts:
        return 4
    if 12 in observation_counts:
        return 12
    return None


class _VsGdpDenominatorContext(NamedTuple):
    """GDP points aligned to the outstanding series for vsGDP division."""

    matched_gdp_points: list[TimeSeriesPoint]
    gdp_annualized: bool
    outstanding_annual_scale: bool
    outstanding_is_stock: bool
    use_calendar_year_gdp: bool


def _get_vs_gdp_denominator_context(
    *,
    outstanding_ticker: str,
    outstanding_measure_type: IndicatorMeasureTypeChoices,
    outstanding_frequency: EconomicPublicationFrequencyChoices,
    gdp_points: list[TimeSeriesPoint],
    gdp_ticker: str,
) -> _VsGdpDenominatorContext:
    """Choose GDP alignment and annualization flags for outstanding / GDP."""
    outstanding_is_stock = outstanding_measure_type == IndicatorMeasureTypeChoices.STOCK
    outstanding_is_annual_frequency = (
        outstanding_frequency == EconomicPublicationFrequencyChoices.ANNUAL
    )
    outstanding_annual_scale = (
        outstanding_ticker in ANNUALIZED_ABS_LEVEL_TICKERS
        or outstanding_is_annual_frequency
    )
    gdp_annualized = gdp_ticker in ANNUALIZED_ABS_LEVEL_TICKERS
    use_calendar_year_gdp = (
        outstanding_is_annual_frequency
        and not outstanding_is_stock
        and not gdp_annualized
    )
    use_calendar_year_average_gdp = (
        outstanding_is_annual_frequency and not outstanding_is_stock and gdp_annualized
    )
    required_observations = _required_observations_for_complete_calendar_year(
        gdp_points
    )
    if use_calendar_year_gdp:
        matched_gdp_points = sum_points_by_calendar_year(
            gdp_points, required_observations=required_observations
        )
    elif use_calendar_year_average_gdp:
        matched_gdp_points = average_points_by_calendar_year(
            gdp_points, required_observations=required_observations
        )
    else:
        matched_gdp_points = gdp_points
    return _VsGdpDenominatorContext(
        matched_gdp_points=matched_gdp_points,
        gdp_annualized=gdp_annualized,
        outstanding_annual_scale=outstanding_annual_scale,
        outstanding_is_stock=outstanding_is_stock,
        use_calendar_year_gdp=use_calendar_year_gdp,
    )


def _scale_outstanding_value_to_gdp_unit(
    outstanding_value: float,
    *,
    outstanding_unit: IndicatorBaseUnitChoices | None,
    gdp_unit: IndicatorBaseUnitChoices | None,
) -> float:
    """Align outstanding amount magnitude to GDP when stored units differ."""
    if (
        outstanding_unit in _AMOUNT_BASE_UNITS
        and gdp_unit in _AMOUNT_BASE_UNITS
        and outstanding_unit != gdp_unit
    ):
        return scale_amount_between_magnitudes(
            outstanding_value,
            IndicatorAmountMagnitudeChoices(outstanding_unit),
            IndicatorAmountMagnitudeChoices(gdp_unit),
        )
    return outstanding_value


class _VsGdpAnnualizedLevels(NamedTuple):
    """Outstanding and GDP levels after stock / flow annualization rules."""

    outstanding_value: float
    gdp_value: float


def _apply_vs_gdp_annualization_to_levels(
    outstanding_value: float,
    gdp_value: float,
    *,
    denominator_context: _VsGdpDenominatorContext,
) -> _VsGdpAnnualizedLevels:
    """Return outstanding and GDP levels after stock / flow annualization rules."""
    if denominator_context.outstanding_is_stock:
        if not denominator_context.gdp_annualized:
            gdp_value *= 4
    elif (
        not denominator_context.outstanding_annual_scale
        and denominator_context.gdp_annualized
    ):
        outstanding_value *= 4
    elif (
        denominator_context.outstanding_annual_scale
        and not denominator_context.gdp_annualized
        and not denominator_context.use_calendar_year_gdp
    ):
        gdp_value *= 4
    return _VsGdpAnnualizedLevels(
        outstanding_value=outstanding_value, gdp_value=gdp_value
    )


def build_vs_gdp_time_series(
    outstanding_points: list[TimeSeriesPoint],
    *,
    outstanding_ticker: str,
    outstanding_unit: IndicatorBaseUnitChoices | None,
    outstanding_measure_type: IndicatorMeasureTypeChoices,
    outstanding_frequency: EconomicPublicationFrequencyChoices,
    gdp_points: list[TimeSeriesPoint],
    gdp_ticker: str,
    gdp_unit: IndicatorBaseUnitChoices | None,
) -> list[TimeSeriesPoint]:
    """Build outstanding / GDP × 100, matching magnitude and annualization.

    Stocks are end-of-period levels: never ×4 the stock. When GDP is a quarterly
    period sum, annualize the denominator (×4). Annual-frequency flows match
    calendar-year GDP totals, not Q1 ×4.
    """
    if not outstanding_points or not gdp_points:
        return []
    denominator_context = _get_vs_gdp_denominator_context(
        outstanding_ticker=outstanding_ticker,
        outstanding_measure_type=outstanding_measure_type,
        outstanding_frequency=outstanding_frequency,
        gdp_points=gdp_points,
        gdp_ticker=gdp_ticker,
    )
    # Usage of dict: period date → GDP level (nominal or real).
    gdp_by_period: dict[date, float] = {
        point.period: point.value for point in denominator_context.matched_gdp_points
    }
    scaled_numerator: list[TimeSeriesPoint] = []
    scaled_denominator: list[TimeSeriesPoint] = []
    for outstanding_point in outstanding_points:
        gdp_value = gdp_by_period.get(outstanding_point.period)
        if gdp_value is None or gdp_value == 0:
            continue
        outstanding_value = _scale_outstanding_value_to_gdp_unit(
            outstanding_point.value,
            outstanding_unit=outstanding_unit,
            gdp_unit=gdp_unit,
        )
        outstanding_value, gdp_value = _apply_vs_gdp_annualization_to_levels(
            outstanding_value,
            gdp_value,
            denominator_context=denominator_context,
        )
        scaled_numerator.append(
            TimeSeriesPoint(period=outstanding_point.period, value=outstanding_value)
        )
        scaled_denominator.append(
            TimeSeriesPoint(period=outstanding_point.period, value=gdp_value)
        )
    return build_ratio_percent_time_series(scaled_numerator, scaled_denominator)


class _AlignedPeriodLevelSeries(NamedTuple):
    """Period-level outstanding and GDP series on matching observation periods."""

    outstanding_points: list[TimeSeriesPoint]
    gdp_points: list[TimeSeriesPoint]


def _align_period_level_series_on_shared_periods(
    outstanding_points: list[TimeSeriesPoint],
    gdp_points: list[TimeSeriesPoint],
    *,
    outstanding_ticker: str,
    gdp_ticker: str,
) -> _AlignedPeriodLevelSeries:
    """Return period-level outstanding and GDP series on matching periods."""
    period_outstanding = convert_points_to_period_level(
        outstanding_points,
        is_annualized=outstanding_ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
    )
    period_gdp = convert_points_to_period_level(
        gdp_points,
        is_annualized=gdp_ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
    )
    # Usage of dict: period → GDP period-level value for alignment.
    gdp_by_period: dict[date, float] = {
        point.period: point.value for point in period_gdp
    }
    aligned_outstanding: list[TimeSeriesPoint] = []
    aligned_gdp: list[TimeSeriesPoint] = []
    for point in sorted(period_outstanding, key=lambda point: point.period):
        gdp_value = gdp_by_period.get(point.period)
        if gdp_value is None:
            continue
        aligned_outstanding.append(point)
        aligned_gdp.append(TimeSeriesPoint(period=point.period, value=gdp_value))
    return _AlignedPeriodLevelSeries(
        outstanding_points=aligned_outstanding, gdp_points=aligned_gdp
    )


def _scale_series_amount_unit(
    points: list[TimeSeriesPoint],
    *,
    from_unit: str,
    to_unit: str,
) -> list[TimeSeriesPoint]:
    """Scale amount-unit series when both ends are K / M / B."""
    if from_unit not in _AMOUNT_BASE_UNITS or to_unit not in _AMOUNT_BASE_UNITS:
        return points
    if from_unit == to_unit:
        return points
    return [
        TimeSeriesPoint(
            period=point.period,
            value=scale_amount_between_magnitudes(
                point.value,
                IndicatorAmountMagnitudeChoices(from_unit),
                IndicatorAmountMagnitudeChoices(to_unit),
            ),
        )
        for point in points
    ]


def build_ytd_vs_gdp_time_series(
    outstanding_points: list[TimeSeriesPoint],
    *,
    outstanding_ticker: str,
    outstanding_unit: str,
    outstanding_frequency: EconomicPublicationFrequencyChoices,
    gdp_points: list[TimeSeriesPoint],
    gdp_ticker: str,
    gdp_unit: str,
) -> list[TimeSeriesPoint]:
    """Return year-to-date flow over year-to-date GDP, in percent."""
    aligned_series = _align_period_level_series_on_shared_periods(
        outstanding_points,
        gdp_points,
        outstanding_ticker=outstanding_ticker,
        gdp_ticker=gdp_ticker,
    )
    ytd_outstanding = build_year_to_date_cumulative_time_series(
        aligned_series.outstanding_points, frequency=outstanding_frequency
    )
    ytd_gdp = build_year_to_date_cumulative_time_series(
        aligned_series.gdp_points, frequency=outstanding_frequency
    )
    scaled_ytd_outstanding = _scale_series_amount_unit(
        ytd_outstanding, from_unit=outstanding_unit, to_unit=gdp_unit
    )
    return build_ratio_percent_time_series(scaled_ytd_outstanding, ytd_gdp)
