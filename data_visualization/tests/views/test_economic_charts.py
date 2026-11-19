"""Tests for economic chart views."""

import json
from collections.abc import Mapping
from datetime import date
from typing import Protocol, TypedDict

from django.test import Client, TestCase
from django.test.utils import ContextList
from freezegun import freeze_time

from data_visualization.services.economic_charts.indicator_selection import (
    EconomicChartsDropdownValues,
)
from data_visualization.services.economic_charts.line_charts import EconomicChartsData
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)

_CHART_SLOTS: list[tuple[str, str]] = [
    ("Macroeconomics", "Growth"),
    ("Macroeconomics", "Trade"),
    ("Macroeconomics", "Confidence"),
    ("Household", "Labour"),
    ("Household", "Inequality"),
    ("Household", "Income"),
    ("Household", "Saving"),
    ("Household", "Debt"),
    ("Household", "Sales"),
    ("Household", "Prices"),
    ("Household", "Housing"),
    ("Household", "Confidence"),
    ("Business", "Income"),
    ("Business", "Investment"),
    ("Business", "Cost"),
    ("Business", "Debt"),
    ("Business", "Prices"),
    ("Business", "Production"),
    ("Business", "Confidence"),
    ("Government", "Budget"),
    ("Government", "Financing"),
    ("Government", "Debt"),
]

_SELECTION_SUFFIXES: list[str] = [
    "macroeconomics_growth_indicator",
    "macroeconomics_trade_indicator",
    "macroeconomics_confidence_indicator",
    "household_labour_indicator",
    "household_inequality_indicator",
    "household_income_indicator",
    "household_saving_indicator",
    "household_debt_indicator",
    "household_sales_indicator",
    "household_prices_indicator",
    "household_housing_indicator",
    "household_confidence_indicator",
    "business_income_indicator",
    "business_investment_indicator",
    "business_cost_indicator",
    "business_debt_indicator",
    "business_prices_indicator",
    "business_production_indicator",
    "business_confidence_indicator",
    "government_budget_indicator",
    "government_financing_indicator",
    "government_debt_indicator",
]


def _empty_charts_payload() -> list[EconomicChartsData]:
    """Build empty chart payloads for every category/subcategory slot."""
    return [
        EconomicChartsData(
            category=category,
            subcategory=subcategory,
            category_data=[],
            value_axis_label="Data Value",
        )
        for category, subcategory in _CHART_SLOTS
    ]


def _charts_payload_with_slot(
    category: str,
    subcategory: str,
    category_data: list,
    value_axis_label: str = "Data Value",
) -> list[EconomicChartsData]:
    """Fill one chart slot and leave the others empty."""
    payload = _empty_charts_payload()
    for index, (slot_category, slot_subcategory) in enumerate(_CHART_SLOTS):
        if (slot_category, slot_subcategory) == (category, subcategory):
            payload[index] = EconomicChartsData(
                category=category,
                subcategory=subcategory,
                category_data=category_data,
                value_axis_label=value_axis_label,
            )
    return payload


