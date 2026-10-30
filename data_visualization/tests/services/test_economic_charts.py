"""Tests for economic chart visualization services."""

from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from data_visualization.services.economic_charts import (
    ChartPeriodWindow,
    EconomicChartsFrontData,
    _build_value_axis_label,
    _change_series_mode,
    _EconomicChartsCategoryDefaults,
    _EconomicChartsData,
    _EconomicChartsDropdownValues,
    _filter_time_series_by_period_window,
    _format_period,
    _parse_selected_indicator_and_mode,
    _SelectedIndicatorsByCategory,
    _TimeSeriesPoint,
    get_default_indicator_selections,
    get_economic_charts_data,
    get_economic_charts_dropdown_values,
    get_selected_indicators_by_category,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorBaseUnitChoices,
    IndicatorDisplayModeChoices,
)


class TestEconomicChartServices(TestCase):
    """Test cases for economic chart services."""

    def setUp(self):
        """Set up test fixtures."""
        self.location = EconomicDataLocationChoices.US

        self.indicator_growth = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP Growth",
            name="US GDP Growth",
            technical_name="us_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_inflation = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.INFLATION,
            type="CPI",
            name="US CPI",
            technical_name="us_cpi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP Growth",
            name="FR GDP Growth",
            technical_name="fr_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565532",
        )

        # Create economic data
        self.period1 = date(2024, 1, 1)
        self.period2 = date(2024, 4, 1)
        EconomicDataModel.objects.create(
            indicator=self.indicator_growth,
            period=self.period1,
            data_value=2.5,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_growth,
            period=self.period2,
            data_value=3.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_inflation,
            period=date(2024, 1, 15),
            data_value=2.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_inflation,
            period=date(2024, 2, 15),
            data_value=2.1,
        )

    def test_format_period_monthly(self):
        """
        GIVEN a date
        WHEN _format_period is called
        THEN period is correctly formatted as YYYY-MM
        """
        test_date = date(2024, 1, 15)
        assert (
            _format_period(test_date, EconomicPublicationFrequencyChoices.MONTHLY)
            == "2024-01"
        )
        assert (
            _format_period(test_date, EconomicPublicationFrequencyChoices.QUARTERLY)
            == "2024Q1"
        )
        assert (
            _format_period(test_date, EconomicPublicationFrequencyChoices.ANNUAL)
            == "2024"
        )

        q3_date = date(2024, 7, 1)
        assert (
            _format_period(q3_date, EconomicPublicationFrequencyChoices.QUARTERLY)
            == "2024Q3"
        )

    def test_get_selected_indicators_us_region(self):
        """
        GIVEN front data with US region indicators
        WHEN get_selected_indicators_by_category is called
        THEN correct indicators are extracted for each category
        """
        front_data = {
            "region": "United States",
            "period_window": ChartPeriodWindow.FIVE_YEARS.value,
            "us_growth_indicator": "GDP Growth,Real GDP",
            "us_inflation_indicator": "CPI",
            "us_government_indicator": "",
            "us_production_indicator": "",
            "us_sales_indicator": "",
            "us_labour_indicator": "",
            "us_housing_indicator": "",
            "us_confidence_indicator": "",
            "eu_growth_indicator": "",
            "eu_inflation_indicator": "",
            "eu_government_indicator": "",
            "eu_production_indicator": "",
            "eu_sales_indicator": "",
            "eu_labour_indicator": "",
            "eu_housing_indicator": "",
            "eu_confidence_indicator": "",
            "fr_growth_indicator": "",
            "fr_inflation_indicator": "",
            "fr_government_indicator": "",
            "fr_production_indicator": "",
            "fr_sales_indicator": "",
            "fr_labour_indicator": "",
            "fr_housing_indicator": "",
            "fr_confidence_indicator": "Aggregate Business Confidence",
            "jp_growth_indicator": "",
            "jp_inflation_indicator": "",
            "jp_government_indicator": "",
            "jp_production_indicator": "",
            "jp_sales_indicator": "",
            "jp_labour_indicator": "",
            "jp_housing_indicator": "",
            "jp_confidence_indicator": "",
        }

        result = get_selected_indicators_by_category(
            EconomicDataLocationChoices.US, EconomicChartsFrontData(**front_data)
        )
        assert result == [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth", "Real GDP"],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.INFLATION,
                selected_indicators=["CPI"],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GOVERNMENT,
                selected_indicators=[],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.PRODUCTION,
                selected_indicators=[],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.SALES,
                selected_indicators=[],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.LABOUR,
                selected_indicators=[],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.HOUSING,
                selected_indicators=[],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.CONFIDENCE,
                selected_indicators=[],
            ),
        ]

    def test_get_default_indicator_selections_uses_db_default_mode(self):
        """
        GIVEN GDP / CPI / debt indicators with distinct DB default modes
        WHEN building default chart selections for US
        THEN each selection encodes that indicator's default_mode
        """
        EconomicIndicatorInformationModel.objects.create(
            id=101,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP",
            name="US GDP",
            technical_name="us_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GDP",
            default_mode=IndicatorDisplayModeChoices.ANNUAL,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=102,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.INFLATION,
            type="Consumer Price Index",
            name="US CPI",
            technical_name="us_cpi_main",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="CPIAUCSL",
            default_mode=IndicatorDisplayModeChoices.ANNUAL,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=103,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            type="Government Debt (% of GDP)",
            name="US Debt",
            technical_name="us_debt",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GFDEGDQ188S",
            default_mode=IndicatorDisplayModeChoices.RAW,
        )
        result = get_default_indicator_selections(EconomicDataLocationChoices.US)
        assert result == _EconomicChartsCategoryDefaults(
            growth_indicator="GDP|Annual",
            inflation_indicator="Consumer Price Index|Annual",
            government_indicator="Government Debt (% of GDP)|Raw",
            production_indicator="Industrial Production|Raw",
            sales_indicator="Retail Sales|Raw",
            labour_indicator="Unemployment Rate|Raw",
            housing_indicator="Home Prices|Raw",
            confidence_indicator="Consumer Confidence|Raw",
        )

    def test_get_dropdown_values_returns_correct_structure(self):
        """
        GIVEN existing indicators
        WHEN getting economic charts dropdown values
        THEN the correct structure is returned
        """
        result = get_economic_charts_dropdown_values(self.location)
        assert result == _EconomicChartsDropdownValues(
            categories=[
                "Growth",
                "Inflation",
                "Government",
                "Production",
                "Sales",
                "Labour",
                "Housing",
                "Confidence",
            ],
            locations=["United States", "Europe", "France", "Japan"],
            indicators_by_category=[
                {
                    "category": "Growth",
                    "indicators": [
                        {
                            "type": "GDP Growth",
                            "name": "GDP Growth",
                            "default_mode": "Raw",
                        }
                    ],
                },
                {
                    "category": "Inflation",
                    "indicators": [
                        {"type": "CPI", "name": "CPI", "default_mode": "Raw"}
                    ],
                },
                {"category": "Government", "indicators": []},
                {"category": "Production", "indicators": []},
                {"category": "Sales", "indicators": []},
                {"category": "Labour", "indicators": []},
                {"category": "Housing", "indicators": []},
                {"category": "Confidence", "indicators": []},
            ],
        )

    def test_get_dropdown_values_different_location(self):
        """
        GIVEN indicators for different locations
        WHEN getting dropdown values for FR
        THEN only FR indicators are returned
        """
        result = get_economic_charts_dropdown_values(EconomicDataLocationChoices.FR)
        assert result == _EconomicChartsDropdownValues(
            categories=[
                "Growth",
                "Inflation",
                "Government",
                "Production",
                "Sales",
                "Labour",
                "Housing",
                "Confidence",
            ],
            locations=["United States", "Europe", "France", "Japan"],
            indicators_by_category=[
                {
                    "category": "Growth",
                    "indicators": [
                        {
                            "type": "GDP Growth",
                            "name": "GDP Growth",
                            "default_mode": "Raw",
                        }
                    ],
                },
                {"category": "Inflation", "indicators": []},
                {"category": "Government", "indicators": []},
                {"category": "Production", "indicators": []},
                {"category": "Sales", "indicators": []},
                {"category": "Labour", "indicators": []},
                {"category": "Housing", "indicators": []},
                {"category": "Confidence", "indicators": []},
            ],
        )

    @patch("data_visualization.services.economic_charts.get_cached_economic_display")
    @patch("data_visualization.services.economic_charts.set_cached_economic_display")
    def test_get_charts_data_uses_redis_cache(self, mock_set_cache, mock_get_cache):
        """
        GIVEN a Redis cache hit for the charts fingerprint
        WHEN getting economic charts data
        THEN the cached payload is returned without recomputing
        """
        cached_payload = [
            _EconomicChartsData(
                category="Growth",
                category_data=[
                    {
                        "period": "2024Q2",
                        "data_value": 3.0,
                        "indicator_name": "GDP Growth",
                    }
                ],
                value_axis_label="Data Value",
            )
        ]
        mock_get_cache.return_value = cached_payload
        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth"],
            ),
        ]

        result = get_economic_charts_data(self.location, selected_indicators)

        assert result == cached_payload
        mock_set_cache.assert_not_called()

    def test_get_charts_data(self):
        """
        GIVEN existing economic data with selected indicators
        WHEN getting economic charts data
        THEN the correct data is returned (sorted by period descending)
        """
        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            _EconomicChartsData(
                category="Growth",
                category_data=[
                    {
                        "period": "2024Q2",
                        "data_value": 3.0,
                        "indicator_name": "GDP Growth",
                    },
                    {
                        "period": "2024Q1",
                        "data_value": 2.5,
                        "indicator_name": "GDP Growth",
                    },
                ],
                value_axis_label="Data Value",
            ),
            _EconomicChartsData(
                category="Inflation", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]

    def test_get_charts_data_inflation_category(self):
        """
        GIVEN existing inflation data with selected indicators
        WHEN getting economic charts data
        THEN inflation data is returned correctly (sorted by period descending)
        """
        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.INFLATION,
                selected_indicators=["CPI"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            _EconomicChartsData(
                category="Growth", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Inflation",
                category_data=[
                    {
                        "period": "2024-02",
                        "data_value": 2.1,
                        "indicator_name": "CPI",
                    },
                    {
                        "period": "2024-01",
                        "data_value": 2.0,
                        "indicator_name": "CPI",
                    },
                ],
                value_axis_label="Data Value",
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]

    def test_get_charts_data_with_selected_indicators(self):
        """
        GIVEN selected indicators for growth only
        WHEN getting economic charts data
        THEN growth data is filtered, inflation returns empty (no selection = no data)
        """
        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth"],
            ),
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.INFLATION,
                selected_indicators=[],
            ),
        ]

        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            _EconomicChartsData(
                category="Growth",
                category_data=[
                    {
                        "period": "2024Q2",
                        "data_value": 3.0,
                        "indicator_name": "GDP Growth",
                    },
                    {
                        "period": "2024Q1",
                        "data_value": 2.5,
                        "indicator_name": "GDP Growth",
                    },
                ],
                value_axis_label="Data Value",
            ),
            _EconomicChartsData(
                category="Inflation", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]

    def test_get_charts_data_empty_selected_list_returns_all_empty(self):
        """
        GIVEN empty selected indicators list
        WHEN getting economic charts data
        THEN all categories returned with empty data
        """
        result = get_economic_charts_data(self.location, [])
        assert result == [
            _EconomicChartsData(
                category="Growth", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Inflation", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]

    def test_get_charts_data_empty_category(self):
        """
        GIVEN a category with no indicators but with selected indicators
        WHEN getting economic charts data
        THEN empty category_data is returned for that category
        """
        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.HOUSING,
                selected_indicators=["Housing Starts"],  # Non-existent indicator
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            _EconomicChartsData(
                category="Growth", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Inflation", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]

    def test_parse_selected_indicator_and_mode(self):
        """
        GIVEN [Location|]Type[|MODE] strings
        WHEN parsing
        THEN an optional location prefix and mode suffix are peeled off
        """
        assert _parse_selected_indicator_and_mode("GDP") == {
            "type": "GDP",
            "mode": IndicatorDisplayModeChoices.RAW,
            "location": None,
        }
        assert _parse_selected_indicator_and_mode("GDP|Annual") == {
            "type": "GDP",
            "mode": IndicatorDisplayModeChoices.ANNUAL,
            "location": None,
        }
        assert _parse_selected_indicator_and_mode("DE|GDP") == {
            "type": "GDP",
            "mode": IndicatorDisplayModeChoices.RAW,
            "location": EconomicDataLocationChoices.DE,
        }
        assert _parse_selected_indicator_and_mode("DE|GDP|Annual") == {
            "type": "GDP",
            "mode": IndicatorDisplayModeChoices.ANNUAL,
            "location": EconomicDataLocationChoices.DE,
        }
        assert _parse_selected_indicator_and_mode("GDP|Annualized Quarter") == {
            "type": "GDP",
            "mode": IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
            "location": None,
        }
        with self.assertRaises(ValueError):
            _parse_selected_indicator_and_mode("CPI|BAD")

    def test_change_series_mode_quarterly_qoq_qoqy_and_yoy(self):
        """
        GIVEN quarterly level points
        WHEN changing to QoQ, QoQy, and YoY modes
        THEN percent changes use QoQ lag, annualized QoQ, and YoY lag
        """
        points = [
            _TimeSeriesPoint(date(2023, 1, 1), 100.0),
            _TimeSeriesPoint(date(2023, 4, 1), 102.0),
            _TimeSeriesPoint(date(2023, 7, 1), 104.0),
            _TimeSeriesPoint(date(2023, 10, 1), 106.0),
            _TimeSeriesPoint(date(2024, 1, 1), 110.0),
        ]
        qoq = _change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            IndicatorDisplayModeChoices.QUARTER,
        )
        assert qoq[0] == _TimeSeriesPoint(date(2023, 4, 1), 2.0)
        assert abs(qoq[-1].value - (110.0 - 106.0) / 106.0 * 100) < 1e-9

        qoqy = _change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
        )
        assert qoqy == [
            _TimeSeriesPoint(date(2023, 4, 1), ((102.0 / 100.0) ** 4 - 1) * 100),
            _TimeSeriesPoint(date(2023, 7, 1), ((104.0 / 102.0) ** 4 - 1) * 100),
            _TimeSeriesPoint(date(2023, 10, 1), ((106.0 / 104.0) ** 4 - 1) * 100),
            _TimeSeriesPoint(date(2024, 1, 1), ((110.0 / 106.0) ** 4 - 1) * 100),
        ]

        yoy = _change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            IndicatorDisplayModeChoices.ANNUAL,
        )
        assert yoy == [_TimeSeriesPoint(date(2024, 1, 1), 10.0)]

    def test_change_series_mode_monthly_missing_prior_is_dropped(self):
        """
        GIVEN monthly points with insufficient history for YoY
        WHEN changing to YoY / QoQ modes
        THEN points without a prior are omitted
        """
        points = [
            _TimeSeriesPoint(date(2024, 1, 1), 100.0),
            _TimeSeriesPoint(date(2024, 2, 1), 101.0),
            _TimeSeriesPoint(date(2024, 3, 1), 102.0),
        ]
        assert (
            _change_series_mode(
                points,
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.ANNUAL,
            )
            == []
        )
        qoq = _change_series_mode(
            points,
            EconomicPublicationFrequencyChoices.MONTHLY,
            IndicatorDisplayModeChoices.QUARTER,
        )
        assert qoq == []  # need 3-month lag; only 3 points → index 3 is out of range

    def test_filter_time_series_by_period_window_truncates(self):
        """
        GIVEN a long series
        WHEN filtering to a 1Y period window
        THEN only the last year of points remains
        """
        time_series = [
            _TimeSeriesPoint(date(2020, 1, 1), 1.0),
            _TimeSeriesPoint(date(2023, 6, 1), 2.0),
            _TimeSeriesPoint(date(2024, 1, 1), 3.0),
            _TimeSeriesPoint(date(2024, 6, 1), 4.0),
        ]
        time_series_in_period_window = _filter_time_series_by_period_window(
            time_series, ChartPeriodWindow.ONE_YEAR
        )
        assert time_series_in_period_window == [
            _TimeSeriesPoint(date(2023, 6, 1), 2.0),
            _TimeSeriesPoint(date(2024, 1, 1), 3.0),
            _TimeSeriesPoint(date(2024, 6, 1), 4.0),
        ]
        assert (
            _filter_time_series_by_period_window(time_series, ChartPeriodWindow.MAX)
            == time_series
        )

    def test_get_charts_data_yoy_and_window(self):
        """
        GIVEN quarterly GDP levels and a YOY selection with 1Y window
        WHEN getting chart data
        THEN values are YoY % and truncated by window
        """
        EconomicDataModel.objects.filter(indicator=self.indicator_growth).delete()
        for period, value in [
            (date(2022, 1, 1), 100.0),
            (date(2022, 4, 1), 101.0),
            (date(2022, 7, 1), 102.0),
            (date(2022, 10, 1), 103.0),
            (date(2023, 1, 1), 110.0),
            (date(2023, 4, 1), 112.0),
            (date(2023, 7, 1), 114.0),
            (date(2023, 10, 1), 116.0),
            (date(2024, 1, 1), 120.0),
            (date(2024, 4, 1), 122.0),
        ]:
            EconomicDataModel.objects.create(
                indicator=self.indicator_growth,
                period=period,
                data_value=value,
            )

        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth|Annual"],
            ),
        ]
        result = get_economic_charts_data(
            self.location,
            selected_indicators,
            period_window=ChartPeriodWindow.ONE_YEAR,
        )
        assert result == [
            _EconomicChartsData(
                category="Growth",
                category_data=[
                    {
                        "period": "2024Q2",
                        "data_value": (122.0 - 112.0) / 112.0 * 100,
                        "indicator_name": "GDP Growth (in %)",
                    },
                    {
                        "period": "2024Q1",
                        "data_value": (120.0 - 110.0) / 110.0 * 100,
                        "indicator_name": "GDP Growth (in %)",
                    },
                    {
                        "period": "2023Q4",
                        "data_value": (116.0 - 103.0) / 103.0 * 100,
                        "indicator_name": "GDP Growth (in %)",
                    },
                    {
                        "period": "2023Q3",
                        "data_value": (114.0 - 102.0) / 102.0 * 100,
                        "indicator_name": "GDP Growth (in %)",
                    },
                    {
                        "period": "2023Q2",
                        "data_value": (112.0 - 101.0) / 101.0 * 100,
                        "indicator_name": "GDP Growth (in %)",
                    },
                ],
                value_axis_label="Data Value (%)",
            ),
            _EconomicChartsData(
                category="Inflation", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]

    def test_get_charts_data_europe_plots_selected_country_curves(self):
        """
        GIVEN GDP series for DE / ES / IT / FR
        WHEN getting Europe charts with only DE and FR selected
        THEN only those country curves appear
        """
        period = date(2024, 4, 1)
        for indicator_id, location, name, ticker, value in [
            (61, EconomicDataLocationChoices.DE, "Germany Real GDP", "gdp_de", 100.0),
            (70, EconomicDataLocationChoices.ES, "Spain Real GDP", "gdp_es", 110.0),
            (79, EconomicDataLocationChoices.IT, "Italy Real GDP", "gdp_it", 120.0),
            (27, EconomicDataLocationChoices.FR, "France Real GDP", "gdp_fr", 130.0),
        ]:
            indicator = EconomicIndicatorInformationModel.objects.create(
                id=indicator_id,
                location=location,
                category=EconomicDataCategoryChoices.GROWTH,
                type="GDP",
                name=name,
                technical_name="GDP and main aggregates",
                frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
                source=EconomicDataSourceChoices.EUROSTAT,
                ticker=ticker,
            )
            EconomicDataModel.objects.create(
                indicator=indicator,
                period=period,
                data_value=value,
            )

        selected_indicators = [
            _SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["DE|GDP|Raw", "FR|GDP|Raw"],
            ),
        ]
        result = get_economic_charts_data(
            EconomicDataLocationChoices.EU, selected_indicators
        )
        assert result == [
            _EconomicChartsData(
                category="Growth",
                category_data=[
                    {
                        "period": "2024Q2",
                        "data_value": 100.0,
                        "indicator_name": "Germany — GDP",
                    },
                    {
                        "period": "2024Q2",
                        "data_value": 130.0,
                        "indicator_name": "France — GDP",
                    },
                ],
                value_axis_label="Data Value",
            ),
            _EconomicChartsData(
                category="Inflation", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Government", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Production", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Sales", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Labour", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Housing", category_data=[], value_axis_label="Data Value"
            ),
            _EconomicChartsData(
                category="Confidence", category_data=[], value_axis_label="Data Value"
            ),
        ]


class TestBuildValueAxisLabel(SimpleTestCase):
    """Economic chart Y-axis titles."""

    def test_growth_mode_is_percent(self):
        """
        GIVEN Annual display mode
        WHEN building the value axis label
        THEN the axis is labeled as percent
        """
        assert (
            _build_value_axis_label(mode=IndicatorDisplayModeChoices.ANNUAL)
            == "Data Value (%)"
        )

    def test_amount_raw_includes_unit(self):
        """
        GIVEN Raw mode with billion EUR base
        WHEN building the value axis label
        THEN the axis includes the compact unit
        """
        assert (
            _build_value_axis_label(
                mode=IndicatorDisplayModeChoices.RAW,
                base_unit=IndicatorBaseUnitChoices.B,
                base_currency="EUR",
            )
            == "Data Value (in bEUR)"
        )
