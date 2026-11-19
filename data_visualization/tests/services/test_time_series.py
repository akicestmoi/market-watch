"""Tests for economic display transforms in 'data_visualization.services.time_series'."""

from datetime import date

from django.test import SimpleTestCase

from core.services.time_series_calculation import (
    TimeSeriesPoint,
    ValueChangeType,
    calculate_value_change,
)
from data_visualization.services.time_series import (
    build_vs_gdp_time_series,
    build_year_to_date_cumulative_time_series,
    build_ytd_vs_gdp_time_series,
    build_ytd_yoy_time_series,
    change_series_mode,
    collapse_ytd_time_series_to_annual_points,
    convert_points_to_period_level,
    scale_amount_between_magnitudes,
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


class TestScaleAndPeriodLevel(SimpleTestCase):
    """Magnitude scaling and annualized → period-level helpers."""

    def test_scale_amount_between_magnitudes(self):
        """
        GIVEN an amount in millions
        WHEN scaling to billions
        THEN the value is divided by 1000
        """
        assert (
            scale_amount_between_magnitudes(
                34_000.0,
                IndicatorAmountMagnitudeChoices.M,
                IndicatorAmountMagnitudeChoices.B,
            )
            == 34.0
        )

    def test_convert_points_to_period_level_divides_annualized(self):
        """
        GIVEN annualized quarterly levels
        WHEN converting to period level
        THEN each value is divided by 4
        """
        points = [TimeSeriesPoint(date(2024, 1, 1), 400.0)]
        assert convert_points_to_period_level(points, is_annualized=True) == [
            TimeSeriesPoint(date(2024, 1, 1), 100.0)
        ]
        assert convert_points_to_period_level(points, is_annualized=False) == points


class TestChangeSeriesMode(SimpleTestCase):
    """MoM / QoQ / YoY mode transforms."""

    def test_change_series_mode_quarterly_qoq_qoqy_and_yoy(self):
        """
        GIVEN quarterly level points
        WHEN changing to QoQ, QoQy, and YoY modes
        THEN percent changes use QoQ lag, annualized QoQ, and YoY lag
        """
        points = [
            TimeSeriesPoint(date(2023, 1, 1), 100.0),
            TimeSeriesPoint(date(2023, 4, 1), 102.0),
            TimeSeriesPoint(date(2023, 7, 1), 104.0),
            TimeSeriesPoint(date(2023, 10, 1), 106.0),
            TimeSeriesPoint(date(2024, 1, 1), 110.0),
        ]
        qoq = change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            IndicatorDisplayModeChoices.QUARTER,
        )
        assert qoq == [
            TimeSeriesPoint(date(2023, 4, 1), 2.0),
            TimeSeriesPoint(date(2023, 7, 1), (104.0 - 102.0) / 102.0 * 100),
            TimeSeriesPoint(date(2023, 10, 1), (106.0 - 104.0) / 104.0 * 100),
            TimeSeriesPoint(date(2024, 1, 1), (110.0 - 106.0) / 106.0 * 100),
        ]

        qoqy = change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
        )
        assert qoqy == [
            TimeSeriesPoint(date(2023, 4, 1), ((102.0 / 100.0) ** 4 - 1) * 100),
            TimeSeriesPoint(date(2023, 7, 1), ((104.0 / 102.0) ** 4 - 1) * 100),
            TimeSeriesPoint(date(2023, 10, 1), ((106.0 / 104.0) ** 4 - 1) * 100),
            TimeSeriesPoint(date(2024, 1, 1), ((110.0 / 106.0) ** 4 - 1) * 100),
        ]

        yoy = change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            IndicatorDisplayModeChoices.ANNUAL,
        )
        assert yoy == [TimeSeriesPoint(date(2024, 1, 1), 10.0)]

    def test_change_series_mode_monthly_missing_prior_is_dropped(self):
        """
        GIVEN monthly points with insufficient history for YoY
        WHEN changing to YoY / QoQ modes
        THEN points without a prior are omitted
        """
        points = [
            TimeSeriesPoint(date(2024, 1, 1), 100.0),
            TimeSeriesPoint(date(2024, 2, 1), 101.0),
            TimeSeriesPoint(date(2024, 3, 1), 102.0),
        ]
        assert (
            change_series_mode(
                points,
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.ANNUAL,
            )
            == []
        )
        assert (
            change_series_mode(
                points,
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.QUARTER,
            )
            == []
        )

    def test_change_series_mode_monthly_yoy_skips_wrong_calendar_month(self):
        """
        GIVEN monthly points where Sep 2025 is missing but Aug 2025 exists
        WHEN changing to YoY
        THEN Sep 2026 is omitted and only Aug 2026 vs Aug 2025 remains
        """
        points = [
            TimeSeriesPoint(date(2025, 8, 1), 323.291),
            TimeSeriesPoint(date(2026, 8, 1), 334.131),
            TimeSeriesPoint(date(2026, 9, 1), 336.298),
        ]
        august_yoy_change = calculate_value_change(
            334.131, 323.291, ValueChangeType.PERCENT
        )
        assert august_yoy_change is not None
        assert change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.MONTHLY,
            IndicatorDisplayModeChoices.ANNUAL,
        ) == [
            TimeSeriesPoint(date(2026, 8, 1), august_yoy_change),
        ]

    def test_change_series_mode_monthly_yoy_uses_same_calendar_month(self):
        """
        GIVEN monthly points including Sep 2025 and Sep 2026
        WHEN changing to YoY
        THEN Sep 2026 uses Sep 2025 even if other months are sparse
        """
        points = [
            TimeSeriesPoint(date(2025, 8, 1), 323.291),
            TimeSeriesPoint(date(2025, 9, 1), 324.245),
            TimeSeriesPoint(date(2026, 9, 1), 336.298),
        ]
        september_yoy_change = calculate_value_change(
            336.298, 324.245, ValueChangeType.PERCENT
        )
        assert september_yoy_change is not None
        assert change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.MONTHLY,
            IndicatorDisplayModeChoices.ANNUAL,
        ) == [
            TimeSeriesPoint(date(2026, 9, 1), september_yoy_change),
        ]


