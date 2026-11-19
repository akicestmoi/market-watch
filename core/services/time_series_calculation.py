"""Generic dated time-series math used across apps.

No domain modes, GDP rules, or publication-frequency enums live here. Callers
pass lookbacks and predefined YTD steps; app services compose those into YTD,
vsGDP, MoM, and similar display transforms.
"""

from datetime import date
from enum import Enum, IntEnum
from typing import NamedTuple

from dateutil.relativedelta import relativedelta


class ValueChangeType(str, Enum):
    """Which change metric 'calculate_value_change' should compute."""

    ABSOLUTE = "absolute"
    PERCENT = "percent"
    BPS = "bps"
    ANNUALIZED_PERCENT = "annualized_percent"


def calculate_value_change(
    current: float | None,
    previous: float | None,
    value_change_type: ValueChangeType,
    annualized_ratio: float | None = None,
) -> float | None:
    """Compute one change metric from 'previous' to 'current'.

    Period labels (DoD / WoW / MoM / QoQ / QoQy / YoY) are caller concerns: pick
    the comparison value and 'value_change_type'. Returns None when either
    input is None.

    - 'ABSOLUTE' — 'current - previous'
    - 'PERCENT' — '(absolute / previous) * 100' (None if 'previous' is 0)
    - 'BPS' — 'absolute * 100' (yields quoted in percent)
    - 'ANNUALIZED_PERCENT' — '((current / previous) ** annualized_ratio - 1) *
      100' (requires 'annualized_ratio'; None if 'previous' is 0 or the
      ratio is non-positive)
    """
    if current is None or previous is None:
        return None
    absolute = current - previous
    match value_change_type:
        case ValueChangeType.ABSOLUTE:
            return absolute
        case ValueChangeType.BPS:
            return absolute * 100
        case ValueChangeType.PERCENT:
            return None if previous == 0 else (absolute / previous) * 100
        case ValueChangeType.ANNUALIZED_PERCENT:
            if annualized_ratio is None or previous == 0:
                return None
            ratio = current / previous
            if ratio <= 0:
                return None
            return ((ratio**annualized_ratio) - 1) * 100


class TimeSeriesPoint(NamedTuple):
    """One dated level in a time series."""

    period: date
    value: float


class YearToDateStep(IntEnum):
    """Calendar-month gap between successive year-to-date ladder periods."""

    MONTHLY = 1
    QUARTERLY = 3
    ANNUAL = 12


def scale_value_by_thousand_powers(value: float, *, power_difference: int) -> float:
    """Scale 'value' by 1000 raised to 'power_difference' (e.g. M→B is -1)."""
    return value * (1000.0**power_difference)


def convert_annualized_levels_to_period_amounts(
    points: list[TimeSeriesPoint],
    *,
    periods_per_year: int,
) -> list[TimeSeriesPoint]:
    """Turn annualized (e.g. SAAR) levels into one-period amounts."""
    if periods_per_year <= 0:
        return points
    return [
        TimeSeriesPoint(period=point.period, value=point.value / periods_per_year)
        for point in points
    ]


def build_percent_change_vs_lookback_period(
    points: list[TimeSeriesPoint],
    *,
    lookback_months: int,
    annualized_ratio: float | None = None,
) -> list[TimeSeriesPoint]:
    """Return percent change vs the calendar period 'lookback_months' earlier.

    When 'annualized_ratio' is set, use compounded annualized percent change.
    Points without a matching prior period are dropped.
    """
    if not points or lookback_months <= 0:
        return []
    ordered_points = sorted(points, key=lambda point: point.period)
    # Usage of dict: keys are observation periods; values are raw levels.
    value_by_period: dict[date, float] = {
        point.period: point.value for point in ordered_points
    }
    changed_points: list[TimeSeriesPoint] = []
    for current_point in ordered_points:
        prior_period = current_point.period + relativedelta(months=-lookback_months)
        prior_value = value_by_period.get(prior_period)
        if prior_value is None:
            continue
        value_change_type = (
            ValueChangeType.ANNUALIZED_PERCENT
            if annualized_ratio is not None
            else ValueChangeType.PERCENT
        )
        change = calculate_value_change(
            current_point.value,
            prior_value,
            value_change_type,
            annualized_ratio=annualized_ratio,
        )
        if change is None:
            continue
        changed_points.append(
            TimeSeriesPoint(period=current_point.period, value=change)
        )
    return changed_points


