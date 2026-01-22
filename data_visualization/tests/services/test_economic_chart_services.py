from datetime import date

from django.test import TestCase

from data_visualization.services.economic_chart_services import (
    EconomicChartsData,
    EconomicChartsDropdownValues,
    EconomicChartsFrontData,
    SelectedIndicatorsByCategory,
    _format_period,
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
)


class TestEconomicChartServices(TestCase):
    """Test cases for economic chart services."""

    def setUp(self):
        """Set up test fixtures."""
        self.location = EconomicDataLocationChoices.US.value

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
        assert _format_period(test_date, "MONTHLY") == "2024-01"
        assert _format_period(test_date, "QUARTERLY") == "2024Q1"
        assert _format_period(test_date, "ANNUAL") == "2024"
        assert _format_period(test_date, "UNKNOWN") == "2024-01-15"

        q3_date = date(2024, 7, 1)
        assert _format_period(q3_date, "QUARTERLY") == "2024Q3"

    def test_get_selected_indicators_us_zone(self):
        """
        GIVEN front data with US zone indicators
        WHEN get_selected_indicators_by_category is called
        THEN correct indicators are extracted for each category
        """
        front_data = {
            "zone": "United States",
            "us_growth_indicator": "GDP Growth,Real GDP",
            "us_inflation_indicator": "CPI",
            "us_government_indicator": "",
            "us_labour_indicator": "",
            "us_housing_indicator": "",
            "us_production_indicator": "",
            "us_confidence_indicator": "",
            "us_sales_indicator": "",
            "fr_growth_indicator": "",
            "fr_inflation_indicator": "",
            "fr_government_indicator": "",
            "fr_labour_indicator": "",
            "fr_housing_indicator": "",
            "fr_production_indicator": "",
            "fr_confidence_indicator": "Aggregate Business Confidence",
            "fr_sales_indicator": "",
            "jp_growth_indicator": "",
            "jp_inflation_indicator": "",
            "jp_government_indicator": "",
            "jp_labour_indicator": "",
            "jp_housing_indicator": "",
            "jp_production_indicator": "",
            "jp_confidence_indicator": "",
            "jp_sales_indicator": "",
        }

        result = get_selected_indicators_by_category(
            "United States", EconomicChartsFrontData(**front_data)
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
                category=EconomicDataCategoryChoices.LABOUR,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.HOUSING,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.PRODUCTION,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.CONFIDENCE,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategory(
                category=EconomicDataCategoryChoices.SALES,
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
                "Labour",
                "Housing",
                "Production",
                "Confidence",
                "Sales",
            ],
            locations=["United States", "Europe", "France", "Japan"],
            indicators_by_category=[
                {"category": "Growth", "indicators": ["GDP Growth"]},
                {"category": "Inflation", "indicators": ["CPI"]},
                {"category": "Government", "indicators": []},
                {"category": "Labour", "indicators": []},
                {"category": "Housing", "indicators": []},
                {"category": "Production", "indicators": []},
                {"category": "Confidence", "indicators": []},
                {"category": "Sales", "indicators": []},
            ],
        )

    def test_get_dropdown_values_different_location(self):
        """
        GIVEN indicators for different locations
        WHEN getting dropdown values for FR
        THEN only FR indicators are returned
        """
        result = get_economic_charts_dropdown_values(
            EconomicDataLocationChoices.FR.value
        )
        assert result == EconomicChartsDropdownValues(
            categories=[
                "Growth",
                "Inflation",
                "Government",
                "Labour",
                "Housing",
                "Production",
                "Confidence",
                "Sales",
            ],
            locations=["United States", "Europe", "France", "Japan"],
            indicators_by_category=[
                {"category": "Growth", "indicators": ["GDP Growth"]},
                {"category": "Inflation", "indicators": []},
                {"category": "Government", "indicators": []},
                {"category": "Labour", "indicators": []},
                {"category": "Housing", "indicators": []},
                {"category": "Production", "indicators": []},
                {"category": "Confidence", "indicators": []},
                {"category": "Sales", "indicators": []},
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
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
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
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
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
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
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
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
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
            EconomicChartsData(category="Labour", category_data=[]),
            EconomicChartsData(category="Housing", category_data=[]),
            EconomicChartsData(category="Production", category_data=[]),
            EconomicChartsData(category="Confidence", category_data=[]),
            EconomicChartsData(category="Sales", category_data=[]),
        ]
