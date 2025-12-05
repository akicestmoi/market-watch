from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from freezegun import freeze_time  # type: ignore[reportMissingImports]

from data_visualization.services.economic_recap_services import (
    _get_upcoming_events_from_publication_schedules,
    _get_upcoming_holidays_events,
    get_economic_recap_data,
    get_economic_recap_upcoming_events,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from market_overview.models import HolidayModel, LocationChoices


class TestEconomicRecapServices(TestCase):
    """Test cases for economic_recap_services functions."""

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
        locations = [EconomicDataLocationChoices.FR.value]
        result = get_economic_recap_data(locations)
        assert result == {
            EconomicDataCategoryChoices.CONFIDENCE: [
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE,
                    "location": EconomicDataLocationChoices.FR,
                    "name": "Test Indicator",
                    "current": 110.0,
                    "previous": 100.0,
                    "change": 10.0,
                    "period": self.second_economic_data.get_period_display(),
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
            EconomicDataLocationChoices.FR.value,
            EconomicDataLocationChoices.US.value,
        ]
        result = get_economic_recap_data(locations)
        assert result == {
            EconomicDataCategoryChoices.CONFIDENCE.value: [
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.FR.value,
                    "name": "Test Indicator",
                    "current": 110.0,
                    "previous": 100.0,
                    "change": 10.0,
                    "period": self.second_economic_data.get_period_display(),
                },
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "change": None,
                    "current": None,
                    "location": EconomicDataLocationChoices.US.value,
                    "name": "Test Indicator",
                    "period": None,
                    "previous": None,
                },
            ],
            EconomicDataCategoryChoices.GROWTH.value: [
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "change": None,
                    "current": None,
                    "location": EconomicDataLocationChoices.FR.value,
                    "name": "US Indicator",
                    "period": None,
                    "previous": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.US.value,
                    "name": "US Indicator",
                    "current": 200.0,
                    "previous": None,
                    "change": None,
                    "period": self.first_economic_data.get_period_display(),
                },
            ],
        }

    def test_get_economic_recap_data_no_location(self):
        """
        GIVEN existing economic data
        WHEN getting economic recap data for a location that has no data
        THEN a default economic data based on existing data is returned
        """
        locations = [EconomicDataLocationChoices.JP.value]
        result = get_economic_recap_data(locations)
        assert result == {
            EconomicDataCategoryChoices.CONFIDENCE.value: [
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.JP.value,
                    "name": "Test Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                }
            ]
        }

    @freeze_time("2024-11-01")
    @patch(
        "data_visualization.services.economic_recap_services._get_upcoming_events_from_publication_schedules"
    )
    @patch(
        "data_visualization.services.economic_recap_services._get_upcoming_central_bank_events"
    )
    @patch(
        "data_visualization.services.economic_recap_services._get_upcoming_holidays_events"
    )
    def test_get_economic_recap_upcoming_events_success(
        self, mock_holidays, mock_cb, mock_publications
    ):
        """
        GIVEN upcoming events from different sources
        WHEN getting economic recap upcoming events
        THEN all events are merged and grouped by date
        """
        event_date = datetime.now(timezone.utc) + timedelta(days=1)
        mock_publications.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": event_date,
                    "time_str": "10:00",
                }
            ]
        }
        mock_cb.return_value = {}
        mock_holidays.return_value = {}

        result = get_economic_recap_upcoming_events()
        assert result == [
            {
                "date": "2024-11-02",
                "date_display": "2024-11-02",
                "events": [
                    {
                        "name": "Test Indicator",
                        "location": "France",
                        "publication_date": event_date,
                        "time_str": "10:00",
                    }
                ],
            }
        ]

    @freeze_time("2024-11-01")
    @patch(
        "data_visualization.services.economic_recap_services._get_upcoming_events_from_publication_schedules"
    )
    @patch(
        "data_visualization.services.economic_recap_services._get_upcoming_central_bank_events"
    )
    @patch(
        "data_visualization.services.economic_recap_services._get_upcoming_holidays_events"
    )
    def test_get_economic_recap_upcoming_events_merged(
        self, mock_holidays, mock_cb, mock_publications
    ):
        """
        GIVEN upcoming events from multiple sources on the same date
        WHEN getting economic recap upcoming events
        THEN events are merged correctly
        """
        event_date = datetime.now(timezone.utc) + timedelta(days=1)
        holiday_date = datetime.now(timezone.utc) + timedelta(days=2)
        mock_publications.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": event_date,
                    "time_str": "10:00",
                }
            ]
        }
        mock_cb.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "ECB Rates Decision",
                    "location": "Europe",
                    "publication_date": event_date,
                    "time_str": "14:00",
                }
            ]
        }
        mock_holidays.return_value = {
            holiday_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Holiday",
                    "location": "Japan",
                    "publication_date": holiday_date,
                    "time_str": "HOLIDAYS",
                }
            ]
        }

        result = get_economic_recap_upcoming_events()
        assert result == [
            {
                "date": "2024-11-02",
                "date_display": "2024-11-02",
                "events": [
                    {
                        "name": "Test Indicator",
                        "location": "France",
                        "publication_date": event_date,
                        "time_str": "10:00",
                    },
                    {
                        "name": "ECB Rates Decision",
                        "location": "Europe",
                        "publication_date": event_date,
                        "time_str": "14:00",
                    },
                ],
            },
            {
                "date": "2024-11-03",
                "date_display": "2024-11-03",
                "events": [
                    {
                        "name": "Holiday",
                        "location": "Japan",
                        "publication_date": holiday_date,
                        "time_str": "HOLIDAYS",
                    }
                ],
            },
        ]

    @freeze_time("2024-11-01")
    def test_get_economic_recap_upcoming_events_from_publication_schedules(self):
        """
        GIVEN publication schedules with upcoming dates
        WHEN getting upcoming events from publication schedules
        THEN events are returned correctly
        """
        future_date = datetime.combine(date.today(), time(10, 30, 0)).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=5)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=future_date,
            next_publication_date=future_date + timedelta(days=30),
        )

        result = _get_upcoming_events_from_publication_schedules(date.today())
        assert result == {
            "2024-11-06": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": datetime(
                        2024, 11, 6, 10, 30, 0, tzinfo=timezone.utc
                    ),
                    "time_str": "10:30",
                }
            ]
        }

    @freeze_time("2024-11-01")
    def test_get_upcoming_holidays_events(self):
        """
        GIVEN upcoming holidays
        WHEN getting upcoming holidays events
        THEN events are returned correctly
        """
        HolidayModel.objects.create(
            id=1,
            name="Holiday",
            date=django_timezone.now() + timedelta(days=2),
            location=LocationChoices.JP,
        )
        result = _get_upcoming_holidays_events(date.today())
        assert result == {
            "2024-11-03": [
                {
                    "name": "Holiday",
                    "location": "Japan",
                    "publication_date": datetime(
                        2024, 11, 3, 0, 0, 0, tzinfo=timezone.utc
                    ),
                    "time_str": "HOLIDAYS",
                }
            ]
        }
