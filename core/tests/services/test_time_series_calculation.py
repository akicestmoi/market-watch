"""Tests for generic dated math in 'core.services.time_series_calculation'."""

from datetime import date

from django.test import SimpleTestCase

from core.services.time_series_calculation import (
    TimeSeriesPoint,
    ValueChangeType,
    YearToDateStep,
    average_points_by_calendar_year,
    build_percent_change_vs_lookback_period,
    build_ratio_percent_time_series,
    build_same_period_year_over_year_percent_time_series,
    build_year_to_date_cumulative_time_series,
    calculate_value_change,
    collapse_to_latest_point_per_calendar_year,
    convert_annualized_levels_to_period_amounts,
    scale_value_by_thousand_powers,
    sum_points_by_calendar_year,
)


class TestCalculateValueChange(SimpleTestCase):
    """Test cases for calculate_value_change."""

    def test_calculate_value_change_absolute_percent_and_bps(self):
        """
        GIVEN current and previous levels
        WHEN calculate_value_change is called for each output
        THEN the matching scalar is returned
        """
        assert calculate_value_change(110.0, 100.0, ValueChangeType.ABSOLUTE) == 10.0
        assert calculate_value_change(110.0, 100.0, ValueChangeType.PERCENT) == 10.0
        assert calculate_value_change(110.0, 100.0, ValueChangeType.BPS) == 1000.0

    def test_calculate_value_change_annualized_percent(self):
        """
        GIVEN current and previous levels and annualized_ratio=4
        WHEN output is ANNUALIZED_PERCENT
        THEN ((current / previous) ** 4 - 1) * 100 is returned
        """
        assert (
            calculate_value_change(
                102.0, 100.0, ValueChangeType.ANNUALIZED_PERCENT, annualized_ratio=4
            )
            == ((102.0 / 100.0) ** 4 - 1) * 100
        )
        assert (
            calculate_value_change(102.0, 100.0, ValueChangeType.ANNUALIZED_PERCENT)
            is None
        )

    def test_calculate_value_change_undefined_when_previous_zero(self):
        """
        GIVEN a zero previous value
        WHEN percent or annualized outputs are requested
        THEN None is returned while absolute and bps remain defined
        """
        assert calculate_value_change(5.0, 0.0, ValueChangeType.ABSOLUTE) == 5.0
        assert calculate_value_change(5.0, 0.0, ValueChangeType.BPS) == 500.0
        assert calculate_value_change(5.0, 0.0, ValueChangeType.PERCENT) is None
        assert (
            calculate_value_change(
                5.0, 0.0, ValueChangeType.ANNUALIZED_PERCENT, annualized_ratio=4
            )
            is None
        )

    def test_calculate_value_change_non_positive_ratio_skips_annualized(self):
        """
        GIVEN a non-positive current/previous ratio
        WHEN ANNUALIZED_PERCENT is requested
        THEN None is returned while simple percent remains defined
        """
        assert calculate_value_change(-1.0, 100.0, ValueChangeType.PERCENT) == -101.0
        assert (
            calculate_value_change(
                -1.0, 100.0, ValueChangeType.ANNUALIZED_PERCENT, annualized_ratio=4
            )
            is None
        )

    def test_calculate_value_change_missing_inputs(self):
        """
        GIVEN a missing current or previous value
        WHEN calculate_value_change is called
        THEN None is returned for every value-change type
        """
        for value_change_type in ValueChangeType:
            assert calculate_value_change(None, 100.0, value_change_type) is None
            assert (
                calculate_value_change(
                    100.0, None, value_change_type, annualized_ratio=4
                )
                is None
            )


class TestScaleAndAnnualizedPeriodAmounts(SimpleTestCase):
    """Thousand-power scaling and SAAR → period amount helpers."""

    def test_scale_value_by_thousand_powers(self):
        """
        GIVEN an amount and a thousand-power difference
        WHEN scaling the value
        THEN the amount moves by 1000 raised to that power
        """
        assert scale_value_by_thousand_powers(34_000.0, power_difference=-1) == 34.0
        assert scale_value_by_thousand_powers(3.5955, power_difference=1) == 3_595.5

    def test_convert_annualized_levels_to_period_amounts(self):
        """
        GIVEN annualized quarterly levels
        WHEN converting with periods_per_year=4
        THEN each value is divided by 4
        """
        points = [
            TimeSeriesPoint(date(2024, 1, 1), 400.0),
            TimeSeriesPoint(date(2024, 4, 1), 440.0),
        ]
        assert convert_annualized_levels_to_period_amounts(
            points, periods_per_year=4
        ) == [
            TimeSeriesPoint(date(2024, 1, 1), 100.0),
            TimeSeriesPoint(date(2024, 4, 1), 110.0),
        ]