def sum_points_by_calendar_year(
    points: list[TimeSeriesPoint],
    *,
    required_observations: int | None = None,
) -> list[TimeSeriesPoint]:
    """Sum intra-year observations into one January-1 total per calendar year.

    When 'required_observations' is set, incomplete years are dropped.
    """
    # Usage of dict: calendar year → summed level across periods in that year.
    total_by_year: dict[int, float] = {}
    # Usage of dict: calendar year → number of intra-year observations summed.
    observation_count_by_year: dict[int, int] = {}
    for point in points:
        total_by_year[point.period.year] = (
            total_by_year.get(point.period.year, 0.0) + point.value
        )
        observation_count_by_year[point.period.year] = (
            observation_count_by_year.get(point.period.year, 0) + 1
        )
    return [
        TimeSeriesPoint(period=date(year, 1, 1), value=year_total)
        for year, year_total in sorted(total_by_year.items())
        if required_observations is None
        or observation_count_by_year[year] >= required_observations
    ]


def average_points_by_calendar_year(
    points: list[TimeSeriesPoint],
    *,
    required_observations: int | None = None,
) -> list[TimeSeriesPoint]:
    """Average intra-year observations into one January-1 value per calendar year."""
    # Usage of dict: calendar year → number of intra-year observations.
    observation_count_by_year: dict[int, int] = {}
    for point in points:
        observation_count_by_year[point.period.year] = (
            observation_count_by_year.get(point.period.year, 0) + 1
        )
    return [
        TimeSeriesPoint(
            period=year_total_point.period,
            value=(
                year_total_point.value
                / observation_count_by_year[year_total_point.period.year]
            ),
        )
        for year_total_point in sum_points_by_calendar_year(
            points, required_observations=required_observations
        )
    ]


def build_ratio_percent_time_series(
    numerator_points: list[TimeSeriesPoint],
    denominator_points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Return numerator / denominator × 100 on shared observation periods."""
    # Usage of dict: period → denominator level.
    denominator_by_period: dict[date, float] = {
        point.period: point.value for point in denominator_points
    }
    ratio_points: list[TimeSeriesPoint] = []
    for point in numerator_points:
        denominator_value = denominator_by_period.get(point.period)
        if denominator_value is None or denominator_value == 0:
            continue
        ratio_points.append(
            TimeSeriesPoint(
                period=point.period,
                value=(point.value / denominator_value) * 100.0,
            )
        )
    return ratio_points


class _YtdRunningTotal(NamedTuple):
    """Next expected month and the running total for one calendar year."""

    next_month: int
    total: float


def build_year_to_date_cumulative_time_series(
    points: list[TimeSeriesPoint],
    *,
    step: YearToDateStep,
) -> list[TimeSeriesPoint]:
    """Return running calendar year-to-date sums, keeping each point's period date.

    'step' is the ladder gap (monthly / quarterly / annual). The stack stays
    contiguous from period 1 of each year; a gap stops that year.
    """
    ordered_points = sorted(points, key=lambda point: point.period)
    step_months = int(step)
    # Usage of dict: calendar year → next expected month and running total.
    running_total_by_year: dict[int, _YtdRunningTotal] = {}
    cumulative_points: list[TimeSeriesPoint] = []
    for point in ordered_points:
        year = point.period.year
        month = point.period.month
        running_total = running_total_by_year.get(
            year, _YtdRunningTotal(next_month=1, total=0.0)
        )
        if running_total.next_month < 0 or month != running_total.next_month:
            running_total_by_year[year] = _YtdRunningTotal(
                next_month=-1, total=running_total.total
            )
            continue
        updated_total = running_total.total + point.value
        next_expected_month = month + step_months
        running_total_by_year[year] = _YtdRunningTotal(
            next_month=next_expected_month if next_expected_month <= 12 else -1,
            total=updated_total,
        )
        cumulative_points.append(
            TimeSeriesPoint(period=point.period, value=updated_total)
        )
    return cumulative_points


def collapse_to_latest_point_per_calendar_year(
    points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Return the latest point of each calendar year, dated 1 January of that year."""
    # Usage of dict: calendar year → latest point seen for that year.
    latest_by_year: dict[int, TimeSeriesPoint] = {}
    for point in sorted(points, key=lambda point: point.period):
        latest_by_year[point.period.year] = point
    return [
        TimeSeriesPoint(period=date(year, 1, 1), value=year_point.value)
        for year, year_point in sorted(latest_by_year.items())
    ]


def build_same_period_year_over_year_percent_time_series(
    points: list[TimeSeriesPoint],
) -> list[TimeSeriesPoint]:
    """Return percent change vs the matching calendar month / day one year earlier."""
    # Usage of dict: observation period → level.
    value_by_period: dict[date, float] = {point.period: point.value for point in points}
    yoy_points: list[TimeSeriesPoint] = []
    for point in sorted(points, key=lambda point: point.period):
        prior_period = point.period + relativedelta(years=-1)
        prior_value = value_by_period.get(prior_period)
        if prior_value is None or prior_value == 0:
            continue
        change = calculate_value_change(
            point.value, prior_value, ValueChangeType.PERCENT
        )
        if change is None:
            continue
        yoy_points.append(TimeSeriesPoint(period=point.period, value=change))
    return yoy_points
