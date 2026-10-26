"""Tests for economic recap visualization services."""

from datetime import date

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
        self.first_economic_data = EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.first_period,
            data_value=100.0,
        )
        self.second_economic_data = EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.second_period,
            data_value=110.0,
        )

    def test_get_economic_recap_data_success(self):
        """
        GIVEN existing economic data
        WHEN getting economic recap data
        THEN the correct data with current, previous, and change is returned
        """
        locations = [EconomicDataLocationChoices.FR]
        result = get_economic_recap_data(locations)
        assert result == {
            EconomicDataCategoryChoices.CONFIDENCE: [
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
                    "period": self.second_economic_data.get_period_display(),
                    "history": [
                        {
                            "period": self.first_economic_data.get_period_display(),
                            "period_date": self.first_period.isoformat(),
                            "value": 100.0,
                        },
                        {
                            "period": self.second_economic_data.get_period_display(),
                            "period_date": self.second_period.isoformat(),
                            "value": 110.0,
                        },
                    ],
                }
            ]
        }

    def test_get_economic_recap_data_multiple_locations(self):
        """
        GIVEN economic data for multiple locations
        WHEN getting economic recap data
        THEN data for all locations is returned
        """
        indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="US Indicator",
            name="US Indicator Name",
            technical_name="us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        EconomicDataModel.objects.create(
            indicator=indicator_us,
            period=self.first_period,
            data_value=200.0,
        )

        locations = [
            EconomicDataLocationChoices.FR,
            EconomicDataLocationChoices.US,
        ]
        result = get_economic_recap_data(locations)
        assert result == {
            EconomicDataCategoryChoices.GROWTH.value: [
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "change": None,
                    "current": None,
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                    "history": [],
                    "location": EconomicDataLocationChoices.FR.value,
                    "name": "US Indicator",
                    "display_name": "US Indicator",
                    "base_year": None,
                    "base_unit": "",
                    "period": None,
                    "previous": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.US.value,
                    "name": "US Indicator",
                    "display_name": "US Indicator",
                    "base_year": None,
                    "base_unit": "",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                    "current": 200.0,
                    "previous": None,
                    "change": None,
                    "period": self.first_economic_data.get_period_display(),
                    "history": [
                        {
                            "period": self.first_economic_data.get_period_display(),
                            "period_date": self.first_period.isoformat(),
                            "value": 200.0,
                        }
                    ],
                },
            ],
            EconomicDataCategoryChoices.CONFIDENCE.value: [
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.FR.value,
                    "name": "Test Indicator",
                    "display_name": "Test Indicator",
                    "base_year": None,
                    "base_unit": "",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                    "current": 110.0,
                    "previous": 100.0,
                    "change": 10.0,
                    "period": self.second_economic_data.get_period_display(),
                    "history": [
                        {
                            "period": self.first_economic_data.get_period_display(),
                            "period_date": self.first_period.isoformat(),
                            "value": 100.0,
                        },
                        {
                            "period": self.second_economic_data.get_period_display(),
                            "period_date": self.second_period.isoformat(),
                            "value": 110.0,
                        },
                    ],
                },
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "change": None,
                    "current": None,
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                    "history": [],
                    "location": EconomicDataLocationChoices.US.value,
                    "name": "Test Indicator",
                    "display_name": "Test Indicator",
                    "base_year": None,
                    "base_unit": "",
                    "period": None,
                    "previous": None,
                },
            ],
        }

    def test_get_economic_recap_data_no_location(self):
        """
        GIVEN existing economic data
        WHEN getting economic recap data for a location that has no data
        THEN a default economic data based on existing data is returned
        """
        locations = [EconomicDataLocationChoices.JP]
        result = get_economic_recap_data(locations)
        assert result == {
            EconomicDataCategoryChoices.CONFIDENCE.value: [
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.JP.value,
                    "name": "Test Indicator",
                    "display_name": "Test Indicator",
                    "base_year": None,
                    "base_unit": "",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                    "history": [],
                }
            ]
        }
