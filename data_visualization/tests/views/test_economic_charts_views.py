import json
from datetime import date
from typing import Any, Dict, Protocol, Union

from django.test import Client, TestCase
from django.test.utils import ContextList
from freezegun import freeze_time  # type: ignore[reportMissingImports]

from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


class TestResponse(Protocol):
    """Protocol for Django test client response with context."""

    @property
    def context(self) -> Union[ContextList, Dict[str, Any]]: ...


def _get_response_context(response: TestResponse) -> Dict[str, object]:
    """Helper to extract and parse response context."""
    context: Dict[str, Any] = dict(response.context or {})
    return {
        "zone": context.get("zone"),
        "dropdown_values": json.loads(context.get("dropdown_values", "{}")),
        "economic_data": json.loads(context.get("economic_data", "[]")),
        "categories": json.loads(context.get("categories", "[]")),
        "selected_values": json.loads(context.get("selected_values", "{}")),
    }


@freeze_time("2025-12-16")
class TestEconomicChartsView(TestCase):
    """Test cases for economic_charts_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/economic-charts/"

        # Create US indicators
        self.indicator_us_growth = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP Growth",
            name="US GDP Growth",
            technical_name="us_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_us_quarterly_growth = (
            EconomicIndicatorInformationModel.objects.create(
                id=2,
                location=EconomicDataLocationChoices.US,
                category=EconomicDataCategoryChoices.GROWTH,
                type="GDP Growth (QoQ)",
                name="US GDP Growth (QoQ)",
                technical_name="us_gdp_growth_qoq",
                frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
                source=EconomicDataSourceChoices.INSEE,
                ticker="001565531",
            )
        )
        self.indicator_us_inflation = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.INFLATION,
            type="CPI",
            name="US CPI",
            technical_name="us_cpi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565532",
        )

        # Create FR indicator
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=4,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP Growth",
            name="FR GDP Growth",
            technical_name="fr_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565533",
        )

        # Create economic data
        self.period1 = date(2024, 1, 1)
        EconomicDataModel.objects.create(
            indicator=self.indicator_us_growth,
            period=self.period1,
            data_value=2.5,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_us_quarterly_growth,
            period=self.period1,
            data_value=0.5,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_us_inflation,
            period=date(2024, 1, 15),
            data_value=2.0,
        )

    def test_economic_charts_view_no_parameters(self):
        """
        GIVEN no parameters
        WHEN accessing economic charts view
        THEN default values are used with correct structure
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "zone": "United States",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Labour",
                    "Housing",
                    "Production",
                    "Confidence",
                    "Sales",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth", "GDP Growth (QoQ)"],
                    },
                    {"category": "Inflation", "indicators": ["CPI"]},
                    {"category": "Government", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Confidence", "indicators": []},
                    {"category": "Sales", "indicators": []},
                ],
            },
            "economic_data": [
                {"category": "Growth", "category_data": []},
                {"category": "Inflation", "category_data": []},
                {"category": "Government", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Production", "category_data": []},
                {"category": "Confidence", "category_data": []},
                {"category": "Sales", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Labour",
                "Housing",
                "Production",
                "Confidence",
                "Sales",
            ],
            "selected_values": {
                "zone": "United States",
                "us_growth_indicator": "",
                "us_inflation_indicator": "",
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
            },
        }

    def test_economic_charts_view_with_selected_indicator(self):
        """
        GIVEN selected indicator in query parameters
        WHEN accessing economic charts view
        THEN selected indicator is in selected values and data is filtered
        """
        params = {
            "zone": str(EconomicDataLocationChoices.US.label),
            "us_growth_indicator": "GDP Growth",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "zone": "United States",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Labour",
                    "Housing",
                    "Production",
                    "Confidence",
                    "Sales",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth", "GDP Growth (QoQ)"],
                    },
                    {"category": "Inflation", "indicators": ["CPI"]},
                    {"category": "Government", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Confidence", "indicators": []},
                    {"category": "Sales", "indicators": []},
                ],
            },
            "economic_data": [
                {
                    "category": "Growth",
                    "category_data": [
                        {
                            "period": "2024",
                            "data_value": 2.5,
                            "indicator_name": "GDP Growth",
                        }
                    ],
                },
                {"category": "Inflation", "category_data": []},
                {"category": "Government", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Production", "category_data": []},
                {"category": "Confidence", "category_data": []},
                {"category": "Sales", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Labour",
                "Housing",
                "Production",
                "Confidence",
                "Sales",
            ],
            "selected_values": {
                "zone": "United States",
                "us_growth_indicator": "GDP Growth",
                "us_inflation_indicator": "",
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
            },
        }

    def test_economic_charts_view_with_multiple_selected_indicators(self):
        """
        GIVEN multiple selected indicators (comma-separated)
        WHEN accessing economic charts view
        THEN all selected indicators are preserved
        """
        params = {
            "zone": str(EconomicDataLocationChoices.US.label),
            "us_growth_indicator": "GDP Growth,GDP Growth (QoQ)",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "zone": "United States",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Labour",
                    "Housing",
                    "Production",
                    "Confidence",
                    "Sales",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth", "GDP Growth (QoQ)"],
                    },
                    {"category": "Inflation", "indicators": ["CPI"]},
                    {"category": "Government", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Confidence", "indicators": []},
                    {"category": "Sales", "indicators": []},
                ],
            },
            "economic_data": [
                {
                    "category": "Growth",
                    "category_data": [
                        {
                            "period": "2024Q1",
                            "data_value": 0.5,
                            "indicator_name": "GDP Growth (QoQ)",
                        },
                        {
                            "period": "2024",
                            "data_value": 2.5,
                            "indicator_name": "GDP Growth",
                        },
                    ],
                },
                {"category": "Inflation", "category_data": []},
                {"category": "Government", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Production", "category_data": []},
                {"category": "Confidence", "category_data": []},
                {"category": "Sales", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Labour",
                "Housing",
                "Production",
                "Confidence",
                "Sales",
            ],
            "selected_values": {
                "zone": "United States",
                "us_growth_indicator": "GDP Growth,GDP Growth (QoQ)",
                "us_inflation_indicator": "",
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
            },
        }

    def test_economic_charts_view_fr_zone_with_fr_data(self):
        """
        GIVEN FR zone with FR data created
        WHEN accessing economic charts view
        THEN FR indicators data is returned
        """
        # Create data for FR indicator
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=self.period1,
            data_value=1.5,
        )

        params = {
            "zone": str(EconomicDataLocationChoices.FR.label),
            "fr_growth_indicator": "GDP Growth",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "zone": "France",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Labour",
                    "Housing",
                    "Production",
                    "Confidence",
                    "Sales",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {"category": "Growth", "indicators": ["GDP Growth"]},
                    {"category": "Inflation", "indicators": []},
                    {"category": "Government", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Confidence", "indicators": []},
                    {"category": "Sales", "indicators": []},
                ],
            },
            "economic_data": [
                {
                    "category": "Growth",
                    "category_data": [
                        {
                            "period": "2024Q1",
                            "data_value": 1.5,
                            "indicator_name": "GDP Growth",
                        }
                    ],
                },
                {"category": "Inflation", "category_data": []},
                {"category": "Government", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Production", "category_data": []},
                {"category": "Confidence", "category_data": []},
                {"category": "Sales", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Labour",
                "Housing",
                "Production",
                "Confidence",
                "Sales",
            ],
            "selected_values": {
                "zone": "France",
                "us_growth_indicator": "",
                "us_inflation_indicator": "",
                "us_government_indicator": "",
                "us_labour_indicator": "",
                "us_housing_indicator": "",
                "us_production_indicator": "",
                "us_confidence_indicator": "",
                "us_sales_indicator": "",
                "fr_growth_indicator": "GDP Growth",
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
            },
        }