class TestLookbackAndYearAggregation(SimpleTestCase):
    """Lookback percent change and calendar-year sum / average helpers."""

    def test_build_percent_change_vs_lookback_period_quarterly(self):
        """
        GIVEN quarterly levels
        WHEN computing percent change with a 3-month lookback
        THEN each point compares to the prior quarter
        """
        points = [
            TimeSeriesPoint(date(2023, 1, 1), 100.0),
            TimeSeriesPoint(date(2023, 4, 1), 102.0),
            TimeSeriesPoint(date(2023, 7, 1), 104.0),
            TimeSeriesPoint(date(2024, 1, 1), 110.0),
        ]
        assert build_percent_change_vs_lookback_period(points, lookback_months=3) == [
            TimeSeriesPoint(date(2023, 4, 1), 2.0),
            TimeSeriesPoint(date(2023, 7, 1), (104.0 - 102.0) / 102.0 * 100),
        ]

    def test_build_percent_change_vs_lookback_period_annualized(self):
        """
        GIVEN quarterly levels and annualized_ratio=4
        WHEN computing lookback percent change
        THEN compounded annualized percent is returned
        """
        points = [
            TimeSeriesPoint(date(2023, 1, 1), 100.0),
            TimeSeriesPoint(date(2023, 4, 1), 102.0),
        ]
        assert build_percent_change_vs_lookback_period(
            points, lookback_months=3, annualized_ratio=4.0
        ) == [
            TimeSeriesPoint(date(2023, 4, 1), ((102.0 / 100.0) ** 4 - 1) * 100),
        ]

    def test_sum_and_average_points_by_calendar_year(self):
        """
        GIVEN four quarterly points in one year and two in another
        WHEN summing and averaging with required_observations=4
        THEN only the complete year is kept
        """
        points = [
            TimeSeriesPoint(date(2024, 1, 1), 10.0),
            TimeSeriesPoint(date(2024, 4, 1), 20.0),
            TimeSeriesPoint(date(2024, 7, 1), 30.0),
            TimeSeriesPoint(date(2024, 10, 1), 40.0),
            TimeSeriesPoint(date(2025, 1, 1), 50.0),
            TimeSeriesPoint(date(2025, 4, 1), 60.0),
        ]
        assert sum_points_by_calendar_year(points, required_observations=4) == [
            TimeSeriesPoint(date(2024, 1, 1), 100.0),
        ]
        assert average_points_by_calendar_year(points, required_observations=4) == [
            TimeSeriesPoint(date(2024, 1, 1), 25.0),
        ]


class TestRatioAndYtdHelpers(SimpleTestCase):
    """Ratio percent, YTD cumulative, collapse, and same-period YoY helpers."""

    def test_build_ratio_percent_time_series(self):
        """
        GIVEN numerator and denominator series on shared periods
        WHEN building the ratio percent series
        THEN missing or zero denominators are dropped
        """
        numerator_points = [
            TimeSeriesPoint(date(2024, 1, 1), 50.0),
            TimeSeriesPoint(date(2024, 4, 1), 60.0),
            TimeSeriesPoint(date(2024, 7, 1), 70.0),
        ]
        denominator_points = [
            TimeSeriesPoint(date(2024, 1, 1), 100.0),
            TimeSeriesPoint(date(2024, 4, 1), 0.0),
        ]
        assert build_ratio_percent_time_series(
            numerator_points, denominator_points
        ) == [
            TimeSeriesPoint(date(2024, 1, 1), 50.0),
        ]

    def test_build_year_to_date_cumulative_time_series_monthly(self):
        """
        GIVEN monthly levels with a mid-year gap
        WHEN building year-to-date cumulative totals
        THEN contiguous months accumulate and the gap stops that year
        """
        points = [
            TimeSeriesPoint(date(2024, 1, 1), 10.0),
            TimeSeriesPoint(date(2024, 2, 1), 20.0),
            TimeSeriesPoint(date(2024, 4, 1), 40.0),
            TimeSeriesPoint(date(2025, 1, 1), 5.0),
            TimeSeriesPoint(date(2025, 2, 1), 7.0),
        ]
        assert build_year_to_date_cumulative_time_series(
            points, step=YearToDateStep.MONTHLY
        ) == [
            TimeSeriesPoint(date(2024, 1, 1), 10.0),
            TimeSeriesPoint(date(2024, 2, 1), 30.0),
            TimeSeriesPoint(date(2025, 1, 1), 5.0),
            TimeSeriesPoint(date(2025, 2, 1), 12.0),
        ]

    def test_collapse_to_latest_point_per_calendar_year(self):
        """
        GIVEN several points across two years
        WHEN collapsing to the latest point per calendar year
        THEN each year keeps its latest value on 1 January
        """
        points = [
            TimeSeriesPoint(date(2024, 3, 1), 10.0),
            TimeSeriesPoint(date(2024, 9, 1), 30.0),
            TimeSeriesPoint(date(2025, 6, 1), 40.0),
        ]
        assert collapse_to_latest_point_per_calendar_year(points) == [
            TimeSeriesPoint(date(2024, 1, 1), 30.0),
            TimeSeriesPoint(date(2025, 1, 1), 40.0),
        ]

    def test_build_same_period_year_over_year_percent_maps_leap_day_to_feb_28(
        self,
    ):
        """
        GIVEN a 29 Feb observation and a 28 Feb value one year earlier
        WHEN building same-period year-over-year percent points
        THEN 29 Feb compares against 28 Feb of the prior year
        """
        points = [
            TimeSeriesPoint(date(2023, 2, 28), 100.0),
            TimeSeriesPoint(date(2024, 2, 28), 110.0),
            TimeSeriesPoint(date(2024, 2, 29), 120.0),
        ]
        assert build_same_period_year_over_year_percent_time_series(points) == [
            TimeSeriesPoint(date(2024, 2, 28), 10.0),
            TimeSeriesPoint(date(2024, 2, 29), 20.0),
        ]
