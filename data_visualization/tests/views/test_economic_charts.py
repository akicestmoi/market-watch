"""Tests for economic chart views."""

import json
from collections.abc import Mapping
from datetime import date
from typing import Protocol, TypedDict

from django.test import Client, TestCase
from django.test.utils import ContextList
from freezegun import freeze_time

from data_visualization.services.economic_charts import (
    EconomicChartsData,
    EconomicChartsDropdownValues,
    EconomicChartsFrontData,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


class EconomicChartsResponseContext(TypedDict):
    """Parsed template context fields accessed by economic charts view tests."""

    zone: str
    period_window: str
    dropdown_values: EconomicChartsDropdownValues
    economic_data: list[EconomicChartsData]
    categories: list[str]
    selected_values: EconomicChartsFrontData


class TestResponse(Protocol):
    """Protocol for Django test client response with context."""

    @property
    def context(self) -> ContextList | Mapping[str, object] | None:
        """Return the Django template context from the response."""
        ...


def _context_as_str(context: Mapping[str, object], key: str, default: str) -> str:
    """Return a context value coerced to str for JSON parsing."""
    value = context.get(key, default)
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _get_response_context(response: TestResponse) -> EconomicChartsResponseContext:
    """Helper to extract and parse response context."""
    context: Mapping[str, object] = dict(response.context or {})
    dropdown_values: EconomicChartsDropdownValues = json.loads(
        _context_as_str(context, "dropdown_values", "{}")
    )
    economic_data: list[EconomicChartsData] = json.loads(
        _context_as_str(context, "economic_data", "[]")
    )
    categories: list[str] = json.loads(_context_as_str(context, "categories", "[]"))
    selected_values: EconomicChartsFrontData = json.loads(
        _context_as_str(context, "selected_values", "{}")
    )
    return EconomicChartsResponseContext(
        zone=_context_as_str(context, "zone", ""),
        period_window=_context_as_str(context, "period_window", ""),
        dropdown_values=dropdown_values,
        economic_data=economic_data,
        categories=categories,
        selected_values=selected_values,
    )


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
            "period_window": "5Y",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Production",
                    "Sales",
                    "Labour",
                    "Housing",
                    "Confidence",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth", "GDP Growth (QoQ)"],
                    },
                    {
                        "category": "Inflation",
                        "indicators": ["CPI"],
                    },
                    {
                        "category": "Government",
                        "indicators": [],
                    },
                    {
                        "category": "Production",
                        "indicators": [],
                    },
                    {
                        "category": "Sales",
                        "indicators": [],
                    },
                    {
                        "category": "Labour",
                        "indicators": [],
                    },
                    {
                        "category": "Housing",
                        "indicators": [],
                    },
                    {
                        "category": "Confidence",
                        "indicators": [],
                    },
                ],
            },
            "economic_data": [
                {"category": "Growth", "category_data": []},
                {"category": "Inflation", "category_data": []},
                {"category": "Government", "category_data": []},
                {"category": "Production", "category_data": []},
                {"category": "Sales", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Confidence", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Production",
                "Sales",
                "Labour",
                "Housing",
                "Confidence",
            ],
            "selected_values": {
                "zone": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "",
                "us_inflation_indicator": "",
                "us_government_indicator": "",
                "us_production_indicator": "",
                "us_sales_indicator": "",
                "us_labour_indicator": "",
                "us_housing_indicator": "",
                "us_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "",
                "jp_inflation_indicator": "",
                "jp_government_indicator": "",
                "jp_production_indicator": "",
                "jp_sales_indicator": "",
                "jp_labour_indicator": "",
                "jp_housing_indicator": "",
                "jp_confidence_indicator": "",
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
            "period_window": "5Y",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Production",
                    "Sales",
                    "Labour",
                    "Housing",
                    "Confidence",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth", "GDP Growth (QoQ)"],
                    },
                    {
                        "category": "Inflation",
                        "indicators": ["CPI"],
                    },
                    {
                        "category": "Government",
                        "indicators": [],
                    },
                    {
                        "category": "Production",
                        "indicators": [],
                    },
                    {
                        "category": "Sales",
                        "indicators": [],
                    },
                    {
                        "category": "Labour",
                        "indicators": [],
                    },
                    {
                        "category": "Housing",
                        "indicators": [],
                    },
                    {
                        "category": "Confidence",
                        "indicators": [],
                    },
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
                {"category": "Production", "category_data": []},
                {"category": "Sales", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Confidence", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Production",
                "Sales",
                "Labour",
                "Housing",
                "Confidence",
            ],
            "selected_values": {
                "zone": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "GDP Growth",
                "us_inflation_indicator": "",
                "us_government_indicator": "",
                "us_production_indicator": "",
                "us_sales_indicator": "",
                "us_labour_indicator": "",
                "us_housing_indicator": "",
                "us_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "",
                "jp_inflation_indicator": "",
                "jp_government_indicator": "",
                "jp_production_indicator": "",
                "jp_sales_indicator": "",
                "jp_labour_indicator": "",
                "jp_housing_indicator": "",
                "jp_confidence_indicator": "",
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
            "period_window": "5Y",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Production",
                    "Sales",
                    "Labour",
                    "Housing",
                    "Confidence",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth", "GDP Growth (QoQ)"],
                    },
                    {
                        "category": "Inflation",
                        "indicators": ["CPI"],
                    },
                    {
                        "category": "Government",
                        "indicators": [],
                    },
                    {
                        "category": "Production",
                        "indicators": [],
                    },
                    {
                        "category": "Sales",
                        "indicators": [],
                    },
                    {
                        "category": "Labour",
                        "indicators": [],
                    },
                    {
                        "category": "Housing",
                        "indicators": [],
                    },
                    {
                        "category": "Confidence",
                        "indicators": [],
                    },
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
                {"category": "Production", "category_data": []},
                {"category": "Sales", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Confidence", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Production",
                "Sales",
                "Labour",
                "Housing",
                "Confidence",
            ],
            "selected_values": {
                "zone": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "GDP Growth,GDP Growth (QoQ)",
                "us_inflation_indicator": "",
                "us_government_indicator": "",
                "us_production_indicator": "",
                "us_sales_indicator": "",
                "us_labour_indicator": "",
                "us_housing_indicator": "",
                "us_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "",
                "jp_inflation_indicator": "",
                "jp_government_indicator": "",
                "jp_production_indicator": "",
                "jp_sales_indicator": "",
                "jp_labour_indicator": "",
                "jp_housing_indicator": "",
                "jp_confidence_indicator": "",
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
            "period_window": "5Y",
            "dropdown_values": {
                "categories": [
                    "Growth",
                    "Inflation",
                    "Government",
                    "Production",
                    "Sales",
                    "Labour",
                    "Housing",
                    "Confidence",
                ],
                "locations": ["United States", "Europe", "France", "Japan"],
                "indicators_by_category": [
                    {
                        "category": "Growth",
                        "indicators": ["GDP Growth"],
                    },
                    {
                        "category": "Inflation",
                        "indicators": [],
                    },
                    {
                        "category": "Government",
                        "indicators": [],
                    },
                    {
                        "category": "Production",
                        "indicators": [],
                    },
                    {
                        "category": "Sales",
                        "indicators": [],
                    },
                    {
                        "category": "Labour",
                        "indicators": [],
                    },
                    {
                        "category": "Housing",
                        "indicators": [],
                    },
                    {
                        "category": "Confidence",
                        "indicators": [],
                    },
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
                {"category": "Production", "category_data": []},
                {"category": "Sales", "category_data": []},
                {"category": "Labour", "category_data": []},
                {"category": "Housing", "category_data": []},
                {"category": "Confidence", "category_data": []},
            ],
            "categories": [
                "Growth",
                "Inflation",
                "Government",
                "Production",
                "Sales",
                "Labour",
                "Housing",
                "Confidence",
            ],
            "selected_values": {
                "zone": "France",
                "period_window": "5Y",
                "us_growth_indicator": "",
                "us_inflation_indicator": "",
                "us_government_indicator": "",
                "us_production_indicator": "",
                "us_sales_indicator": "",
                "us_labour_indicator": "",
                "us_housing_indicator": "",
                "us_confidence_indicator": "",
                "fr_growth_indicator": "GDP Growth",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "",
                "jp_inflation_indicator": "",
                "jp_government_indicator": "",
                "jp_production_indicator": "",
                "jp_sales_indicator": "",
                "jp_labour_indicator": "",
                "jp_housing_indicator": "",
                "jp_confidence_indicator": "",
            },
        }

    def test_economic_charts_view_fr_defaults_and_period_window(self):
        """
        GIVEN France zone with no indicator query params
        WHEN accessing economic charts view
        THEN FR Type|MODE defaults and period_window 5Y are applied
        """
        response = self.client.get(
            self.base_url, {"zone": str(EconomicDataLocationChoices.FR.label)}
        )
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context["period_window"] == "5Y"
        selected = response_context["selected_values"]
        assert selected["period_window"] == "5Y"
        assert selected["fr_growth_indicator"] == "GDP|YOY"
        assert selected["fr_inflation_indicator"] == "Consumer Price Index|YOY"
        assert selected["fr_government_indicator"] == "Government Debt (% of GDP)|ABS"
        assert selected["fr_production_indicator"] == "Industrial Production|ABS"
        assert selected["fr_sales_indicator"] == "Retail Sales|YOY"
        assert selected["fr_labour_indicator"] == "Unemployment Rate|ABS"
        assert selected["fr_housing_indicator"] == "Home Prices|ABS"
        assert (
            selected["fr_confidence_indicator"] == "Aggregate Business Confidence|ABS"
        )