class TestVsGdpTimeSeries(SimpleTestCase):
    """Outstanding / GDP display transforms."""

    def test_build_vs_gdp_time_series_stock_and_flow_annualization(self):
        """
        GIVEN stock, period-flow, and annual-flow levels against SAAR or period GDP
        WHEN building vsGDP points
        THEN stocks and annual flows stay annual-scale while period flows ×4 vs SAAR
        """
        period = date(2025, 4, 1)
        stock_vs_saar = build_vs_gdp_time_series(
            [TimeSeriesPoint(period, 34_000_000.0)],
            outstanding_ticker="gg_debt_securities_loans",
            outstanding_unit=IndicatorBaseUnitChoices.M,
            outstanding_measure_type=IndicatorMeasureTypeChoices.STOCK,
            outstanding_frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            gdp_points=[TimeSeriesPoint(period, 30_100.0)],
            gdp_ticker="GDP",
            gdp_unit=IndicatorBaseUnitChoices.B,
        )
        assert stock_vs_saar == [TimeSeriesPoint(period, (34_000.0 / 30_100.0) * 100.0)]

        stock_vs_period = build_vs_gdp_time_series(
            [TimeSeriesPoint(period, 2_900_000.0)],
            outstanding_ticker="gov_10q_ggdebt",
            outstanding_unit=IndicatorBaseUnitChoices.M,
            outstanding_measure_type=IndicatorMeasureTypeChoices.STOCK,
            outstanding_frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            gdp_points=[TimeSeriesPoint(period, 1_100_000.0)],
            gdp_ticker="namq_10_gdp",
            gdp_unit=IndicatorBaseUnitChoices.M,
        )
        assert stock_vs_period == [
            TimeSeriesPoint(period, (2_900_000.0 / (1_100_000.0 * 4.0)) * 100.0)
        ]

        fr_stock_billions = build_vs_gdp_time_series(
            [TimeSeriesPoint(period, 3595.5)],
            outstanding_ticker="010777616",
            outstanding_unit=IndicatorBaseUnitChoices.B,
            outstanding_measure_type=IndicatorMeasureTypeChoices.STOCK,
            outstanding_frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            gdp_points=[TimeSeriesPoint(period, 760_337.9)],
            gdp_ticker="namq_10_gdp_cp",
            gdp_unit=IndicatorBaseUnitChoices.M,
        )
        assert fr_stock_billions == [
            TimeSeriesPoint(period, ((3595.5 * 1000.0) / (760_337.9 * 4.0)) * 100.0)
        ]

        flow_vs_saar = build_vs_gdp_time_series(
            [TimeSeriesPoint(period, 100_000.0)],
            outstanding_ticker="IEABC",
            outstanding_unit=IndicatorBaseUnitChoices.M,
            outstanding_measure_type=IndicatorMeasureTypeChoices.FLOW,
            outstanding_frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            gdp_points=[TimeSeriesPoint(period, 30_000.0)],
            gdp_ticker="GDP",
            gdp_unit=IndicatorBaseUnitChoices.B,
        )
        assert flow_vs_saar == [
            TimeSeriesPoint(period, ((100_000.0 * 4.0) / 1000.0 / 30_000.0) * 100.0)
        ]

        annual_flow_vs_saar = build_vs_gdp_time_series(
            [TimeSeriesPoint(date(2024, 1, 1), 241_468.5)],
            outstanding_ticker="gfs_expense_gg_fy",
            outstanding_unit=IndicatorBaseUnitChoices.B,
            outstanding_measure_type=IndicatorMeasureTypeChoices.FLOW,
            outstanding_frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            gdp_points=[TimeSeriesPoint(date(2024, 1, 1), 621_923.6)],
            gdp_ticker="gaku-mk",
            gdp_unit=IndicatorBaseUnitChoices.B,
        )
        assert annual_flow_vs_saar == [
            TimeSeriesPoint(date(2024, 1, 1), (241_468.5 / 621_923.6) * 100.0)
        ]

    def test_build_vs_gdp_time_series_annual_flow_vs_saar_year_average(self):
        """
        GIVEN a calendar-year BEA expenditure total and four SAAR GDP quarters
        WHEN building vsGDP points
        THEN the annual flow is divided by the mean of that year's SAAR quarters
        """
        result = build_vs_gdp_time_series(
            [TimeSeriesPoint(date(2024, 1, 1), 10_168.7)],
            outstanding_ticker="bea_t31600_total",
            outstanding_unit=IndicatorBaseUnitChoices.B,
            outstanding_measure_type=IndicatorMeasureTypeChoices.FLOW,
            outstanding_frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            gdp_points=[
                TimeSeriesPoint(date(2024, 1, 1), 28_600.0),
                TimeSeriesPoint(date(2024, 4, 1), 29_000.0),
                TimeSeriesPoint(date(2024, 7, 1), 29_400.0),
                TimeSeriesPoint(date(2024, 10, 1), 29_800.0),
            ],
            gdp_ticker="GDP",
            gdp_unit=IndicatorBaseUnitChoices.B,
        )
        assert result == [
            TimeSeriesPoint(
                date(2024, 1, 1),
                (10_168.7 / ((28_600.0 + 29_000.0 + 29_400.0 + 29_800.0) / 4)) * 100.0,
            )
        ]


