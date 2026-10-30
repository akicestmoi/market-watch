"""Tests for economic recap views."""

import json
from datetime import date, datetime, timezone

from django.test import Client, TestCase
from freezegun import freeze_time

from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)

_EXPECTED_LOCATIONS = ["US", "FR", "JP"]

_EXPECTED_ECONOMIC_DATA = [
    {
        "category": EconomicDataCategoryChoices.GROWTH,
        "rows": [
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.US,
                "name": "US Indicator",
                "display_name": "US Indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": 115.0,
                "previous": 100.0,
                "change": 15.0,
                "period": "Jul.25",
                "time_series": [
                    {
                        "period": "Jun.25",
                        "period_date": "2025-06-15",
                        "value": 100.0,
                    },
                    {
                        "period": "Jul.25",
                        "period_date": "2025-07-15",
                        "value": 115.0,
                    },
                ],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.FR,
                "name": "US Indicator",
                "display_name": "US Indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.JP,
                "name": "US Indicator",
                "display_name": "US Indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.US,
                "name": "Second US Indicator",
                "display_name": "Second US Indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.FR,
                "name": "Second US Indicator",
                "display_name": "Second US Indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.JP,
                "name": "Second US Indicator",
                "display_name": "Second US Indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.US,
                "name": "JP Indicator",
                "display_name": "JP Indicator",
                "frequency": EconomicPublicationFrequencyChoices.ANNUAL,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.FR,
                "name": "JP Indicator",
                "display_name": "JP Indicator",
                "frequency": EconomicPublicationFrequencyChoices.ANNUAL,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.GROWTH,
                "location": EconomicDataLocationChoices.JP,
                "name": "JP Indicator",
                "display_name": "JP Indicator",
                "frequency": EconomicPublicationFrequencyChoices.ANNUAL,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": 55.0,
                "previous": None,
                "change": None,
                "period": "2025",
                "time_series": [
                    {
                        "period": "2025",
                        "period_date": "2025-06-15",
                        "value": 55.0,
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
                "location": EconomicDataLocationChoices.US,
                "name": "FR Indicator",
                "display_name": "FR Indicator",
                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
            {
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "location": EconomicDataLocationChoices.FR,
                "name": "FR Indicator",
                "display_name": "FR Indicator",
                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": 210.0,
                "previous": 200.0,
                "change": 10.0,
                "period": "25Q3",
                "time_series": [
                    {
                        "period": "24Q2",
                        "period_date": "2024-06-15",
                        "value": 180.0,
                    },
                    {
                        "period": "25Q2",
                        "period_date": "2025-06-15",
                        "value": 200.0,
                    },
                    {
                        "period": "25Q3",
                        "period_date": "2025-07-15",
                        "value": 210.0,
                    },
                ],
            },
            {
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "location": EconomicDataLocationChoices.JP,
                "name": "FR Indicator",
                "display_name": "FR Indicator",
                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                "base_year": None,
                "base_unit": None,
                "base_currency": None,
                "default_mode": "Raw",
                "current": None,
                "previous": None,
                "change": None,
                "period": None,
                "time_series": [],
            },
        ],
    },
]


class TestEconomicRecapView(TestCase):
    """Test cases for economic_recap_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/economic-recap/"
        self.indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="US Indicator",
            name="US Indicator Name",
            technical_name="us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="Second US Indicator",
            name="Second US Indicator Name",
            technical_name="second_us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="FR Indicator",
            name="FR Indicator Name",
            technical_name="fr_indicator",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_jp = EconomicIndicatorInformationModel.objects.create(
            id=4,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GROWTH,
            type="JP Indicator",
            name="JP Indicator Name",
            technical_name="jp_indicator",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565532",
        )
        past_period = date(2024, 6, 15)
        first_period = date(2025, 6, 15)
        second_period = date(2025, 7, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator_us,
            period=first_period,
            data_value=100.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_us,
            period=second_period,
            data_value=115.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=past_period,
            data_value=180.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=first_period,
            data_value=200.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=second_period,
            data_value=210.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_jp,
            period=first_period,
            data_value=55.0,
        )
        PublicationScheduleModel.objects.create(
            indicator=self.indicator_fr,
            current_publication_date=datetime(
                2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc
            ),
            next_publication_date=None,
        )
        PublicationScheduleModel.objects.create(
            indicator=self.indicator_us,
            current_publication_date=datetime(
                2025, 7, 15, 0, 0, 0, tzinfo=timezone.utc
            ),
            next_publication_date=datetime(2025, 8, 14, 0, 0, 0, tzinfo=timezone.utc),
        )

    @freeze_time("2025-07-01")
    def test_economic_recap_view_success(self):
        """
        GIVEN economic data services
        WHEN accessing economic recap view
        THEN the view renders successfully with economic data
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        assert {
            "locations": response.context["locations"],
            "economic_data": response.context["economic_data"],
            "economic_data_json": response.context["economic_data_json"],
            "locations_json": response.context["locations_json"],
        } == {
            "locations": _EXPECTED_LOCATIONS,
            "economic_data": _EXPECTED_ECONOMIC_DATA,
            "economic_data_json": json.dumps(_EXPECTED_ECONOMIC_DATA, default=str),
            "locations_json": json.dumps(_EXPECTED_LOCATIONS),
        }
        assert "upcoming_events" not in response.context

    @freeze_time("2025-08-01")
    def test_economic_recap_view_no_upcoming_events_in_context(self):
        """
        GIVEN publication schedules (including past ones)
        WHEN accessing economic recap view
        THEN upcoming releases are not part of the economic recap context
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        assert {
            "locations": response.context["locations"],
            "economic_data": response.context["economic_data"],
            "economic_data_json": response.context["economic_data_json"],
            "locations_json": response.context["locations_json"],
        } == {
            "locations": _EXPECTED_LOCATIONS,
            "economic_data": _EXPECTED_ECONOMIC_DATA,
            "economic_data_json": json.dumps(_EXPECTED_ECONOMIC_DATA, default=str),
            "locations_json": json.dumps(_EXPECTED_LOCATIONS),
        }
        assert "upcoming_events" not in response.context
