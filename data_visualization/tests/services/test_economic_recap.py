"""Tests for economic recap visualization services."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time

from data_visualization.services.economic_recap import get_economic_recap_data
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


@freeze_time("2025-12-16")
class TestEconomicRecapServices(TestCase):
    """Test cases for economic_recap functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Test Indicator",
            name="Test Indicator Name",
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

    @patch("data_visualization.services.economic_recap.get_cached_economic_display")
    @patch("data_visualization.services.economic_recap.set_cached_economic_display")
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
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.FR,
                        "name": "Test Indicator",
                        "display_name": "Test Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
                        "current": 110.0,
                        "previous": 100.0,
                        "change": 10.0,
                        "period": "Feb.24",
                        "time_series": [],
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
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.FR,
                        "name": "Test Indicator",
                        "display_name": "Test Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
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
        ]

    def test_get_economic_recap_data_aligns_shared_type_across_locations(self):
        """
        GIVEN the same indicator type seeded for FR and US
        WHEN getting economic recap data for both locations
        THEN one row name is used with exactly one cell per location
        """
        indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP",
            name="United States Real GDP",
            technical_name="Gross Domestic Product",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="GDPC1",
        )
        indicator_fr_gdp = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.GROWTH,
            type="GDP",
            name="France GDP",
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
                "category": EconomicDataCategoryChoices.GROWTH,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.GROWTH,
                        "location": EconomicDataLocationChoices.FR,
                        "name": "GDP",
                        "display_name": "GDP",
                        "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                        "base_year": None,
                        "base_unit": "",
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
                        "category": EconomicDataCategoryChoices.GROWTH,
                        "location": EconomicDataLocationChoices.US,
                        "name": "GDP",
                        "display_name": "GDP",
                        "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                        "base_year": None,
                        "base_unit": "",
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
            },
            {
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.FR,
                        "name": "Test Indicator",
                        "display_name": "Test Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
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
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.US,
                        "name": "Test Indicator",
                        "display_name": "Test Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
                        "current": None,
                        "previous": None,
                        "change": None,
                        "period": None,
                        "time_series": [],
                    },
                ],
            },
        ]

    def test_get_economic_recap_data_country_only_type_pads_other_locations(self):
        """
        GIVEN a US-only indicator type
        WHEN getting economic recap data for FR and US
        THEN the FR cell is an empty placeholder on the same row name
        """
        indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.LABOUR,
            type="Nonfarm Payrolls",
            name="United States Nonfarm Payrolls",
            technical_name="Employment Situation",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="PAYEMS",
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
                "category": EconomicDataCategoryChoices.LABOUR,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.LABOUR,
                        "location": EconomicDataLocationChoices.FR,
                        "name": "Nonfarm Payrolls",
                        "display_name": "Nonfarm Payrolls",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
                        "current": None,
                        "previous": None,
                        "change": None,
                        "period": None,
                        "time_series": [],
                    },
                    {
                        "category": EconomicDataCategoryChoices.LABOUR,
                        "location": EconomicDataLocationChoices.US,
                        "name": "Nonfarm Payrolls",
                        "display_name": "Nonfarm Payrolls",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
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
            },
            {
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.FR,
                        "name": "Test Indicator",
                        "display_name": "Test Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
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
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.US,
                        "name": "Test Indicator",
                        "display_name": "Test Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "base_year": None,
                        "base_unit": "",
                        "current": None,
                        "previous": None,
                        "change": None,
                        "period": None,
                        "time_series": [],
                    },
                ],
            },
        ]

    def test_get_economic_recap_data_duplicate_type_in_location_uses_name(self):
        """
        GIVEN two JP indicators sharing the same type
        WHEN getting economic recap data
        THEN each series keeps its own row keyed by indicator name
        """
        large = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Manufacturing Business Confidence",
            name="Japan Tankan Large Enterprises Manufacturing DI",
            technical_name="Tankan",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.BOJ,
            ticker="business_conditions_large_mfg",
        )
        medium = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Manufacturing Business Confidence",
            name="Japan Tankan Medium-sized Enterprises Manufacturing DI",
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
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "rows": [
                    {
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.JP,
                        "name": "Japan Tankan Large Enterprises Manufacturing DI",
                        "display_name": "Manufacturing Business Confidence",
                        "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                        "base_year": None,
                        "base_unit": "",
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
                        "category": EconomicDataCategoryChoices.CONFIDENCE,
                        "location": EconomicDataLocationChoices.JP,
                        "name": "Japan Tankan Medium-sized Enterprises Manufacturing DI",
                        "display_name": "Manufacturing Business Confidence",
                        "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                        "base_year": None,
                        "base_unit": "",
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
        ]

    def test_get_economic_recap_data_no_location(self):
        """
        GIVEN only FR indicators exist
        WHEN getting economic recap data for JP
        THEN no placeholder rows are invented for missing locations' indicators
        """
        result = get_economic_recap_data([EconomicDataLocationChoices.JP])
        assert result == []
