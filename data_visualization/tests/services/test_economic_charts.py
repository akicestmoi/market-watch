"""Tests for economic chart visualization services."""

from datetime import date

from django.test import TestCase

from data_visualization.services.economic_charts import (
    ChartLevelPoint,
    ChartPeriodWindow,
    ChartSeriesMode,
    EconomicChartsData,
    EconomicChartsDropdownValues,
    EconomicChartsFrontData,
    SelectedIndicatorsByCategory,
    _format_period,
    _parse_indicator_selection,
    _apply_period_window,
    get_economic_charts_data,
    get_economic_charts_dropdown_values,
    get_selected_indicators_by_category,
    _transform_level_series,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
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

    def test_get_selected_indicators_us_zone(self):
        """
        GIVEN front data with US zone indicators
        WHEN get_selected_indicators_by_category is called
        THEN correct indicators are extracted for each category
        """
        front_data = {
            "zone": "United States",
            "period_window": ChartPeriodWindow.FIVE_YEARS.value,
            "us_growth_indicator": "GDP Growth,Real GDP",
            "us_inflation_indicator": "CPI",
            "us_government_indicator": "",
            "us_production_indicator": "",
            "us_sales_indicator": "",
            "us_labour_indicator": "",
            "us_housing_indicator": "",
            "us_confidence_indicator": "",
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
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth", "Real GDP"],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.INFLATION,
                selected_indicators=["CPI"],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GOVERNMENT,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.PRODUCTION,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.SALES,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.LABOUR,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.HOUSING,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.CONFIDENCE,
                selected_indicators=[],
            ),
        ]

    def test_get_dropdown_values_returns_correct_structure(self):
        """
        GIVEN existing indicators
        WHEN getting economic charts dropdown values
        THEN the correct structure is returned
        """
        result = get_economic_charts_dropdown_values(self.location)
        assert result == EconomicChartsDropdownValues(
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
                {"category": "Growth", "indicators": ["GDP Growth"]},
                {"category": "Inflation", "indicators": ["CPI"]},
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
        assert result == EconomicChartsDropdownValues(
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
                {"category": "Growth", "indicators": ["GDP Growth"]},
                {"category": "Inflation", "indicators": []},
                {"category": "Government", "indicators": []},
                {"category": "Production", "indicators": []},
                {"category": "Sales", "indicators": []},
                {"category": "Labour", "indicators": []},
                {"category": "Housing", "indicators": []},
                {"category": "Confidence", "indicators": []},
            ],
        )

    def test_get_charts_data(self):
        """
        GIVEN existing economic data with selected indicators
        WHEN getting economic charts data
        THEN the correct data is returned (sorted by period descending)
        """
        selected_indicators = [
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            EconomicChartsData(
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
            ),
            EconomicChartsData(category="Inflation", category_data=[]),
            EconomicChartsData(category="Government", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
        ]

    def test_get_charts_data_inflation_category(self):
        """
        GIVEN existing inflation data with selected indicators
        WHEN getting economic charts data
        THEN inflation data is returned correctly (sorted by period descending)
        """
        selected_indicators = [
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.INFLATION,
                selected_indicators=["CPI"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            EconomicChartsData(category="Growth", category_data=[]),
            EconomicChartsData(
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
            ),
            EconomicChartsData(category="Government", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
        ]

    def test_get_charts_data_with_selected_indicators(self):
        """
        GIVEN selected indicators for growth only
        WHEN getting economic charts data
        THEN growth data is filtered, inflation returns empty (no selection = no data)
        """
        selected_indicators = [
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth"],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.INFLATION,
                selected_indicators=[],
            ),
        ]

        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            EconomicChartsData(
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
            ),
            EconomicChartsData(category="Inflation", category_data=[]),
            EconomicChartsData(category="Government", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
        ]

    def test_get_charts_data_empty_selected_list_returns_all_empty(self):
        """
        GIVEN empty selected indicators list
        WHEN getting economic charts data
        THEN all categories returned with empty data
        """
        result = get_economic_charts_data(self.location, [])
        assert result == [
            EconomicChartsData(category="Growth", category_data=[]),
            EconomicChartsData(category="Inflation", category_data=[]),
            EconomicChartsData(category="Government", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
        ]

    def test_get_charts_data_empty_category(self):
        """
        GIVEN a category with no indicators but with selected indicators
        WHEN getting economic charts data
        THEN empty category_data is returned for that category
        """
        selected_indicators = [
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.HOUSING,
                selected_indicators=["Housing Starts"],  # Non-existent indicator
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == [
            EconomicChartsData(category="Growth", category_data=[]),
            EconomicChartsData(category="Inflation", category_data=[]),
            EconomicChartsData(category="Government", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
        ]

    def test__parse_indicator_selection(self):
        """
        GIVEN Type or Type|MODE strings
        WHEN parsing
        THEN type and mode are extracted with ABS when no mode; invalid mode raises
        """
        assert _parse_indicator_selection("GDP") == {
            "type": "GDP",
            "mode": ChartSeriesMode.ABS,
        }
        assert _parse_indicator_selection("GDP|YOY") == {
            "type": "GDP",
            "mode": ChartSeriesMode.YOY,
        }
        with self.assertRaises(ValueError):
            _parse_indicator_selection("CPI|BAD")

    def test_transform_quarterly_qoq_and_yoy(self):
        """
        GIVEN quarterly level points
        WHEN transforming QoQ and YoY
        THEN percent changes use 1 and 4 quarter lags
        """
        points = [
            ChartLevelPoint(date(2023, 1, 1), 100.0),
            ChartLevelPoint(date(2023, 4, 1), 102.0),
            ChartLevelPoint(date(2023, 7, 1), 104.0),
            ChartLevelPoint(date(2023, 10, 1), 106.0),
            ChartLevelPoint(date(2024, 1, 1), 110.0),
        ]
        qoq = _transform_level_series(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            ChartSeriesMode.QOQ,
        )
        assert qoq[0] == ChartLevelPoint(date(2023, 4, 1), 2.0)
        assert abs(qoq[-1].value - (110.0 - 106.0) / 106.0 * 100) < 1e-9

        yoy = _transform_level_series(
            points,
            EconomicPublicationFrequencyChoices.QUARTERLY,
            ChartSeriesMode.YOY,
        )
        assert yoy == [ChartLevelPoint(date(2024, 1, 1), 10.0)]

    def test_transform_monthly_missing_prior_is_dropped(self):
        """
        GIVEN monthly points with insufficient history for YoY
        WHEN transforming
        THEN points without a prior are omitted
        """
        points = [
            ChartLevelPoint(date(2024, 1, 1), 100.0),
            ChartLevelPoint(date(2024, 2, 1), 101.0),
            ChartLevelPoint(date(2024, 3, 1), 102.0),
        ]
        assert (
            _transform_level_series(
                points,
                EconomicPublicationFrequencyChoices.MONTHLY,
                ChartSeriesMode.YOY,
            )
            == []
        )
        qoq = _transform_level_series(
            points,
            EconomicPublicationFrequencyChoices.MONTHLY,
            ChartSeriesMode.QOQ,
        )
        assert qoq == []  # need 3-month lag; only 3 points → index 3 is out of range

    def test_apply_period_window_truncates(self):
        """
        GIVEN a long series
        WHEN applying a 1Y window
        THEN only the last year of points remains
        """
        points = [
            ChartLevelPoint(date(2020, 1, 1), 1.0),
            ChartLevelPoint(date(2023, 6, 1), 2.0),
            ChartLevelPoint(date(2024, 1, 1), 3.0),
            ChartLevelPoint(date(2024, 6, 1), 4.0),
        ]
        windowed = _apply_period_window(points, ChartPeriodWindow.ONE_YEAR)
        assert windowed == [
            ChartLevelPoint(date(2023, 6, 1), 2.0),
            ChartLevelPoint(date(2024, 1, 1), 3.0),
            ChartLevelPoint(date(2024, 6, 1), 4.0),
        ]
        assert _apply_period_window(points, ChartPeriodWindow.MAX) == points

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
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.GROWTH,
                selected_indicators=["GDP Growth|YOY"],
            ),
        ]
        result = get_economic_charts_data(
            self.location,
            selected_indicators,
            period_window=ChartPeriodWindow.ONE_YEAR,
        )
        growth = next(item for item in result if item["category"] == "Growth")
        assert growth["category_data"]
        assert all(
            point["indicator_name"] == "GDP Growth (in %)"
            for point in growth["category_data"]
        )
        # Latest YoY: 122 vs 112; window from max period 2024-04 back 1Y
        latest = growth["category_data"][0]
        assert latest["period"] == "2024Q2"
        assert abs(latest["data_value"] - (122.0 - 112.0) / 112.0 * 100) < 1e-9
        # Earliest in window should be >= 2023-04
        periods = [point["period"] for point in growth["category_data"]]
        assert "2022Q1" not in periods