class TestYtdTimeSeries(SimpleTestCase):
    """Year-to-date cumulative, YoY, and vsGDP helpers."""

    def test_build_ytd_yoy_compares_same_month_not_full_prior_year(self):
        """
        GIVEN monthly levels where the latest year is only through September
        WHEN building cumulative YTD then YTD YoY and collapsing to annual points
        THEN the incomplete year compares to the same month a year earlier
        """
        source_points = [
            TimeSeriesPoint(date(2024, month, 1), 100.0) for month in range(1, 13)
        ] + [TimeSeriesPoint(date(2025, month, 1), 110.0) for month in range(1, 10)]
        ytd_points = build_year_to_date_cumulative_time_series(
            source_points,
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        annual_ytd_yoy_points = collapse_ytd_time_series_to_annual_points(
            build_ytd_yoy_time_series(ytd_points)
        )
        assert annual_ytd_yoy_points == [
            TimeSeriesPoint(date(2025, 1, 1), 10.0),
        ]

    def test_build_ytd_vs_gdp_time_series_scales_and_ratios(self):
        """
        GIVEN monthly outstanding in millions and matching period-level GDP in billions
        WHEN building YTD vs GDP
        THEN outstanding is scaled to GDP units before the percent ratio
        """
        outstanding_points = [
            TimeSeriesPoint(date(2024, 1, 1), 1_000.0),
            TimeSeriesPoint(date(2024, 2, 1), 1_000.0),
        ]
        gdp_points = [
            TimeSeriesPoint(date(2024, 1, 1), 2.0),
            TimeSeriesPoint(date(2024, 2, 1), 2.0),
        ]
        assert build_ytd_vs_gdp_time_series(
            outstanding_points,
            outstanding_ticker="non_saar_flow",
            outstanding_unit=IndicatorBaseUnitChoices.M,
            outstanding_frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            gdp_points=gdp_points,
            gdp_ticker="non_saar_gdp",
            gdp_unit=IndicatorBaseUnitChoices.B,
        ) == [
            TimeSeriesPoint(date(2024, 1, 1), (1.0 / 2.0) * 100.0),
            TimeSeriesPoint(date(2024, 2, 1), (2.0 / 4.0) * 100.0),
        ]