def _empty_selected_values(
    *,
    region: str = "US",
    period_window: str = "10Y",
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build default empty selection map for every region/slot, then apply overrides."""
    selected_values: dict[str, str] = {
        "region": region,
        "period_window": period_window,
        "countries": "US,FR,JP,DE,ES,IT",
    }
    for region_code in ("us", "cross", "fr", "jp"):
        for suffix in _SELECTION_SUFFIXES:
            selected_values[f"{region_code}_{suffix}"] = ""
    if overrides:
        selected_values.update(overrides)
    return selected_values


def _us_dropdown_values() -> EconomicChartsDropdownValues:
    """Dropdown payload for the US region fixtures in these tests."""
    return EconomicChartsDropdownValues(
        categories=["Macroeconomics", "Household", "Business", "Government"],
        locations=["United States", "France", "Japan", "Cross-Region"],
        indicators_by_category_subcategory=[
            {
                "category": "Macroeconomics",
                "subcategory": "Growth",
                "indicators": [
                    {
                        "series_label": "GDP Growth",
                        "name": "GDP Growth",
                        "default_mode": "Raw",
                        "measure_type": "FLOW",
                        "expansion_relation": "",
                        "supports_vs_gdp": False,
                        "description": "",
                        "comparability_warning": "",
                    },
                    {
                        "series_label": "GDP Growth (QoQ)",
                        "name": "GDP Growth (QoQ)",
                        "default_mode": "Raw",
                        "measure_type": "FLOW",
                        "expansion_relation": "",
                        "supports_vs_gdp": False,
                        "description": "",
                        "comparability_warning": "",
                    },
                ],
            },
            {"category": "Macroeconomics", "subcategory": "Trade", "indicators": []},
            {
                "category": "Macroeconomics",
                "subcategory": "Confidence",
                "indicators": [],
            },
            {"category": "Household", "subcategory": "Labour", "indicators": []},
            {"category": "Household", "subcategory": "Inequality", "indicators": []},
            {"category": "Household", "subcategory": "Income", "indicators": []},
            {"category": "Household", "subcategory": "Saving", "indicators": []},
            {"category": "Household", "subcategory": "Debt", "indicators": []},
            {"category": "Household", "subcategory": "Sales", "indicators": []},
            {
                "category": "Household",
                "subcategory": "Prices",
                "indicators": [
                    {
                        "series_label": "CPI",
                        "name": "CPI",
                        "default_mode": "Raw",
                        "measure_type": "FLOW",
                        "expansion_relation": "",
                        "supports_vs_gdp": False,
                        "description": "",
                        "comparability_warning": "",
                    },
                ],
            },
            {"category": "Household", "subcategory": "Housing", "indicators": []},
            {"category": "Household", "subcategory": "Confidence", "indicators": []},
            {"category": "Business", "subcategory": "Income", "indicators": []},
            {"category": "Business", "subcategory": "Investment", "indicators": []},
            {"category": "Business", "subcategory": "Cost", "indicators": []},
            {"category": "Business", "subcategory": "Debt", "indicators": []},
            {"category": "Business", "subcategory": "Prices", "indicators": []},
            {"category": "Business", "subcategory": "Production", "indicators": []},
            {"category": "Business", "subcategory": "Confidence", "indicators": []},
            {"category": "Government", "subcategory": "Budget", "indicators": []},
            {"category": "Government", "subcategory": "Financing", "indicators": []},
            {"category": "Government", "subcategory": "Debt", "indicators": []},
        ],
    )


def _fr_dropdown_values() -> EconomicChartsDropdownValues:
    """Dropdown payload for the France region fixtures in these tests."""
    return EconomicChartsDropdownValues(
        categories=["Macroeconomics", "Household", "Business", "Government"],
        locations=["United States", "France", "Japan", "Cross-Region"],
        indicators_by_category_subcategory=[
            {
                "category": "Macroeconomics",
                "subcategory": "Growth",
                "indicators": [
                    {
                        "series_label": "GDP Growth",
                        "name": "GDP Growth",
                        "default_mode": "Raw",
                        "measure_type": "FLOW",
                        "expansion_relation": "",
                        "supports_vs_gdp": False,
                        "description": "",
                        "comparability_warning": "",
                    },
                ],
            },
            {"category": "Macroeconomics", "subcategory": "Trade", "indicators": []},
            {
                "category": "Macroeconomics",
                "subcategory": "Confidence",
                "indicators": [],
            },
            {"category": "Household", "subcategory": "Labour", "indicators": []},
            {"category": "Household", "subcategory": "Inequality", "indicators": []},
            {"category": "Household", "subcategory": "Income", "indicators": []},
            {"category": "Household", "subcategory": "Saving", "indicators": []},
            {"category": "Household", "subcategory": "Debt", "indicators": []},
            {"category": "Household", "subcategory": "Sales", "indicators": []},
            {"category": "Household", "subcategory": "Prices", "indicators": []},
            {"category": "Household", "subcategory": "Housing", "indicators": []},
            {"category": "Household", "subcategory": "Confidence", "indicators": []},
            {"category": "Business", "subcategory": "Income", "indicators": []},
            {"category": "Business", "subcategory": "Investment", "indicators": []},
            {"category": "Business", "subcategory": "Cost", "indicators": []},
            {"category": "Business", "subcategory": "Debt", "indicators": []},
            {"category": "Business", "subcategory": "Prices", "indicators": []},
            {"category": "Business", "subcategory": "Production", "indicators": []},
            {"category": "Business", "subcategory": "Confidence", "indicators": []},
            {"category": "Government", "subcategory": "Budget", "indicators": []},
            {"category": "Government", "subcategory": "Financing", "indicators": []},
            {"category": "Government", "subcategory": "Debt", "indicators": []},
        ],
    )


def _cross_dropdown_values() -> EconomicChartsDropdownValues:
    """Cross-Region dropdown: like-to-like only; fixtures lack full coverage."""
    return EconomicChartsDropdownValues(
        categories=["Macroeconomics", "Household", "Business", "Government"],
        locations=["United States", "France", "Japan", "Cross-Region"],
        indicators_by_category_subcategory=[
            {
                "category": category,
                "subcategory": subcategory,
                "indicators": [],
            }
            for category, subcategory in _CHART_SLOTS
        ],
    )


class EconomicChartsResponseContext(TypedDict):
    """Parsed template context fields accessed by economic charts view tests."""

    region: str
    period_window: str
    dropdown_values: EconomicChartsDropdownValues
    economic_data: list[EconomicChartsData]
    composition_panels: list
    industry_profitability_panels: list
    trade_ranking_panels: list
    categories: list[str]
    selected_values: dict[str, str]


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
    # Usage of dict: Django template context values before JSON parsing.
    context: Mapping[str, object] = dict(response.context or {})
    dropdown_values: EconomicChartsDropdownValues = json.loads(
        _context_as_str(context, "dropdown_values", "{}")
    )
    economic_data: list[EconomicChartsData] = json.loads(
        _context_as_str(context, "economic_data", "[]")
    )
    composition_panels: list = json.loads(
        _context_as_str(context, "composition_panels", "[]")
    )
    industry_profitability_panels: list = json.loads(
        _context_as_str(context, "industry_profitability_panels", "[]")
    )
    trade_ranking_panels: list = json.loads(
        _context_as_str(context, "trade_ranking_panels", "[]")
    )
    categories: list[str] = json.loads(_context_as_str(context, "categories", "[]"))
    selected_values: dict[str, str] = json.loads(
        _context_as_str(context, "selected_values", "{}")
    )
    return EconomicChartsResponseContext(
        region=_context_as_str(context, "region", ""),
        period_window=_context_as_str(context, "period_window", ""),
        dropdown_values=dropdown_values,
        economic_data=economic_data,
        composition_panels=composition_panels,
        industry_profitability_panels=industry_profitability_panels,
        trade_ranking_panels=trade_ranking_panels,
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

        self.indicator_us_growth = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP Growth",
            full_name="US GDP Growth",
            technical_name="us_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_us_quarterly_growth = (
            EconomicIndicatorInformationModel.objects.create(
                id=2,
                location=EconomicDataLocationChoices.US,
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
                series_label="GDP Growth (QoQ)",
                full_name="US GDP Growth (QoQ)",
                technical_name="us_gdp_growth_qoq",
                frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
                source=EconomicDataSourceChoices.INSEE,
                ticker="001565531",
            )
        )
        self.indicator_us_inflation = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.PRICES,
            series_label="CPI",
            full_name="US CPI",
            technical_name="us_cpi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565532",
        )
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=4,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP Growth",
            full_name="FR GDP Growth",
            technical_name="fr_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565533",
        )

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
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=date(2024, 4, 1),
            data_value=1.2,
        )

    def test_economic_charts_view_no_parameters(self):
        """
        GIVEN no parameters
        WHEN accessing economic charts view
        THEN default values are used with correct structure
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "United States",
            "period_window": "10Y",
            "dropdown_values": _us_dropdown_values(),
            "economic_data": _empty_charts_payload(),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(),
        }

    def test_economic_charts_view_with_selected_indicator(self):
        """
        GIVEN selected indicator in query parameters
        WHEN accessing economic charts view
        THEN selected indicator is in selected values and data is filtered
        """
        params = {
            "region": EconomicDataLocationChoices.US.value,
            "us_macroeconomics_growth_indicator": "GDP Growth",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "United States",
            "period_window": "10Y",
            "dropdown_values": _us_dropdown_values(),
            "economic_data": _charts_payload_with_slot(
                "Macroeconomics",
                "Growth",
                [
                    {
                        "period": "2024",
                        "data_value": 2.5,
                        "indicator_name": "GDP Growth",
                        "unit_label": "",
                    }
                ],
            ),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(
                overrides={"us_macroeconomics_growth_indicator": "GDP Growth"}
            ),
        }

    def test_economic_charts_view_with_multiple_selected_indicators(self):
        """
        GIVEN multiple selected growth indicators
        WHEN accessing economic charts view
        THEN both series appear in the growth chart payload
        """
        params = {
            "region": EconomicDataLocationChoices.US.value,
            "us_macroeconomics_growth_indicator": "GDP Growth,GDP Growth (QoQ)",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "United States",
            "period_window": "10Y",
            "dropdown_values": _us_dropdown_values(),
            "economic_data": _charts_payload_with_slot(
                "Macroeconomics",
                "Growth",
                [
                    {
                        "period": "2024Q1",
                        "data_value": 0.5,
                        "indicator_name": "GDP Growth (QoQ)",
                        "unit_label": "",
                    },
                    {
                        "period": "2024",
                        "data_value": 2.5,
                        "indicator_name": "GDP Growth",
                        "unit_label": "",
                    },
                ],
            ),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(
                overrides={
                    "us_macroeconomics_growth_indicator": "GDP Growth,GDP Growth (QoQ)"
                }
            ),
        }

    def test_economic_charts_view_fr_region_with_fr_data(self):
        """
        GIVEN France region and a selected FR growth indicator
        WHEN accessing economic charts view
        THEN France dropdown/data are returned
        """
        params = {
            "region": EconomicDataLocationChoices.FR.value,
            "fr_macroeconomics_growth_indicator": "GDP Growth",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "France",
            "period_window": "10Y",
            "dropdown_values": _fr_dropdown_values(),
            "economic_data": _charts_payload_with_slot(
                "Macroeconomics",
                "Growth",
                [
                    {
                        "period": "2024Q2",
                        "data_value": 1.2,
                        "indicator_name": "GDP Growth",
                        "unit_label": "",
                    }
                ],
            ),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(
                region="FR",
                overrides={"fr_macroeconomics_growth_indicator": "GDP Growth"},
            ),
        }

    def test_economic_charts_view_fr_defaults_and_period_window(self):
        """
        GIVEN France region and a custom period window
        WHEN accessing economic charts view with no indicator selection
        THEN empty chart slots are returned for the requested window
        """
        params = {
            "region": EconomicDataLocationChoices.FR.value,
            "period_window": "1Y",
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "France",
            "period_window": "1Y",
            "dropdown_values": _fr_dropdown_values(),
            "economic_data": _empty_charts_payload(),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(region="FR", period_window="1Y"),
        }

    def test_economic_charts_view_us_defaults(self):
        """
        GIVEN United States region with no indicator overrides
        WHEN accessing economic charts view
        THEN US dropdown/empty charts are returned
        """
        params = {"region": EconomicDataLocationChoices.US.value}
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "United States",
            "period_window": "10Y",
            "dropdown_values": _us_dropdown_values(),
            "economic_data": _empty_charts_payload(),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(),
        }

    def test_economic_charts_view_jp_defaults(self):
        """
        GIVEN Japan region with no Japan-specific indicators seeded
        WHEN accessing economic charts view
        THEN empty dropdown slots and chart payloads are returned
        """
        params = {"region": EconomicDataLocationChoices.JP.value}
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "Japan",
            "period_window": "10Y",
            "dropdown_values": EconomicChartsDropdownValues(
                categories=["Macroeconomics", "Household", "Business", "Government"],
                locations=["United States", "France", "Japan", "Cross-Region"],
                indicators_by_category_subcategory=[
                    {
                        "category": category,
                        "subcategory": subcategory,
                        "indicators": [],
                    }
                    for category, subcategory in _CHART_SLOTS
                ],
            ),
            "economic_data": _empty_charts_payload(),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(region="JP"),
        }

    def test_economic_charts_view_japan_display_label_region_param(self):
        """
        GIVEN region query param set to the Japan display label
        WHEN accessing economic charts view
        THEN Japan charts load and selected_values keep the JP wire code
        """
        params = {"region": "Japan"}
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "Japan",
            "period_window": "10Y",
            "dropdown_values": EconomicChartsDropdownValues(
                categories=["Macroeconomics", "Household", "Business", "Government"],
                locations=["United States", "France", "Japan", "Cross-Region"],
                indicators_by_category_subcategory=[
                    {
                        "category": category,
                        "subcategory": subcategory,
                        "indicators": [],
                    }
                    for category, subcategory in _CHART_SLOTS
                ],
            ),
            "economic_data": _empty_charts_payload(),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(region="JP"),
        }

    def test_economic_charts_view_cross_defaults(self):
        """
        GIVEN Cross-Region region
        WHEN accessing economic charts view
        THEN EU country curves appear in the growth dropdown
        """
        params = {"region": "Cross-Region"}
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert _get_response_context(response) == {
            "region": "Cross-Region",
            "period_window": "10Y",
            "dropdown_values": _cross_dropdown_values(),
            "economic_data": _empty_charts_payload(),
            "composition_panels": [],
            "industry_profitability_panels": [],
            "trade_ranking_panels": [],
            "categories": ["Macroeconomics", "Household", "Business", "Government"],
            "selected_values": _empty_selected_values(region="Cross-Region"),
        }
