"""Tests for economic recap visualization services."""

from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from freezegun import freeze_time

from data_visualization.services.economic_recap.final_data import (
    get_economic_recap_data,
)
from data_visualization.services.economic_recap.table_content import (
    AnnualGdpGrowthTriplet,
    _format_recap_line_unit_parenthesis,
    _format_spaced_number,
    _GdpLevelPoint,
    _scale_amount_for_display,
    _ScaledAmount,
    compute_annual_gdp_growth_triplet,
    format_amount_unit_label,
    format_indicator_value,
)
from data_visualization.services.economic_recap.table_filter import (
    EconomicRecapAsOfSelection,
    EconomicRecapComparisonChoices,
    build_economic_recap_as_of_query_string,
    get_default_comparison_for_economic_recap,
    list_as_of_years_for_economic_recap,
    parse_economic_recap_as_of,
    parse_economic_recap_comparison,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorAmountMagnitudeChoices,
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
    IndicatorMeasureTypeChoices,
    IndicatorPriceBasisChoices,
)


@freeze_time("2025-12-16")
class TestEconomicRecapServices(TestCase):
    """Test cases for economic_recap functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
            series_label="Test Indicator",
            full_name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.first_period = date(2024, 1, 15)
        self.second_period = date(2024, 2, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.first_period,
            data_value=100.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.second_period,
            data_value=110.0,
        )

    @patch(
        "data_visualization.services.economic_recap.final_data.get_cached_economic_display"
    )
    @patch(
        "data_visualization.services.economic_recap.final_data.set_cached_economic_display"
    )
    def test_get_economic_recap_data_uses_redis_cache(
        self, mock_set_cache, mock_get_cache
    ):
        """
        GIVEN a Redis cache hit for the recap fingerprint
        WHEN getting economic recap data
        THEN the cached economic recap payload is returned without recomputing
        """
        cached_payload = [
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "Test Indicator",
                                "display_name": "Test Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "test_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 110.0,
                                "previous": 100.0,
                                "change": 10.0,
                                "period": "Feb.24",
                                "time_series": [],
                            }
                        ],
                    }
                ],
            }
        ]
        mock_get_cache.return_value = cached_payload

        result = get_economic_recap_data([EconomicDataLocationChoices.FR])

        assert result == cached_payload
        mock_set_cache.assert_not_called()

    def test_get_economic_recap_data_success(self):
        """
        GIVEN existing economic data
        WHEN getting economic recap data
        THEN the correct data with current, previous, and change is returned
        """
        result = get_economic_recap_data([EconomicDataLocationChoices.FR])
        assert result == [
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "Test Indicator",
                                "display_name": "Test Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "test_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 110.0,
                                "previous": 100.0,
                                "change": 10.0,
                                "period": "Feb.24",
                                "time_series": [
                                    {
                                        "period": "Jan.24",
                                        "period_date": "2024-01-15",
                                        "value": 100.0,
                                    },
                                    {
                                        "period": "Feb.24",
                                        "period_date": "2024-02-15",
                                        "value": 110.0,
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]

    def test_get_economic_recap_data_aligns_shared_type_across_locations(self):
        """
        GIVEN the same indicator type seeded for FR and US
        WHEN getting economic recap data for both locations
        THEN one line name is used with exactly one cell per location
        """
        indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP",
            full_name="United States Real GDP",
            technical_name="Gross Domestic Product",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GDPC1",
        )
        indicator_fr_gdp = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP",
            full_name="France GDP",
            technical_name="Quarterly national accounts - first estimate",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="011794860",
        )
        EconomicDataModel.objects.create(
            indicator=indicator_us,
            period=self.first_period,
            data_value=200.0,
        )
        EconomicDataModel.objects.create(
            indicator=indicator_fr_gdp,
            period=self.first_period,
            data_value=150.0,
        )

        result = get_economic_recap_data(
            [EconomicDataLocationChoices.FR, EconomicDataLocationChoices.US]
        )
        assert result == [
            {
                "category": EconomicDataCategoryChoices.MACROECONOMICS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.MACROECONOMICS,
                                "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "GDP",
                                "display_name": "GDP",
                                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "Quarterly national accounts - first estimate",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 150.0,
                                "previous": None,
                                "change": None,
                                "period": "24Q1",
                                "time_series": [
                                    {
                                        "period": "24Q1",
                                        "period_date": "2024-01-15",
                                        "value": 150.0,
                                    }
                                ],
                            },
                            {
                                "category": EconomicDataCategoryChoices.MACROECONOMICS,
                                "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                                "location": EconomicDataLocationChoices.US,
                                "name": "GDP",
                                "display_name": "GDP",
                                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                                "source": EconomicDataSourceChoices.FRED,
                                "technical_name": "Gross Domestic Product",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": True,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 200.0,
                                "previous": None,
                                "change": None,
                                "period": "24Q1",
                                "time_series": [
                                    {
                                        "period": "24Q1",
                                        "period_date": "2024-01-15",
                                        "value": 200.0,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "Test Indicator",
                                "display_name": "Test Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "test_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 110.0,
                                "previous": 100.0,
                                "change": 10.0,
                                "period": "Feb.24",
                                "time_series": [
                                    {
                                        "period": "Jan.24",
                                        "period_date": "2024-01-15",
                                        "value": 100.0,
                                    },
                                    {
                                        "period": "Feb.24",
                                        "period_date": "2024-02-15",
                                        "value": 110.0,
                                    },
                                ],
                            },
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.US,
                                "name": "Test Indicator",
                                "display_name": "Test Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "test_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": None,
                                "previous": None,
                                "change": None,
                                "period": None,
                                "time_series": [],
                            },
                        ],
                    }
                ],
            },
        ]

    def test_get_economic_recap_data_country_only_type_pads_other_locations(self):
        """
        GIVEN a US-only indicator type with description and docs URL
        WHEN getting economic recap data for FR and US
        THEN the FR cell is an empty placeholder (no copied description / URL)
        """
        indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.HOUSEHOLD,
            subcategory=EconomicDataSubcategoryChoices.LABOUR,
            series_label="Nonfarm Payrolls",
            full_name="United States Nonfarm Payrolls",
            technical_name="Employment Situation",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="PAYEMS",
            description=(
                "Employees on nonfarm payrolls — the main US payroll "
                "employment gauge."
            ),
            source_url="https://fred.stlouisfed.org/series/PAYEMS",
        )
        EconomicDataModel.objects.create(
            indicator=indicator_us,
            period=self.first_period,
            data_value=200.0,
        )

        result = get_economic_recap_data(
            [EconomicDataLocationChoices.FR, EconomicDataLocationChoices.US]
        )
        assert result == [
            {
                "category": EconomicDataCategoryChoices.HOUSEHOLD,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.LABOUR,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.HOUSEHOLD,
                                "subcategory": EconomicDataSubcategoryChoices.LABOUR,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "Nonfarm Payrolls",
                                "display_name": "Nonfarm Payrolls",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.FRED,
                                "technical_name": "Employment Situation",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": None,
                                "previous": None,
                                "change": None,
                                "period": None,
                                "time_series": [],
                            },
                            {
                                "category": EconomicDataCategoryChoices.HOUSEHOLD,
                                "subcategory": EconomicDataSubcategoryChoices.LABOUR,
                                "location": EconomicDataLocationChoices.US,
                                "name": "Nonfarm Payrolls",
                                "display_name": "Nonfarm Payrolls",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.FRED,
                                "technical_name": "Employment Situation",
                                "description": (
                                    "Employees on nonfarm payrolls — the main "
                                    "US payroll employment gauge."
                                ),
                                "source_url": (
                                    "https://fred.stlouisfed.org/series/PAYEMS"
                                ),
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 200.0,
                                "previous": None,
                                "change": None,
                                "period": "Jan.24",
                                "time_series": [
                                    {
                                        "period": "Jan.24",
                                        "period_date": "2024-01-15",
                                        "value": 200.0,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "Test Indicator",
                                "display_name": "Test Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "test_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 110.0,
                                "previous": 100.0,
                                "change": 10.0,
                                "period": "Feb.24",
                                "time_series": [
                                    {
                                        "period": "Jan.24",
                                        "period_date": "2024-01-15",
                                        "value": 100.0,
                                    },
                                    {
                                        "period": "Feb.24",
                                        "period_date": "2024-02-15",
                                        "value": 110.0,
                                    },
                                ],
                            },
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.US,
                                "name": "Test Indicator",
                                "display_name": "Test Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "test_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": None,
                                "previous": None,
                                "change": None,
                                "period": None,
                                "time_series": [],
                            },
                        ],
                    }
                ],
            },
        ]

    def test_get_economic_recap_data_duplicate_type_in_location_uses_name(self):
        """
        GIVEN two JP indicators sharing the same type
        WHEN getting economic recap data
        THEN each series keeps its own line keyed by indicator name
        """
        large = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
            series_label="Manufacturing Business Confidence",
            full_name="Japan Tankan Large Enterprises Manufacturing DI",
            technical_name="Tankan",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.BOJ,
            ticker="business_conditions_large_mfg",
        )
        medium = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
            series_label="Manufacturing Business Confidence",
            full_name="Japan Tankan Medium-sized Enterprises Manufacturing DI",
            technical_name="Tankan",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.BOJ,
            ticker="business_conditions_medium_mfg",
        )
        EconomicDataModel.objects.create(
            indicator=large, period=self.first_period, data_value=10.0
        )
        EconomicDataModel.objects.create(
            indicator=medium, period=self.first_period, data_value=5.0
        )

        result = get_economic_recap_data([EconomicDataLocationChoices.JP])
        assert result == [
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 2,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                        "indicator_row_count": 2,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.JP,
                                "name": "Japan Tankan Large Enterprises Manufacturing DI",
                                "display_name": "Manufacturing Business Confidence",
                                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                                "source": EconomicDataSourceChoices.BOJ,
                                "technical_name": "Tankan",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 10.0,
                                "previous": None,
                                "change": None,
                                "period": "24Q1",
                                "time_series": [
                                    {
                                        "period": "24Q1",
                                        "period_date": "2024-01-15",
                                        "value": 10.0,
                                    }
                                ],
                            },
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.JP,
                                "name": (
                                    "Japan Tankan Medium-sized Enterprises "
                                    "Manufacturing DI"
                                ),
                                "display_name": "Manufacturing Business Confidence",
                                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                                "source": EconomicDataSourceChoices.BOJ,
                                "technical_name": "Tankan",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 5.0,
                                "previous": None,
                                "change": None,
                                "period": "24Q1",
                                "time_series": [
                                    {
                                        "period": "24Q1",
                                        "period_date": "2024-01-15",
                                        "value": 5.0,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ]

    def test_get_economic_recap_data_same_type_different_categories_uses_type(self):
        """
        GIVEN MACRO and BUSINESS US indicators that share the type label
        WHEN getting economic recap data
        THEN each category keeps a line keyed by type (not the long series name)
        """
        macro_investment = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Business Investment",
            full_name="United States Real Gross Private Domestic Business Investment",
            technical_name="Gross Domestic Product",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GPDIC1",
            parent_series_label="Real GDP",
            expansion_relation="COMPONENT",
        )
        business_investment = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.INVESTMENT,
            series_label="Business Investment",
            full_name="United States Real Private Nonresidential Fixed Investment",
            technical_name="Gross Domestic Product",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="PNFIC1",
        )
        EconomicDataModel.objects.create(
            indicator=macro_investment, period=self.first_period, data_value=100.0
        )
        EconomicDataModel.objects.create(
            indicator=business_investment, period=self.first_period, data_value=80.0
        )

        result = get_economic_recap_data([EconomicDataLocationChoices.US])
        assert result == [
            {
                "category": EconomicDataCategoryChoices.MACROECONOMICS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.MACROECONOMICS,
                                "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                                "location": EconomicDataLocationChoices.US,
                                "name": "Business Investment",
                                "display_name": "Business Investment",
                                "frequency": (
                                    EconomicPublicationFrequencyChoices.QUARTERLY
                                ),
                                "source": EconomicDataSourceChoices.FRED,
                                "technical_name": "Gross Domestic Product",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": True,
                                "is_seasonally_adjusted": True,
                                "price_basis": IndicatorPriceBasisChoices.REAL,
                                # Parent Real GDP is not in this payload, so the
                                # COMPONENT link is cleared and the line stands alone.
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": IndicatorDisplayModeChoices.RAW,
                                "supports_vs_gdp": False,
                                "current": 100.0,
                                "previous": None,
                                "change": None,
                                "period": "24Q1",
                                "time_series": [
                                    {
                                        "period": "24Q1",
                                        "period_date": "2024-01-15",
                                        "value": 100.0,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.INVESTMENT,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.INVESTMENT,
                                "location": EconomicDataLocationChoices.US,
                                "name": "Business Investment",
                                "display_name": "Business Investment",
                                "frequency": (
                                    EconomicPublicationFrequencyChoices.QUARTERLY
                                ),
                                "source": EconomicDataSourceChoices.FRED,
                                "technical_name": "Gross Domestic Product",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": IndicatorPriceBasisChoices.REAL,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": IndicatorDisplayModeChoices.RAW,
                                "supports_vs_gdp": False,
                                "current": 80.0,
                                "previous": None,
                                "change": None,
                                "period": "24Q1",
                                "time_series": [
                                    {
                                        "period": "24Q1",
                                        "period_date": "2024-01-15",
                                        "value": 80.0,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]

    def test_get_economic_recap_data_trade_order_follows_catalog_ids(self):
        """
        GIVEN FR Current Account seeded with a lower id than FR REER
        WHEN getting economic recap data for FR only
        THEN top-level TRADE order follows catalog id order
        """
        fr_current_account = EconomicIndicatorInformationModel.objects.create(
            id=20,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.TRADE,
            series_label="Current Account",
            full_name="France Current Account",
            technical_name="Balance of payments",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.EUROSTAT,
            ticker="bop_c6_q_ca",
        )
        fr_reer = EconomicIndicatorInformationModel.objects.create(
            id=21,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.TRADE,
            series_label="Real Effective Exchange Rate",
            full_name="France Real Broad Effective Exchange Rate",
            technical_name="BIS Effective Exchange Rate Indices",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="RBFRBIS",
        )
        EconomicDataModel.objects.create(
            indicator=fr_current_account, period=self.first_period, data_value=1.0
        )
        EconomicDataModel.objects.create(
            indicator=fr_reer, period=self.first_period, data_value=100.0
        )

        result = get_economic_recap_data([EconomicDataLocationChoices.FR])
        trade_entries = result[0]["subcategories"][0]["entries"]
        assert [entry["name"] for entry in trade_entries] == [
            "Current Account",
            "Real Effective Exchange Rate",
        ]

    def test_get_economic_recap_data_no_location(self):
        """
        GIVEN only FR indicators exist
        WHEN getting economic recap data for JP
        THEN no placeholder lines are invented for missing locations' indicators
        """
        result = get_economic_recap_data([EconomicDataLocationChoices.JP])
        assert result == []


class TestComputeAnnualGdpGrowthTriplet(SimpleTestCase):
    """Trailing-4Q estimate vs sourced OECD realized annual growth."""

    @staticmethod
    def _quarter_point(year: int, quarter: int, value: float) -> _GdpLevelPoint:
        """Build a Real GDP-like quarter point (period = first month of quarter)."""
        month = (quarter - 1) * 3 + 1
        return _GdpLevelPoint(period=date(year, month, 1), data_value=value)

    @staticmethod
    def _annual_point(year: int, value: float) -> _GdpLevelPoint:
        """Build a sourced realized annual growth point."""
        return _GdpLevelPoint(period=date(year, 1, 1), data_value=value)

    def test_period_level_sum_trailing_and_sourced_previous(self):
        """
        GIVEN eight period-level Real GDP quarters and a sourced 2023 annual print
        WHEN computing the annual GDP growth triplet
        THEN Current is trailing-4Q growth, Previous is sourced, Period is 2024
        """
        chronological = [
            self._quarter_point(2023, quarter, 100.0) for quarter in range(1, 5)
        ] + [self._quarter_point(2024, quarter, 110.0) for quarter in range(1, 5)]
        newest_first = list(reversed(chronological))
        realized_newest_first = [
            self._annual_point(2024, 9.5),
            self._annual_point(2023, 2.1),
        ]
        assert compute_annual_gdp_growth_triplet(
            newest_first,
            realized_newest_first,
            is_annualized=False,
        ) == AnnualGdpGrowthTriplet(
            current=10.0,
            previous=2.1,
            change=7.9,
            period="2024",
            time_series=[
                {
                    "period": "2023",
                    "period_date": "2023-01-01",
                    "value": 2.1,
                },
                {
                    "period": "2024",
                    "period_date": "2024-01-01",
                    "value": 10.0,
                },
            ],
        )

    def test_annualized_averages_quarters(self):
        """
        GIVEN eight SAAR Real GDP quarters and a sourced previous year
        WHEN computing with is_annualized=True
        THEN windows use the average of four prints (not the sum)
        """
        chronological = [
            self._quarter_point(2023, quarter, 100.0) for quarter in range(1, 5)
        ] + [self._quarter_point(2024, quarter, 110.0) for quarter in range(1, 5)]
        newest_first = list(reversed(chronological))
        realized_newest_first = [self._annual_point(2023, 2.1)]
        assert compute_annual_gdp_growth_triplet(
            newest_first,
            realized_newest_first,
            is_annualized=True,
        ) == AnnualGdpGrowthTriplet(
            current=10.0,
            previous=2.1,
            change=7.9,
            period="2024",
            time_series=[
                {
                    "period": "2023",
                    "period_date": "2023-01-01",
                    "value": 2.1,
                },
                {
                    "period": "2024",
                    "period_date": "2024-01-01",
                    "value": 10.0,
                },
            ],
        )

    def test_estimate_differs_from_sourced_previous_mid_year(self):
        """
        GIVEN two complete years plus two stronger 2025 quarters and a 2024 print
        WHEN computing the triplet
        THEN Period is 2025 and Previous is the sourced 2024 print
        """
        chronological = (
            [self._quarter_point(2023, quarter, 100.0) for quarter in range(1, 5)]
            + [self._quarter_point(2024, quarter, 110.0) for quarter in range(1, 5)]
            + [
                self._quarter_point(2025, 1, 130.0),
                self._quarter_point(2025, 2, 130.0),
            ]
        )
        newest_first = list(reversed(chronological))
        realized_newest_first = [
            self._annual_point(2025, 3.0),
            self._annual_point(2024, 2.5),
        ]
        result = compute_annual_gdp_growth_triplet(
            newest_first,
            realized_newest_first,
            is_annualized=False,
        )
        assert result == AnnualGdpGrowthTriplet(
            current=round(480.0 / 420.0 * 100.0 - 100.0, 10),
            previous=2.5,
            change=round(480.0 / 420.0 * 100.0 - 100.0, 10) - 2.5,
            period="2025",
            time_series=[
                {
                    "period": "2024",
                    "period_date": "2024-01-01",
                    "value": 2.5,
                },
                {
                    "period": "2025",
                    "period_date": "2025-01-01",
                    "value": round(480.0 / 420.0 * 100.0 - 100.0, 10),
                },
            ],
        )

    def test_falls_back_to_calendar_year_growth_when_no_sourced_series(self):
        """
        GIVEN complete 2023–2024 Real GDP plus early 2025 and no annual series
        WHEN computing the triplet
        THEN Previous is 2024 vs 2023 calendar-year growth from Real GDP
        """
        chronological = (
            [self._quarter_point(2023, quarter, 100.0) for quarter in range(1, 5)]
            + [self._quarter_point(2024, quarter, 110.0) for quarter in range(1, 5)]
            + [
                self._quarter_point(2025, 1, 130.0),
                self._quarter_point(2025, 2, 130.0),
            ]
        )
        newest_first = list(reversed(chronological))
        current = round(480.0 / 420.0 * 100.0 - 100.0, 10)
        assert compute_annual_gdp_growth_triplet(
            newest_first,
            [],
            is_annualized=False,
        ) == AnnualGdpGrowthTriplet(
            current=current,
            previous=10.0,
            change=current - 10.0,
            period="2025",
            time_series=[
                {
                    "period": "2024",
                    "period_date": "2024-01-01",
                    "value": 10.0,
                },
                {
                    "period": "2025",
                    "period_date": "2025-01-01",
                    "value": current,
                },
            ],
        )


class TestFormatAmountHelpers(SimpleTestCase):
    """Amount scaling and unit label helpers."""

    def test_format_amount_unit_label(self):
        """
        GIVEN a magnitude and optional currency
        WHEN formatting the amount unit label
        THEN the compact label uses magnitude + currency symbol
        """
        assert (
            format_amount_unit_label(
                IndicatorAmountMagnitudeChoices.B,
                IndicatorBaseCurrencyChoices.USD,
            )
            == "b$"
        )
        assert (
            format_amount_unit_label(
                IndicatorAmountMagnitudeChoices.T,
                IndicatorBaseCurrencyChoices.EUR,
            )
            == "t€"
        )
        assert (
            format_amount_unit_label(
                IndicatorAmountMagnitudeChoices.M,
                IndicatorBaseCurrencyChoices.JPY,
            )
            == "m¥"
        )
        assert format_amount_unit_label(IndicatorAmountMagnitudeChoices.M) == "m"

    def test_scale_amount_bumps_magnitude(self):
        """
        GIVEN a billion-scale value above 999
        WHEN scaling for display
        THEN the value is divided by 1_000 and magnitude becomes T
        """
        assert _scale_amount_for_display(
            1_500.0,
            IndicatorAmountMagnitudeChoices.B,
            IndicatorBaseCurrencyChoices.USD,
        ) == _ScaledAmount(
            value=1.5,
            magnitude=IndicatorAmountMagnitudeChoices.T,
            currency=IndicatorBaseCurrencyChoices.USD,
        )

    def test_format_spaced_number(self):
        """
        GIVEN a large float
        WHEN formatting with space thousands separators
        THEN integer groups are space-separated
        """
        assert _format_spaced_number(1234.5, digits=2) == "1 234.50"
        assert _format_spaced_number(-12.3, digits=1) == "-12.3"


class TestFormatIndicatorValue(SimpleTestCase):
    """Single-value formatting for UI / LLM."""

    def test_none_returns_empty(self):
        """
        GIVEN a None value
        WHEN formatting
        THEN an empty string is returned
        """
        assert format_indicator_value(None) == ""

    def test_percent_mode_appends_percent(self):
        """
        GIVEN a growth-mode value
        WHEN formatting with unit label
        THEN a trailing percent sign is appended
        """
        assert (
            format_indicator_value(
                1.25,
                mode=IndicatorDisplayModeChoices.QUARTER,
                include_unit_label=True,
            )
            == "1.25 %"
        )

    def test_amount_raw_with_currency(self):
        """
        GIVEN a raw billion USD amount
        WHEN formatting with unit label
        THEN the scaled value uses magnitude + currency symbol
        """
        assert (
            format_indicator_value(
                1_500.0,
                base_unit=IndicatorBaseUnitChoices.B,
                base_currency="USD",
                mode=IndicatorDisplayModeChoices.RAW,
            )
            == "1.50 t$"
        )

    def test_amount_shared_magnitude_keeps_previous_on_same_scale(self):
        """
        GIVEN a current value that scales to trillions and a smaller previous
        WHEN formatting previous with the shared magnitude from current
        THEN previous keeps the trillion unit instead of staying in billions
        """
        assert (
            format_indicator_value(
                850.0,
                base_unit=IndicatorBaseUnitChoices.B,
                base_currency="USD",
                mode=IndicatorDisplayModeChoices.RAW,
                amount_magnitude=IndicatorAmountMagnitudeChoices.T,
            )
            == "0.85 t$"
        )

    def test_index_raw_number_only(self):
        """
        GIVEN an index-series value
        WHEN formatting in Raw mode
        THEN only the spaced number is returned
        """
        assert (
            format_indicator_value(
                102.5,
                base_unit=IndicatorBaseUnitChoices.INDEX,
                mode=IndicatorDisplayModeChoices.RAW,
            )
            == "102.50"
        )

    def test_ytd_raw_keeps_amount_units(self):
        """
        GIVEN a year-to-date cumulative amount
        WHEN formatting in YTDRaw mode
        THEN amount magnitude units are used instead of a bare percent
        """
        assert (
            format_indicator_value(
                1_500.0,
                base_unit=IndicatorBaseUnitChoices.B,
                base_currency="USD",
                mode=IndicatorDisplayModeChoices.YTD_RAW,
            )
            == "1.50 t$"
        )


class TestFormatRecapRowUnitParenthetical(TestCase):
    """Cross-location unit / base-year parentheticals for recap line titles."""

    def setUp(self):
        """Create two amount indicators that disagree on unit."""
        self.us_gdp = EconomicIndicatorInformationModel.objects.create(
            id=101,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP",
            full_name="US GDP",
            technical_name="us_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GDP",
            base_unit=IndicatorBaseUnitChoices.B,
            base_currency="USD",
        )
        self.jp_gdp = EconomicIndicatorInformationModel.objects.create(
            id=102,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="GDP",
            full_name="JP GDP",
            technical_name="jp_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="JPNGDPNQDSMEI",
            base_unit=IndicatorBaseUnitChoices.B,
            base_currency="JPY",
        )

    def test_growth_mode_has_no_name_unit(self):
        """
        GIVEN any indicators
        WHEN formatting the unit parenthetical in Quarter mode
        THEN the name suffix is empty (percent lives on value cells)
        """
        assert (
            _format_recap_line_unit_parenthesis(
                [self.us_gdp, self.jp_gdp],
                mode=IndicatorDisplayModeChoices.QUARTER,
            )
            == ""
        )

    def test_amount_units_omitted_from_name(self):
        """
        GIVEN US and JP GDP with different currencies
        WHEN formatting the Raw unit parenthetical
        THEN the name suffix is empty (amount units live on value cells)
        """
        assert (
            _format_recap_line_unit_parenthesis(
                [self.us_gdp, self.jp_gdp],
                mode=IndicatorDisplayModeChoices.RAW,
            )
            == ""
        )


class TestEconomicRecapAsOfHelpers(SimpleTestCase):
    """Unit tests for economic recap as-of year / quarter / month parsing."""

    @freeze_time("2025-07-01")
    def test_list_as_of_years_for_economic_recap(self):
        """
        GIVEN today is mid-2025
        WHEN listing as-of years
        THEN the fixed range runs newest-first from 2025 through 2010
        """
        assert list_as_of_years_for_economic_recap() == list(range(2025, 2009, -1))

    def test_parse_economic_recap_as_of_latest(self):
        """
        GIVEN no as-of year
        WHEN parsing as-of params
        THEN Latest is returned with no end date
        """
        assert parse_economic_recap_as_of(
            as_of_year=None,
            as_of_quarter=None,
            as_of_month=None,
            today=date(2025, 7, 1),
        ) == EconomicRecapAsOfSelection(
            year=None, quarter=None, month=None, end_date=None
        )

    def test_parse_economic_recap_as_of_year_alone_defaults_to_december(self):
        """
        GIVEN only as_of_year
        WHEN parsing as-of params
        THEN the end date is 31 Dec of that year and month stays unset
        """
        assert parse_economic_recap_as_of(
            as_of_year="2024",
            as_of_quarter=None,
            as_of_month=None,
            today=date(2025, 7, 1),
        ) == EconomicRecapAsOfSelection(
            year=2024, quarter=None, month=None, end_date=date(2024, 12, 31)
        )

    def test_parse_economic_recap_as_of_quarter(self):
        """
        GIVEN year and quarter
        WHEN parsing as-of params
        THEN the end date is the quarter-end month and month stays unset
        """
        assert parse_economic_recap_as_of(
            as_of_year="2025",
            as_of_quarter="1",
            as_of_month=None,
            today=date(2025, 7, 1),
        ) == EconomicRecapAsOfSelection(
            year=2025, quarter=1, month=None, end_date=date(2025, 3, 31)
        )

    def test_parse_economic_recap_as_of_month_wins_over_quarter(self):
        """
        GIVEN both quarter and month
        WHEN parsing as-of params
        THEN month wins and quarter is cleared
        """
        selection = parse_economic_recap_as_of(
            as_of_year="2025",
            as_of_quarter="2",
            as_of_month="5",
            today=date(2025, 7, 1),
        )
        assert selection == EconomicRecapAsOfSelection(
            year=2025, quarter=None, month=5, end_date=date(2025, 5, 31)
        )
        assert build_economic_recap_as_of_query_string(selection) == (
            "as_of_year=2025&as_of_month=5"
        )

    def test_get_default_comparison_for_economic_recap(self):
        """
        GIVEN As-of Latest / year-only / quarter / month selections
        WHEN resolving the Comparison default
        THEN Latest / Year / Quarter / Latest are returned
        """
        assert (
            get_default_comparison_for_economic_recap(
                year=None, quarter=None, month=None
            )
            == EconomicRecapComparisonChoices.LATEST
        )
        assert (
            get_default_comparison_for_economic_recap(
                year=2024, quarter=None, month=None
            )
            == EconomicRecapComparisonChoices.YEAR
        )
        assert (
            get_default_comparison_for_economic_recap(year=2024, quarter=2, month=None)
            == EconomicRecapComparisonChoices.QUARTER
        )
        assert (
            get_default_comparison_for_economic_recap(year=2024, quarter=None, month=5)
            == EconomicRecapComparisonChoices.LATEST
        )

    def test_parse_economic_recap_comparison_rejects_quarter_on_year_only(self):
        """
        GIVEN year-only As-of and Comparison=Quarter
        WHEN parsing comparison
        THEN Comparison falls back to Year
        """
        assert (
            parse_economic_recap_comparison(
                "Quarter", year=2024, quarter=None, month=None
            )
            == EconomicRecapComparisonChoices.YEAR
        )

    def test_build_economic_recap_as_of_query_string_includes_non_default_comparison(
        self,
    ):
        """
        GIVEN year-only As-of with an overridden Comparison=Latest
        WHEN building the as-of query string
        THEN comparison is included because it differs from the Year default
        """
        selection = EconomicRecapAsOfSelection(
            year=2024, quarter=None, month=None, end_date=date(2024, 12, 31)
        )
        assert (
            build_economic_recap_as_of_query_string(
                selection, comparison=EconomicRecapComparisonChoices.LATEST
            )
            == "as_of_year=2024&comparison=Latest"
        )
