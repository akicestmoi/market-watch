"""Tests for economic chart visualization services."""

from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.services.time_series_calculation import TimeSeriesPoint
from data_visualization.services.config import ChartPeriodWindow
from data_visualization.services.economic_charts.indicator_breakdown import (
    get_composition_chart_panels,
)
from data_visualization.services.economic_charts.indicator_selection import (
    EconomicChartsDropdownValues,
    SelectedIndicatorsByCategorySubcategory,
    get_default_indicator_selections,
    get_economic_charts_dropdown_values,
    get_selected_indicators_by_category_subcategory,
)
from data_visualization.services.economic_charts.line_charts import (
    EconomicChartsData,
    GdpSeriesMeta,
    _format_value_axis_label,
    _GdpSeriesForLocation,
    _get_required_gdp_base_unit,
    _parse_selected_indicator_and_mode,
    aggregate_monthly_points_to_quarterly_mean,
    align_cross_region_time_series,
    filter_time_series_by_period_window,
    format_period,
    get_economic_charts_data,
    interpolate_points_to_monthly,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
    IndicatorExpansionRelationChoices,
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


def _empty_charts_payload() -> list[EconomicChartsData]:
    """Build the empty category/subcategory charts payload."""
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
    """Build charts payload with one filled category/subcategory slot."""
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


class TestEconomicChartServices(TestCase):
    """Test cases for economic chart services."""

    def setUp(self):
        """Set up test fixtures."""
        self.location = EconomicDataLocationChoices.US

        self.indicator_growth = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP Growth",
            full_name="US GDP Growth",
            technical_name="us_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_inflation = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.PRICES,
            series_label="CPI",
            full_name="US CPI",
            technical_name="us_cpi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP Growth",
            full_name="FR GDP Growth",
            technical_name="fr_gdp_growth",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565532",
        )

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

    def testformat_period_monthly(self):
        """
        GIVEN a date
        WHEN format_period is called
        THEN period is correctly formatted as YYYY-MM
        """
        test_date = date(2024, 1, 15)
        assert (
            format_period(test_date, EconomicPublicationFrequencyChoices.MONTHLY)
            == "2024-01"
        )
        assert (
            format_period(test_date, EconomicPublicationFrequencyChoices.QUARTERLY)
            == "2024Q1"
        )
        assert (
            format_period(test_date, EconomicPublicationFrequencyChoices.ANNUAL)
            == "2024"
        )

        q3_date = date(2024, 7, 1)
        assert (
            format_period(q3_date, EconomicPublicationFrequencyChoices.QUARTERLY)
            == "2024Q3"
        )

    def test_get_selected_indicators_us_region(self):
        """
        GIVEN front data with US region indicators
        WHEN get_selected_indicators_by_category_subcategory is called
        THEN correct indicators are extracted for each category/subcategory
        """
        front_data = {
            "region": "United States",
            "period_window": ChartPeriodWindow.FIVE_YEARS.value,
            "us_macroeconomics_growth_indicator": "GDP Growth,Real GDP",
            "us_household_prices_indicator": "CPI",
        }

        result = get_selected_indicators_by_category_subcategory("us", front_data)
        assert result == [
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
                selected_indicators=["GDP Growth", "Real GDP"],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.TRADE,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.LABOUR,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.INEQUALITY,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.INCOME,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.SAVING,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.DEBT,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.SALES,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.PRICES,
                selected_indicators=["CPI"],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.HOUSING,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.INCOME,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.INVESTMENT,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.COST,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.DEBT,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.PRICES,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.PRODUCTION,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.GOVERNMENT,
                subcategory=EconomicDataSubcategoryChoices.BUDGET,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.GOVERNMENT,
                subcategory=EconomicDataSubcategoryChoices.FINANCING,
                selected_indicators=[],
            ),
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.GOVERNMENT,
                subcategory=EconomicDataSubcategoryChoices.DEBT,
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
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Real GDP",
            full_name="US Real GDP",
            technical_name="us_real_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GDPC1",
            default_mode=IndicatorDisplayModeChoices.ANNUAL,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=102,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.PRICES,
            series_label="Consumer Price Index",
            full_name="US CPI",
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
            subcategory=EconomicDataSubcategoryChoices.DEBT,
            series_label="Government Debt",
            full_name="US Debt",
            technical_name="us_debt",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GFDEBTN",
            default_mode=IndicatorDisplayModeChoices.RAW,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=104,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.INCOME,
            series_label="Nominal Disposable Household Income",
            full_name="US Nominal Disposable Household Income",
            technical_name="us_nom_disp_hh",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="DSPI",
            default_mode=IndicatorDisplayModeChoices.ANNUAL,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=105,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.INCOME,
            series_label="Real Disposable Household Income",
            full_name="US Real Disposable Household Income",
            technical_name="us_real_disp_hh",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="DSPIC96",
            default_mode=IndicatorDisplayModeChoices.ANNUAL,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=106,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.SAVING,
            series_label="Household Saving Ratio",
            full_name="US Household Saving Ratio",
            technical_name="us_hh_saving_ratio",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="PSAVERT",
            default_mode=IndicatorDisplayModeChoices.RAW,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=107,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.DEBT,
            series_label="Household Debt Ratio",
            full_name="US Household Debt Ratio",
            technical_name="us_hh_debt_ratio",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="TDSP",
            default_mode=IndicatorDisplayModeChoices.RAW,
        )
        result = get_default_indicator_selections(EconomicDataLocationChoices.US)
        assert result == {
            "macroeconomics_growth_indicator": "Real GDP|YoY",
            "macroeconomics_trade_indicator": "",
            "macroeconomics_confidence_indicator": "",
            "household_labour_indicator": "",
            "household_inequality_indicator": "",
            "household_income_indicator": (
                "Nominal Disposable Household Income|YoY,"
                "Real Disposable Household Income|YoY"
            ),
            "household_saving_indicator": "Household Saving Ratio|Raw",
            "household_debt_indicator": "Household Debt Ratio|Raw",
            "household_sales_indicator": "",
            "household_prices_indicator": "Consumer Price Index|YoY",
            "household_housing_indicator": "",
            "household_confidence_indicator": "",
            "business_income_indicator": "",
            "business_investment_indicator": "",
            "business_cost_indicator": "",
            "business_debt_indicator": "",
            "business_prices_indicator": "",
            "business_production_indicator": "",
            "business_confidence_indicator": "",
            "government_budget_indicator": "",
            "government_financing_indicator": "",
            "government_debt_indicator": "Government Debt|Raw",
        }

    def test_get_default_indicator_selections_us_sales_includes_real_retail(self):
        """
        GIVEN US Retail Sales and Real Retail Sales catalog entries
        WHEN building default chart selections for US
        THEN Sales defaults to both series with their DB default modes
        """
        EconomicIndicatorInformationModel.objects.create(
            id=301,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.SALES,
            series_label="Retail Sales",
            full_name="United States Retail Sales",
            technical_name="us_retail_sales",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="RSAFS",
            default_mode=IndicatorDisplayModeChoices.YTD_YOY,
        )
        EconomicIndicatorInformationModel.objects.create(
            id=302,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.SALES,
            series_label="Real Retail Sales",
            full_name="United States Real Retail Sales",
            technical_name="us_real_retail_sales",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="RRSFS",
            default_mode=IndicatorDisplayModeChoices.YTD_YOY,
        )

        result = get_default_indicator_selections(EconomicDataLocationChoices.US)
        assert result["household_sales_indicator"] == (
            "Retail Sales|YTDYoY,Real Retail Sales|YTDYoY"
        )

    def test_composition_child_indicators_leave_slot_dropdown_and_build_panel(self):
        """
        GIVEN Annual Government Expenditures parent and COMPONENT children
        WHEN building dropdown values and composition panels for US
        THEN children are omitted from Budget and the breakdown panel uses top shares
        """
        parent = EconomicIndicatorInformationModel.objects.create(
            id=201,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Annual Government Expenditures",
            full_name="US Annual Government Expenditures",
            technical_name="us_annual_gov_exp",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.BEA,
            ticker="bea_t31600_total",
            base_unit=IndicatorBaseUnitChoices.B,
        )
        child_a = EconomicIndicatorInformationModel.objects.create(
            id=202,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Health",
            full_name="US Health Expenditures",
            technical_name="us_health_exp",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.BEA,
            ticker="bea_t31600_health",
            base_unit=IndicatorBaseUnitChoices.B,
            parent_series_label="Annual Government Expenditures",
            expansion_relation=IndicatorExpansionRelationChoices.COMPONENT,
        )
        child_b = EconomicIndicatorInformationModel.objects.create(
            id=203,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Education",
            full_name="US Education Expenditures",
            technical_name="us_education_exp",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.BEA,
            ticker="bea_t31600_education",
            base_unit=IndicatorBaseUnitChoices.B,
            parent_series_label="Annual Government Expenditures",
            expansion_relation=IndicatorExpansionRelationChoices.COMPONENT,
        )
        child_c = EconomicIndicatorInformationModel.objects.create(
            id=204,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Income Security",
            full_name="US Income Security Expenditures",
            technical_name="us_income_security_exp",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.BEA,
            ticker="bea_t31600_income_security",
            base_unit=IndicatorBaseUnitChoices.B,
            parent_series_label="Annual Government Expenditures",
            expansion_relation=IndicatorExpansionRelationChoices.COMPONENT,
        )
        period = date(2024, 1, 1)
        EconomicDataModel.objects.create(
            indicator=parent, period=period, data_value=100.0
        )
        EconomicDataModel.objects.create(
            indicator=child_a, period=period, data_value=40.0
        )
        EconomicDataModel.objects.create(
            indicator=child_b, period=period, data_value=35.0
        )
        EconomicDataModel.objects.create(
            indicator=child_c, period=period, data_value=25.0
        )

        dropdown = get_economic_charts_dropdown_values(
            cross_region=False, location=EconomicDataLocationChoices.US
        )
        government_budget = next(
            slot
            for slot in dropdown["indicators_by_category_subcategory"]
            if slot["category"] == "Government" and slot["subcategory"] == "Budget"
        )
        assert government_budget["indicators"] == [
            {
                "series_label": "Annual Government Expenditures",
                "name": "Annual Government Expenditures",
                "default_mode": "Raw",
                "measure_type": "FLOW",
                "expansion_relation": "",
                "supports_vs_gdp": True,
                "description": "",
                "comparability_warning": "",
            }
        ]

        panels = get_composition_chart_panels(
            EconomicDataLocationChoices.US,
            ChartPeriodWindow.FIVE_YEARS,
            cross_region=False,
        )
        assert panels == [
            {
                "category": "Government",
                "panel_id": "budget",
                "title": "Budget Expenditure Breakdown",
                "trend_title": "Trend",
                "pie_title": "Share",
                "available_locations": [
                    {"code": "US", "label": "United States"},
                ],
                "default_location": "US",
                "by_location": {
                    "US": {
                        "line_data_by_mode": {
                            "Share": [
                                {
                                    "period": "2024",
                                    "data_value": 25.0,
                                    "indicator_name": "Income Security",
                                    "unit_label": "%",
                                },
                                {
                                    "period": "2024",
                                    "data_value": 40.0,
                                    "indicator_name": "Health",
                                    "unit_label": "%",
                                },
                                {
                                    "period": "2024",
                                    "data_value": 35.0,
                                    "indicator_name": "Education",
                                    "unit_label": "%",
                                },
                            ],
                            "Raw": [
                                {
                                    "period": "2024",
                                    "data_value": 25.0,
                                    "indicator_name": "Income Security",
                                    "unit_label": "",
                                },
                                {
                                    "period": "2024",
                                    "data_value": 40.0,
                                    "indicator_name": "Health",
                                    "unit_label": "",
                                },
                                {
                                    "period": "2024",
                                    "data_value": 35.0,
                                    "indicator_name": "Education",
                                    "unit_label": "",
                                },
                            ],
                            "YoY": [],
                        },
                        "value_axis_label_by_mode": {
                            "Share": "Share of Annual Government Expenditures (%)",
                            "Raw": "Level",
                            "YoY": "YoY (%)",
                        },
                        "multiselect_indicators": [
                            {
                                "series_label": "Education",
                                "name": "Education",
                                "description": "",
                                "include_in_pie": True,
                            },
                            {
                                "series_label": "Health",
                                "name": "Health",
                                "description": "",
                                "include_in_pie": True,
                            },
                            {
                                "series_label": "Income Security",
                                "name": "Income Security",
                                "description": "",
                                "include_in_pie": True,
                            },
                        ],
                        "default_selected_series_labels": [
                            "Health",
                            "Education",
                            "Income Security",
                        ],
                        "pie_by_period_by_granularity": {
                            "year": {
                                "2024": [
                                    {"name": "Health", "share": 40.0},
                                    {"name": "Education", "share": 35.0},
                                    {"name": "Income Security", "share": 25.0},
                                ]
                            }
                        },
                        "periods_by_granularity": {"year": ["2024"]},
                        "available_pie_granularities": ["year"],
                        "default_pie_granularity": "year",
                        "available_breakdown_modes": ["Share", "Raw", "YoY"],
                        "default_breakdown_mode": "Share",
                        "mode_in_trend_panel": False,
                    }
                },
            }
        ]

    def test_gdp_composition_excludes_exports_from_share_mode_lines(self):
        """
        GIVEN Real GDP, a COMPONENT child, and Exports trend-only data
        WHEN building GDP composition panels
        THEN Share lines and pies omit Exports while the multiselect still lists it
        """
        parent = EconomicIndicatorInformationModel.objects.create(
            id=301,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Real GDP",
            full_name="US Real GDP",
            technical_name="us_real_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.BEA,
            ticker="GDPC1",
            base_unit=IndicatorBaseUnitChoices.B,
        )
        consumption = EconomicIndicatorInformationModel.objects.create(
            id=302,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Personal Consumption",
            full_name="US Personal Consumption",
            technical_name="us_pce",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.BEA,
            ticker="PCEC",
            base_unit=IndicatorBaseUnitChoices.B,
            parent_series_label="Real GDP",
            expansion_relation=IndicatorExpansionRelationChoices.COMPONENT,
        )
        exports = EconomicIndicatorInformationModel.objects.create(
            id=303,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Exports",
            full_name="US Exports",
            technical_name="us_exports",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.BEA,
            ticker="EXPGS",
            base_unit=IndicatorBaseUnitChoices.B,
        )
        period = date(2024, 1, 1)
        EconomicDataModel.objects.create(
            indicator=parent, period=period, data_value=100.0
        )
        EconomicDataModel.objects.create(
            indicator=consumption, period=period, data_value=60.0
        )
        EconomicDataModel.objects.create(
            indicator=exports, period=period, data_value=20.0
        )

        panels = get_composition_chart_panels(
            EconomicDataLocationChoices.US,
            ChartPeriodWindow.FIVE_YEARS,
            cross_region=False,
        )
        gdp_panel = next(panel for panel in panels if panel["panel_id"] == "gdp")
        us_data = gdp_panel["by_location"]["US"]
        share_indicator_names = {
            point["indicator_name"] for point in us_data["line_data_by_mode"]["Share"]
        }
        raw_indicator_names = {
            point["indicator_name"] for point in us_data["line_data_by_mode"]["Raw"]
        }
        assert share_indicator_names == {"Personal Consumption"}
        assert raw_indicator_names == {"Personal Consumption", "Exports"}
        assert us_data["multiselect_indicators"] == [
            {
                "series_label": "Exports",
                "name": "Exports",
                "description": "",
                "include_in_pie": False,
            },
            {
                "series_label": "Personal Consumption",
                "name": "Personal Consumption",
                "description": "",
                "include_in_pie": True,
            },
        ]
        assert us_data["pie_by_period_by_granularity"]["quarter"] == {
            "2024Q1": [{"name": "Personal Consumption", "share": 60.0}]
        }

    def test_get_dropdown_values_returns_correct_structure(self):
        """
        GIVEN existing indicators
        WHEN getting economic charts dropdown values
        THEN the correct structure is returned
        """
        result = get_economic_charts_dropdown_values(
            cross_region=False, location=self.location
        )
        assert result == EconomicChartsDropdownValues(
            categories=[
                "Macroeconomics",
                "Household",
                "Business",
                "Government",
            ],
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
                {
                    "category": "Macroeconomics",
                    "subcategory": "Trade",
                    "indicators": [],
                },
                {
                    "category": "Macroeconomics",
                    "subcategory": "Confidence",
                    "indicators": [],
                },
                {"category": "Household", "subcategory": "Labour", "indicators": []},
                {
                    "category": "Household",
                    "subcategory": "Inequality",
                    "indicators": [],
                },
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
                {
                    "category": "Household",
                    "subcategory": "Confidence",
                    "indicators": [],
                },
                {"category": "Business", "subcategory": "Income", "indicators": []},
                {"category": "Business", "subcategory": "Investment", "indicators": []},
                {"category": "Business", "subcategory": "Cost", "indicators": []},
                {"category": "Business", "subcategory": "Debt", "indicators": []},
                {"category": "Business", "subcategory": "Prices", "indicators": []},
                {"category": "Business", "subcategory": "Production", "indicators": []},
                {"category": "Business", "subcategory": "Confidence", "indicators": []},
                {"category": "Government", "subcategory": "Budget", "indicators": []},
                {
                    "category": "Government",
                    "subcategory": "Financing",
                    "indicators": [],
                },
                {"category": "Government", "subcategory": "Debt", "indicators": []},
            ],
        )

    def test_get_dropdown_values_different_location(self):
        """
        GIVEN indicators for different locations
        WHEN getting dropdown values for FR
        THEN only FR indicators are returned
        """
        result = get_economic_charts_dropdown_values(
            cross_region=False, location=EconomicDataLocationChoices.FR
        )
        assert result == EconomicChartsDropdownValues(
            categories=[
                "Macroeconomics",
                "Household",
                "Business",
                "Government",
            ],
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
                {
                    "category": "Macroeconomics",
                    "subcategory": "Trade",
                    "indicators": [],
                },
                {
                    "category": "Macroeconomics",
                    "subcategory": "Confidence",
                    "indicators": [],
                },
                {"category": "Household", "subcategory": "Labour", "indicators": []},
                {
                    "category": "Household",
                    "subcategory": "Inequality",
                    "indicators": [],
                },
                {"category": "Household", "subcategory": "Income", "indicators": []},
                {"category": "Household", "subcategory": "Saving", "indicators": []},
                {"category": "Household", "subcategory": "Debt", "indicators": []},
                {"category": "Household", "subcategory": "Sales", "indicators": []},
                {"category": "Household", "subcategory": "Prices", "indicators": []},
                {"category": "Household", "subcategory": "Housing", "indicators": []},
                {
                    "category": "Household",
                    "subcategory": "Confidence",
                    "indicators": [],
                },
                {"category": "Business", "subcategory": "Income", "indicators": []},
                {"category": "Business", "subcategory": "Investment", "indicators": []},
                {"category": "Business", "subcategory": "Cost", "indicators": []},
                {"category": "Business", "subcategory": "Debt", "indicators": []},
                {"category": "Business", "subcategory": "Prices", "indicators": []},
                {"category": "Business", "subcategory": "Production", "indicators": []},
                {"category": "Business", "subcategory": "Confidence", "indicators": []},
                {"category": "Government", "subcategory": "Budget", "indicators": []},
                {
                    "category": "Government",
                    "subcategory": "Financing",
                    "indicators": [],
                },
                {"category": "Government", "subcategory": "Debt", "indicators": []},
            ],
        )

    @patch(
        "data_visualization.services.economic_charts.line_charts.get_cached_economic_display"
    )
    @patch(
        "data_visualization.services.economic_charts.line_charts.set_cached_economic_display"
    )
    def test_get_charts_data_uses_redis_cache(self, mock_set_cache, mock_get_cache):
        """
        GIVEN a Redis cache hit for the charts fingerprint
        WHEN getting economic charts data
        THEN the cached payload is returned without recomputing
        """
        cached_payload = [
            EconomicChartsData(
                category="Macroeconomics",
                subcategory="Growth",
                category_data=[
                    {
                        "period": "2024Q2",
                        "data_value": 3.0,
                        "indicator_name": "GDP Growth",
                        "unit_label": "",
                    }
                ],
                value_axis_label="Data Value",
            )
        ]
        mock_get_cache.return_value = cached_payload
        selected_indicators = [
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
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
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
                selected_indicators=["GDP Growth"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == _charts_payload_with_slot(
            "Macroeconomics",
            "Growth",
            [
                {
                    "period": "2024Q2",
                    "data_value": 3.0,
                    "indicator_name": "GDP Growth",
                    "unit_label": "",
                },
                {
                    "period": "2024Q1",
                    "data_value": 2.5,
                    "indicator_name": "GDP Growth",
                    "unit_label": "",
                },
            ],
        )

    def test_get_charts_data_inflation_category(self):
        """
        GIVEN existing inflation data with selected indicators
        WHEN getting economic charts data
        THEN inflation data is returned correctly (sorted by period descending)
        """
        selected_indicators = [
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.PRICES,
                selected_indicators=["CPI"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == _charts_payload_with_slot(
            "Household",
            "Prices",
            [
                {
                    "period": "2024-02",
                    "data_value": 2.1,
                    "indicator_name": "CPI",
                    "unit_label": "",
                },
                {
                    "period": "2024-01",
                    "data_value": 2.0,
                    "indicator_name": "CPI",
                    "unit_label": "",
                },
            ],
        )

    def test_get_charts_data_empty_selected_list_returns_all_empty(self):
        """
        GIVEN empty selected indicators list
        WHEN getting economic charts data
        THEN all category/subcategory slots are returned with empty data
        """
        result = get_economic_charts_data(self.location, [])
        assert result == _empty_charts_payload()

    def test_get_charts_data_empty_category(self):
        """
        GIVEN a subcategory with no indicators but with selected indicators
        WHEN getting economic charts data
        THEN empty category_data is returned for that slot
        """
        selected_indicators = [
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.HOUSEHOLD,
                subcategory=EconomicDataSubcategoryChoices.HOUSING,
                selected_indicators=["Housing Starts"],
            ),
        ]
        result = get_economic_charts_data(self.location, selected_indicators)
        assert result == _empty_charts_payload()

    def test_parse_selected_indicator_and_mode(self):
        """
        GIVEN [Location|]Type[|MODE] strings
        WHEN parsing
        THEN an optional location prefix and mode suffix are peeled off
        """
        assert _parse_selected_indicator_and_mode("GDP") == {
            "series_label": "GDP",
            "mode": IndicatorDisplayModeChoices.RAW,
            "location": None,
        }
        assert _parse_selected_indicator_and_mode("GDP|YoY") == {
            "series_label": "GDP",
            "mode": IndicatorDisplayModeChoices.ANNUAL,
            "location": None,
        }
        assert _parse_selected_indicator_and_mode("DE|GDP") == {
            "series_label": "GDP",
            "mode": IndicatorDisplayModeChoices.RAW,
            "location": EconomicDataLocationChoices.DE,
        }
        assert _parse_selected_indicator_and_mode("DE|GDP|YoY") == {
            "series_label": "GDP",
            "mode": IndicatorDisplayModeChoices.ANNUAL,
            "location": EconomicDataLocationChoices.DE,
        }
        assert _parse_selected_indicator_and_mode("GDP|QoQy") == {
            "series_label": "GDP",
            "mode": IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
            "location": None,
        }
        with self.assertRaises(ValueError):
            _parse_selected_indicator_and_mode("CPI|BAD")

    def test_get_required_gdp_base_unit_raises_when_missing(self):
        """
        GIVEN a GDP series meta with no base_unit
        WHEN requiring the GDP unit for vsGDP / YTD vs GDP
        THEN a ValueError is raised
        """
        gdp_series = _GdpSeriesForLocation(
            points=[],
            meta=GdpSeriesMeta(ticker="GDP", base_unit=None),
        )
        with self.assertRaises(ValueError) as raised:
            _get_required_gdp_base_unit(gdp_series, location_code="US")
        assert "GDP base_unit is missing" in str(raised.exception)

    def testfilter_time_series_by_period_window_truncates(self):
        """
        GIVEN a long series
        WHEN filtering to a 1Y period window
        THEN only the last year of points remains
        """
        time_series = [
            TimeSeriesPoint(date(2020, 1, 1), 1.0),
            TimeSeriesPoint(date(2023, 6, 1), 2.0),
            TimeSeriesPoint(date(2024, 1, 1), 3.0),
            TimeSeriesPoint(date(2024, 6, 1), 4.0),
        ]
        time_series_in_period_window = filter_time_series_by_period_window(
            time_series, ChartPeriodWindow.ONE_YEAR
        )
        assert time_series_in_period_window == [
            TimeSeriesPoint(date(2023, 6, 1), 2.0),
            TimeSeriesPoint(date(2024, 1, 1), 3.0),
            TimeSeriesPoint(date(2024, 6, 1), 4.0),
        ]
        assert (
            filter_time_series_by_period_window(time_series, ChartPeriodWindow.MAX)
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
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
                selected_indicators=["GDP Growth|YoY"],
            ),
        ]
        result = get_economic_charts_data(
            self.location,
            selected_indicators,
            period_window=ChartPeriodWindow.ONE_YEAR,
        )
        assert result == _charts_payload_with_slot(
            "Macroeconomics",
            "Growth",
            [
                {
                    "period": "2024Q2",
                    "data_value": (122.0 - 112.0) / 112.0 * 100,
                    "indicator_name": "GDP Growth (YoY)",
                    "unit_label": "%",
                },
                {
                    "period": "2024Q1",
                    "data_value": (120.0 - 110.0) / 110.0 * 100,
                    "indicator_name": "GDP Growth (YoY)",
                    "unit_label": "%",
                },
                {
                    "period": "2023Q4",
                    "data_value": (116.0 - 103.0) / 103.0 * 100,
                    "indicator_name": "GDP Growth (YoY)",
                    "unit_label": "%",
                },
                {
                    "period": "2023Q3",
                    "data_value": (114.0 - 102.0) / 102.0 * 100,
                    "indicator_name": "GDP Growth (YoY)",
                    "unit_label": "%",
                },
                {
                    "period": "2023Q2",
                    "data_value": (112.0 - 101.0) / 101.0 * 100,
                    "indicator_name": "GDP Growth (YoY)",
                    "unit_label": "%",
                },
            ],
            value_axis_label="%",
        )

    def test_get_charts_data_europe_plots_selected_country_curves(self):
        """
        GIVEN GDP series for DE / ES / IT / FR
        WHEN getting Cross-Region charts with generic GDP|Raw and DE+FR countries
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
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
                series_label="GDP",
                full_name=name,
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
            SelectedIndicatorsByCategorySubcategory(
                category=EconomicDataCategoryChoices.MACROECONOMICS,
                subcategory=EconomicDataSubcategoryChoices.GROWTH,
                selected_indicators=["GDP|Raw"],
            ),
        ]
        result = get_economic_charts_data(
            None,
            selected_indicators,
            cross_region=True,
            countries=[
                EconomicDataLocationChoices.DE,
                EconomicDataLocationChoices.FR,
            ],
        )
        assert result == _charts_payload_with_slot(
            "Macroeconomics",
            "Growth",
            [
                {
                    "period": "2024Q2",
                    "data_value": 100.0,
                    "indicator_name": "Germany",
                    "unit_label": "",
                },
                {
                    "period": "2024Q2",
                    "data_value": 130.0,
                    "indicator_name": "France",
                    "unit_label": "",
                },
            ],
        )


class TestCrossRegionFrequencyAlign(SimpleTestCase):
    """Cross-Region monthly↔quarterly alignment helpers."""

    def testaggregate_monthly_points_to_quarterly_mean(self):
        """
        GIVEN three monthly values in Q1 and two in Q2
        WHEN aggregating to quarterly means
        THEN each quarter is the mean of its available months at quarter start
        """
        points = [
            TimeSeriesPoint(date(2024, 1, 1), 10.0),
            TimeSeriesPoint(date(2024, 2, 1), 20.0),
            TimeSeriesPoint(date(2024, 3, 1), 30.0),
            TimeSeriesPoint(date(2024, 4, 1), 40.0),
            TimeSeriesPoint(date(2024, 5, 1), 50.0),
        ]
        assert aggregate_monthly_points_to_quarterly_mean(points) == [
            TimeSeriesPoint(date(2024, 1, 1), 20.0),
            TimeSeriesPoint(date(2024, 4, 1), 45.0),
        ]

    def testinterpolate_points_to_monthly(self):
        """
        GIVEN quarterly endpoints at Jan and Apr
        WHEN interpolating to monthly
        THEN Feb and Mar are linear steps between the endpoints
        """
        points = [
            TimeSeriesPoint(date(2024, 1, 1), 100.0),
            TimeSeriesPoint(date(2024, 4, 1), 103.0),
        ]
        assert interpolate_points_to_monthly(points) == [
            TimeSeriesPoint(date(2024, 1, 1), 100.0),
            TimeSeriesPoint(date(2024, 2, 1), 101.0),
            TimeSeriesPoint(date(2024, 3, 1), 102.0),
            TimeSeriesPoint(date(2024, 4, 1), 103.0),
        ]

    def testalign_cross_region_time_series_household_and_employment(self):
        """
        GIVEN monthly household points and quarterly employment points
        WHEN aligning for Cross-Region
        THEN household becomes quarterly means and employment becomes monthly
        """
        monthly_points = [
            TimeSeriesPoint(date(2024, 1, 1), 4.0),
            TimeSeriesPoint(date(2024, 2, 1), 5.0),
            TimeSeriesPoint(date(2024, 3, 1), 6.0),
        ]
        aligned_household, household_frequency = align_cross_region_time_series(
            monthly_points,
            source_frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            series_label="Household Saving Ratio",
        )
        assert household_frequency == EconomicPublicationFrequencyChoices.QUARTERLY
        assert aligned_household == [TimeSeriesPoint(date(2024, 1, 1), 5.0)]

        quarterly_points = [
            TimeSeriesPoint(date(2024, 1, 1), 200.0),
            TimeSeriesPoint(date(2024, 4, 1), 206.0),
        ]
        aligned_employment, employment_frequency = align_cross_region_time_series(
            quarterly_points,
            source_frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            series_label="Employment Level",
        )
        assert employment_frequency == EconomicPublicationFrequencyChoices.MONTHLY
        assert aligned_employment == [
            TimeSeriesPoint(date(2024, 1, 1), 200.0),
            TimeSeriesPoint(date(2024, 2, 1), 202.0),
            TimeSeriesPoint(date(2024, 3, 1), 204.0),
            TimeSeriesPoint(date(2024, 4, 1), 206.0),
        ]


class TestCrossRegionUnemploymentPrefersMonthly(TestCase):
    """Cross-Region picks hidden FR monthly unemployment over INSEE quarterly."""

    def test_get_charts_data_cross_region_uses_hidden_fr_monthly_unemployment(self):
        """
        GIVEN FR quarterly visible and FR monthly hidden unemployment series
        WHEN getting Cross-Region charts for Unemployment Rate
        THEN the monthly FR value is used
        """
        quarterly = EconomicIndicatorInformationModel.objects.create(
            id=11,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.LABOUR,
            series_label="Unemployment Rate",
            full_name="INSEE Quarterly Unemployment Rate",
            technical_name="ILO",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001688527",
            base_unit=IndicatorBaseUnitChoices.PERCENT,
            is_hidden=False,
        )
        monthly = EconomicIndicatorInformationModel.objects.create(
            id=452,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.LABOUR,
            series_label="Unemployment Rate",
            full_name="Eurostat Monthly Unemployment Rate",
            technical_name="Unemployment",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.EUROSTAT,
            ticker="une_rt_m",
            base_unit=IndicatorBaseUnitChoices.PERCENT,
            is_hidden=True,
        )
        EconomicDataModel.objects.create(
            indicator=quarterly,
            period=date(2024, 1, 1),
            data_value=7.5,
        )
        EconomicDataModel.objects.create(
            indicator=monthly,
            period=date(2024, 3, 1),
            data_value=7.1,
        )
        result = get_economic_charts_data(
            None,
            [
                SelectedIndicatorsByCategorySubcategory(
                    category=EconomicDataCategoryChoices.HOUSEHOLD,
                    subcategory=EconomicDataSubcategoryChoices.LABOUR,
                    selected_indicators=["Unemployment Rate|Raw"],
                )
            ],
            cross_region=True,
            countries=[EconomicDataLocationChoices.FR],
        )
        assert result == _charts_payload_with_slot(
            "Household",
            "Labour",
            [
                {
                    "period": "2024-03",
                    "data_value": 7.1,
                    "indicator_name": "France",
                    "unit_label": "%",
                }
            ],
            value_axis_label="%",
        )


class TestBuildValueAxisLabel(SimpleTestCase):
    """Economic chart Y-axis titles."""

    def test_growth_mode_is_percent(self):
        """
        GIVEN Annual display mode
        WHEN building the value axis label
        THEN the axis is labeled as percent
        """
        assert _format_value_axis_label(mode=IndicatorDisplayModeChoices.ANNUAL) == "%"

    def test_amount_raw_includes_unit(self):
        """
        GIVEN Raw mode with billion EUR base
        WHEN building the value axis label
        THEN the axis includes the compact unit
        """
        assert (
            _format_value_axis_label(
                mode=IndicatorDisplayModeChoices.RAW,
                base_unit=IndicatorBaseUnitChoices.B,
                base_currency=IndicatorBaseCurrencyChoices.EUR,
            )
            == "in b€"
        )

    def test_index_raw_mentions_base_year(self):
        """
        GIVEN Raw mode with an index unit and base year
        WHEN building the value axis label
        THEN the axis is Index Level with that base year
        """
        assert (
            _format_value_axis_label(
                mode=IndicatorDisplayModeChoices.RAW,
                base_unit=IndicatorBaseUnitChoices.INDEX,
                base_year=2020,
            )
            == "Index Level (base year: 2020)"
        )

    def test_stock_raw_keeps_data_value(self):
        """
        GIVEN Raw mode with no amount or index unit
        WHEN building the value axis label
        THEN the axis stays Data Value
        """
        assert (
            _format_value_axis_label(
                mode=IndicatorDisplayModeChoices.RAW,
            )
            == "Data Value"
        )
