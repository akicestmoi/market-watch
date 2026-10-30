"""Tests for economic chart views."""

import json
from collections.abc import Mapping
from datetime import date
from typing import Protocol, TypedDict

from django.test import Client, TestCase
from django.test.utils import ContextList
from django.urls import get_resolver
from freezegun import freeze_time

# Load root URLConf before freezegun patches datetime (pydantic_ai TypeAdapter).
get_resolver().urlconf_module

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

    region: str
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
        region=_context_as_str(context, "region", ""),
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
            "region": "United States",
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
                        "indicators": [
                            {"type": "GDP Growth", "name": "GDP Growth"},
                            {"type": "GDP Growth (QoQ)", "name": "GDP Growth (QoQ)"},
                        ],
                    },
                    {
                        "category": "Inflation",
                        "indicators": [{"type": "CPI", "name": "CPI"}],
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
                "region": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "GDP|YOY",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY",
                "eu_government_indicator": "DE|Government Debt (% of GDP)|ABS,ES|Government Debt (% of GDP)|ABS,IT|Government Debt (% of GDP)|ABS,FR|Government Debt (% of GDP)|ABS",
                "eu_production_indicator": "DE|Industrial Production|ABS,ES|Industrial Production|ABS,IT|Industrial Production|ABS,FR|Industrial Production|ABS",
                "eu_sales_indicator": "DE|Retail Sales|YOY,ES|Retail Sales|YOY,IT|Retail Sales|YOY,FR|Retail Sales|YOY",
                "eu_labour_indicator": "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS",
                "eu_housing_indicator": "DE|Home Prices|ABS,ES|Home Prices|ABS,IT|Home Prices|ABS,FR|Home Prices|ABS",
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_with_selected_indicator(self):
        """
        GIVEN selected indicator in query parameters
        WHEN accessing economic charts view
        THEN selected indicator is in selected values and data is filtered
        """
        params = {
            "region": str(EconomicDataLocationChoices.US.label),
            "us_growth_indicator": "GDP Growth",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "United States",
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
                        "indicators": [
                            {"type": "GDP Growth", "name": "GDP Growth"},
                            {"type": "GDP Growth (QoQ)", "name": "GDP Growth (QoQ)"},
                        ],
                    },
                    {
                        "category": "Inflation",
                        "indicators": [{"type": "CPI", "name": "CPI"}],
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
                "region": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "GDP Growth",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY",
                "eu_government_indicator": "DE|Government Debt (% of GDP)|ABS,ES|Government Debt (% of GDP)|ABS,IT|Government Debt (% of GDP)|ABS,FR|Government Debt (% of GDP)|ABS",
                "eu_production_indicator": "DE|Industrial Production|ABS,ES|Industrial Production|ABS,IT|Industrial Production|ABS,FR|Industrial Production|ABS",
                "eu_sales_indicator": "DE|Retail Sales|YOY,ES|Retail Sales|YOY,IT|Retail Sales|YOY,FR|Retail Sales|YOY",
                "eu_labour_indicator": "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS",
                "eu_housing_indicator": "DE|Home Prices|ABS,ES|Home Prices|ABS,IT|Home Prices|ABS,FR|Home Prices|ABS",
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_with_multiple_selected_indicators(self):
        """
        GIVEN multiple selected indicators (comma-separated)
        WHEN accessing economic charts view
        THEN all selected indicators are preserved
        """
        params = {
            "region": str(EconomicDataLocationChoices.US.label),
            "us_growth_indicator": "GDP Growth,GDP Growth (QoQ)",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "United States",
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
                        "indicators": [
                            {"type": "GDP Growth", "name": "GDP Growth"},
                            {"type": "GDP Growth (QoQ)", "name": "GDP Growth (QoQ)"},
                        ],
                    },
                    {
                        "category": "Inflation",
                        "indicators": [{"type": "CPI", "name": "CPI"}],
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
                "region": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "GDP Growth,GDP Growth (QoQ)",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY",
                "eu_government_indicator": "DE|Government Debt (% of GDP)|ABS,ES|Government Debt (% of GDP)|ABS,IT|Government Debt (% of GDP)|ABS,FR|Government Debt (% of GDP)|ABS",
                "eu_production_indicator": "DE|Industrial Production|ABS,ES|Industrial Production|ABS,IT|Industrial Production|ABS,FR|Industrial Production|ABS",
                "eu_sales_indicator": "DE|Retail Sales|YOY,ES|Retail Sales|YOY,IT|Retail Sales|YOY,FR|Retail Sales|YOY",
                "eu_labour_indicator": "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS",
                "eu_housing_indicator": "DE|Home Prices|ABS,ES|Home Prices|ABS,IT|Home Prices|ABS,FR|Home Prices|ABS",
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_fr_region_with_fr_data(self):
        """
        GIVEN FR region with FR data created
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
            "region": str(EconomicDataLocationChoices.FR.label),
            "fr_growth_indicator": "GDP Growth",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "France",
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
                        "indicators": [{"type": "GDP Growth", "name": "GDP Growth"}],
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
                "region": "France",
                "period_window": "5Y",
                "us_growth_indicator": "GDP|YOY",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY",
                "eu_government_indicator": "DE|Government Debt (% of GDP)|ABS,ES|Government Debt (% of GDP)|ABS,IT|Government Debt (% of GDP)|ABS,FR|Government Debt (% of GDP)|ABS",
                "eu_production_indicator": "DE|Industrial Production|ABS,ES|Industrial Production|ABS,IT|Industrial Production|ABS,FR|Industrial Production|ABS",
                "eu_sales_indicator": "DE|Retail Sales|YOY,ES|Retail Sales|YOY,IT|Retail Sales|YOY,FR|Retail Sales|YOY",
                "eu_labour_indicator": "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS",
                "eu_housing_indicator": "DE|Home Prices|ABS,ES|Home Prices|ABS,IT|Home Prices|ABS,FR|Home Prices|ABS",
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP Growth",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_fr_defaults_and_period_window(self):
        """
        GIVEN France region with no indicator query params
        WHEN accessing economic charts view
        THEN FR Type|MODE defaults and period_window 5Y are applied
        """
        response = self.client.get(
            self.base_url, {"region": str(EconomicDataLocationChoices.FR.label)}
        )
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "France",
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
                        "indicators": [{"type": "GDP Growth", "name": "GDP Growth"}],
                    },
                    {"category": "Inflation", "indicators": []},
                    {"category": "Government", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Sales", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Confidence", "indicators": []},
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
                "region": "France",
                "period_window": "5Y",
                "us_growth_indicator": "GDP|YOY",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": (
                    "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,"
                    "IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY"
                ),
                "eu_government_indicator": (
                    "DE|Government Debt (% of GDP)|ABS,"
                    "ES|Government Debt (% of GDP)|ABS,"
                    "IT|Government Debt (% of GDP)|ABS,"
                    "FR|Government Debt (% of GDP)|ABS"
                ),
                "eu_production_indicator": (
                    "DE|Industrial Production|ABS,ES|Industrial Production|ABS,"
                    "IT|Industrial Production|ABS,FR|Industrial Production|ABS"
                ),
                "eu_sales_indicator": (
                    "DE|Retail Sales|YOY,ES|Retail Sales|YOY,"
                    "IT|Retail Sales|YOY,FR|Retail Sales|YOY"
                ),
                "eu_labour_indicator": (
                    "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,"
                    "IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS"
                ),
                "eu_housing_indicator": (
                    "DE|Home Prices|ABS,ES|Home Prices|ABS,"
                    "IT|Home Prices|ABS,FR|Home Prices|ABS"
                ),
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_us_defaults(self):
        """
        GIVEN United States region with no indicator query params
        WHEN accessing economic charts view
        THEN US Type|MODE defaults match the shared category stack
        """
        response = self.client.get(
            self.base_url, {"region": str(EconomicDataLocationChoices.US.label)}
        )
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "United States",
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
                        "indicators": [
                            {"type": "GDP Growth", "name": "GDP Growth"},
                            {"type": "GDP Growth (QoQ)", "name": "GDP Growth (QoQ)"},
                        ],
                    },
                    {
                        "category": "Inflation",
                        "indicators": [{"type": "CPI", "name": "CPI"}],
                    },
                    {"category": "Government", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Sales", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Confidence", "indicators": []},
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
                "region": "United States",
                "period_window": "5Y",
                "us_growth_indicator": "GDP|YOY",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": (
                    "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,"
                    "IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY"
                ),
                "eu_government_indicator": (
                    "DE|Government Debt (% of GDP)|ABS,"
                    "ES|Government Debt (% of GDP)|ABS,"
                    "IT|Government Debt (% of GDP)|ABS,"
                    "FR|Government Debt (% of GDP)|ABS"
                ),
                "eu_production_indicator": (
                    "DE|Industrial Production|ABS,ES|Industrial Production|ABS,"
                    "IT|Industrial Production|ABS,FR|Industrial Production|ABS"
                ),
                "eu_sales_indicator": (
                    "DE|Retail Sales|YOY,ES|Retail Sales|YOY,"
                    "IT|Retail Sales|YOY,FR|Retail Sales|YOY"
                ),
                "eu_labour_indicator": (
                    "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,"
                    "IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS"
                ),
                "eu_housing_indicator": (
                    "DE|Home Prices|ABS,ES|Home Prices|ABS,"
                    "IT|Home Prices|ABS,FR|Home Prices|ABS"
                ),
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_jp_defaults(self):
        """
        GIVEN Japan region with no indicator query params
        WHEN accessing economic charts view
        THEN JP Type|MODE defaults match the shared category stack
        """
        response = self.client.get(
            self.base_url, {"region": str(EconomicDataLocationChoices.JP.label)}
        )
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "Japan",
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
                    {"category": "Growth", "indicators": []},
                    {"category": "Inflation", "indicators": []},
                    {"category": "Government", "indicators": []},
                    {"category": "Production", "indicators": []},
                    {"category": "Sales", "indicators": []},
                    {"category": "Labour", "indicators": []},
                    {"category": "Housing", "indicators": []},
                    {"category": "Confidence", "indicators": []},
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
                "region": "Japan",
                "period_window": "5Y",
                "us_growth_indicator": "GDP|YOY",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": (
                    "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,"
                    "IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY"
                ),
                "eu_government_indicator": (
                    "DE|Government Debt (% of GDP)|ABS,"
                    "ES|Government Debt (% of GDP)|ABS,"
                    "IT|Government Debt (% of GDP)|ABS,"
                    "FR|Government Debt (% of GDP)|ABS"
                ),
                "eu_production_indicator": (
                    "DE|Industrial Production|ABS,ES|Industrial Production|ABS,"
                    "IT|Industrial Production|ABS,FR|Industrial Production|ABS"
                ),
                "eu_sales_indicator": (
                    "DE|Retail Sales|YOY,ES|Retail Sales|YOY,"
                    "IT|Retail Sales|YOY,FR|Retail Sales|YOY"
                ),
                "eu_labour_indicator": (
                    "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,"
                    "IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS"
                ),
                "eu_housing_indicator": (
                    "DE|Home Prices|ABS,ES|Home Prices|ABS,"
                    "IT|Home Prices|ABS,FR|Home Prices|ABS"
                ),
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }

    def test_economic_charts_view_eu_defaults(self):
        """
        GIVEN Europe region with no indicator query params
        WHEN accessing economic charts view
        THEN EU defaults are DE/ES/IT/FR Location|Type|MODE curves (no confidence)
        """
        response = self.client.get(
            self.base_url, {"region": str(EconomicDataLocationChoices.EU.label)}
        )
        assert response.status_code == 200
        response_context = _get_response_context(response)
        assert response_context == {
            "region": "Europe",
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
                        "indicators": [
                            {
                                "type": "FR|GDP Growth",
                                "name": "France — GDP Growth",
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
                "region": "Europe",
                "period_window": "5Y",
                "us_growth_indicator": "GDP|YOY",
                "us_inflation_indicator": "Consumer Price Index|YOY",
                "us_government_indicator": "Government Debt (% of GDP)|ABS",
                "us_production_indicator": "Industrial Production|ABS",
                "us_sales_indicator": "Retail Sales|YOY",
                "us_labour_indicator": "Unemployment Rate|ABS",
                "us_housing_indicator": "Home Prices|ABS",
                "us_confidence_indicator": "Consumer Confidence|ABS",
                "eu_growth_indicator": "DE|GDP|YOY,ES|GDP|YOY,IT|GDP|YOY,FR|GDP|YOY",
                "eu_inflation_indicator": (
                    "DE|Consumer Price Index|YOY,ES|Consumer Price Index|YOY,"
                    "IT|Consumer Price Index|YOY,FR|Consumer Price Index|YOY"
                ),
                "eu_government_indicator": (
                    "DE|Government Debt (% of GDP)|ABS,"
                    "ES|Government Debt (% of GDP)|ABS,"
                    "IT|Government Debt (% of GDP)|ABS,"
                    "FR|Government Debt (% of GDP)|ABS"
                ),
                "eu_production_indicator": (
                    "DE|Industrial Production|ABS,ES|Industrial Production|ABS,"
                    "IT|Industrial Production|ABS,FR|Industrial Production|ABS"
                ),
                "eu_sales_indicator": (
                    "DE|Retail Sales|YOY,ES|Retail Sales|YOY,"
                    "IT|Retail Sales|YOY,FR|Retail Sales|YOY"
                ),
                "eu_labour_indicator": (
                    "DE|Unemployment Rate|ABS,ES|Unemployment Rate|ABS,"
                    "IT|Unemployment Rate|ABS,FR|Unemployment Rate|ABS"
                ),
                "eu_housing_indicator": (
                    "DE|Home Prices|ABS,ES|Home Prices|ABS,"
                    "IT|Home Prices|ABS,FR|Home Prices|ABS"
                ),
                "eu_confidence_indicator": "",
                "fr_growth_indicator": "GDP|YOY",
                "fr_inflation_indicator": "Consumer Price Index|YOY",
                "fr_government_indicator": "Government Debt (% of GDP)|ABS",
                "fr_production_indicator": "Industrial Production|ABS",
                "fr_sales_indicator": "Retail Sales|YOY",
                "fr_labour_indicator": "Unemployment Rate|ABS",
                "fr_housing_indicator": "Home Prices|ABS",
                "fr_confidence_indicator": "Aggregate Business Confidence|ABS",
                "jp_growth_indicator": "GDP|YOY",
                "jp_inflation_indicator": "Consumer Price Index|YOY",
                "jp_government_indicator": "Government Debt (% of GDP)|ABS",
                "jp_production_indicator": "Industrial Production|ABS",
                "jp_sales_indicator": "Retail Sales|YOY",
                "jp_labour_indicator": "Unemployment Rate|ABS",
                "jp_housing_indicator": "Home Prices|ABS",
                "jp_confidence_indicator": "Manufacturing Business Confidence|ABS",
            },
        }
