"""Tests for economic events visualization services."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from freezegun import freeze_time

from data_visualization.services.economic_events import (
    UpcomingEventGroup,
    _get_upcoming_events,
    _get_upcoming_events_from_publication_schedules,
    _get_upcoming_holidays_events,
    group_upcoming_events_by_week,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from market_overview.models import HolidayModel, LocationChoices


class TestGroupUpcomingEventsByWeek(TestCase):
    """Tests for ISO-week paging of upcoming events (two weeks per page)."""

    def test_group_upcoming_events_by_week(self):
        """
        GIVEN day-level upcoming events spanning the focus and next weeks
        WHEN grouping by week
        THEN those weeks are returned with all Mon–Fri day slots
        """
        today = date(2025, 12, 16)  # Tuesday; ISO week starts 2025-12-15
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2025-12-16",
                "date_display": "Tuesday 16 December 2025",
                "events": [
                    {
                        "name": "This Week",
                        "location": "France",
                        "publication_date": datetime(
                            2025, 12, 16, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                        "is_holiday": False,
                    }
                ],
            },
            {
                "date": "2025-12-22",
                "date_display": "Monday 22 December 2025",
                "events": [
                    {
                        "name": "Next Week",
                        "location": "United States",
                        "publication_date": datetime(
                            2025, 12, 22, 14, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "14:00",
                        "is_holiday": False,
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert len(result) == 2
        assert result[0]["week_start"] == "2025-12-15"
        assert result[0]["is_current_week"] is True
        assert len(result[0]["days"]) == 5
        assert result[0]["days"][0]["date"] == "2025-12-15"
        assert result[0]["days"][0]["events"] == []
        assert result[0]["days"][0]["is_today"] is False
        assert result[0]["days"][1]["date"] == "2025-12-16"
        assert result[0]["days"][1]["is_today"] is True
        assert result[0]["days"][1]["events"][0]["name"] == "This Week"
        assert result[1]["week_start"] == "2025-12-22"
        assert result[1]["days"][0]["date"] == "2025-12-22"
        assert result[1]["days"][0]["is_today"] is False
        assert result[1]["days"][0]["events"][0]["name"] == "Next Week"

    def test_group_upcoming_events_focus_week_after_friday(self):
        """
        GIVEN today is Saturday and only next-week events exist
        WHEN grouping by week
        THEN the focus week is next Monday–Friday and the following week is included
        """
        today = date(2025, 12, 20)  # Saturday
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2025-12-22",
                "date_display": "Monday 22 December 2025",
                "events": [
                    {
                        "name": "Next Week",
                        "location": "France",
                        "publication_date": datetime(
                            2025, 12, 22, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                        "is_holiday": False,
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert len(result) == 2
        assert result[0]["week_start"] == "2025-12-22"
        assert result[0]["is_current_week"] is True
        assert result[0]["days"][0]["events"][0]["name"] == "Next Week"
        assert all(day["is_today"] is False for week in result for day in week["days"])
        assert result[1]["week_start"] == "2025-12-29"
        assert all(day["events"] == [] for day in result[1]["days"])

    def test_group_upcoming_events_includes_empty_weekdays(self):
        """
        GIVEN events on only one weekday
        WHEN grouping by week
        THEN Mon–Fri slots are all present and empty days have no events
        """
        today = date(2025, 12, 16)
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2025-12-17",
                "date_display": "Wednesday 17 December 2025",
                "events": [
                    {
                        "name": "Only Wednesday",
                        "location": "France",
                        "publication_date": datetime(
                            2025, 12, 17, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                        "is_holiday": False,
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert len(result[0]["days"]) == 5
        assert [day["date"] for day in result[0]["days"]] == [
            "2025-12-15",
            "2025-12-16",
            "2025-12-17",
            "2025-12-18",
            "2025-12-19",
        ]
        assert result[0]["days"][2]["events"][0]["name"] == "Only Wednesday"
        assert result[0]["days"][0]["events"] == []

    def test_group_upcoming_events_extends_and_pads_even_weeks(self):
        """
        GIVEN events three weeks out
        WHEN grouping by week
        THEN weeks run through that week and the count is even for paging
        """
        today = date(2025, 12, 16)
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2026-01-05",
                "date_display": "Monday 5 January 2026",
                "events": [
                    {
                        "name": "Far Ahead",
                        "location": "France",
                        "publication_date": datetime(
                            2026, 1, 5, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                        "is_holiday": False,
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert len(result) % 2 == 0
        assert result[0]["week_start"] == "2025-12-15"
        assert any(week["week_start"] == "2026-01-05" for week in result)
        far_week = next(week for week in result if week["week_start"] == "2026-01-05")
        assert far_week["days"][0]["events"][0]["name"] == "Far Ahead"


@freeze_time("2025-12-16")
class TestUpcomingEvents(TestCase):
    """Tests for upcoming event aggregation."""

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

    @patch(
        "data_visualization.services.economic_events._get_upcoming_events_from_publication_schedules"
    )
    @patch(
        "data_visualization.services.economic_events._get_upcoming_central_bank_events"
    )
    @patch("data_visualization.services.economic_events._get_upcoming_holidays_events")
    def test_get_upcoming_events_success(
        self, mock_holidays, mock_cb, mock_publications
    ):
        """
        GIVEN upcoming events from different sources
        WHEN getting upcoming events
        THEN all events are merged and grouped by date with full day labels
        """
        event_date = datetime.now(timezone.utc) + timedelta(days=1)
        mock_publications.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": event_date,
                    "time_str": "10:00",
                    "is_holiday": False,
                }
            ]
        }
        mock_cb.return_value = {}
        mock_holidays.return_value = {}

        result = _get_upcoming_events()
        assert result == [
            {
                "date": "2025-12-17",
                "date_display": "Wednesday 17 December 2025",
                "events": [
                    {
                        "name": "Test Indicator",
                        "location": "France",
                        "publication_date": event_date,
                        "time_str": "10:00",
                        "is_holiday": False,
                    }
                ],
            }
        ]

    def test_get_upcoming_events_from_publication_schedules(self):
        """
        GIVEN publication schedules with upcoming dates
        WHEN getting upcoming events from publication schedules
        THEN events are returned correctly without flag prefixes
        """
        today = date(2025, 12, 16)
        future_date = datetime.combine(today, time(10, 30, 0)).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=5)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=future_date,
            next_publication_date=future_date + timedelta(days=30),
        )

        result = _get_upcoming_events_from_publication_schedules(today)
        assert result == {
            "2025-12-21": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": datetime(
                        2025, 12, 21, 10, 30, 0, tzinfo=timezone.utc
                    ),
                    # Stored UTC 10:30 → Europe/Paris winter (CET) 11:30
                    "time_str": "11:30",
                    "is_holiday": False,
                }
            ]
        }

    def test_get_upcoming_holidays_events(self):
        """
        GIVEN upcoming holidays
        WHEN getting upcoming holidays events
        THEN events are returned correctly without flag prefixes
        """
        today = date(2025, 12, 16)
        HolidayModel.objects.create(
            id=1,
            name="Holiday",
            date=django_timezone.now() + timedelta(days=2),
            location=LocationChoices.JP,
        )
        result = _get_upcoming_holidays_events(today)
        assert result == {
            "2025-12-18": [
                {
                    "name": "Holiday",
                    "location": "Japan",
                    "publication_date": datetime(
                        2025, 12, 18, 0, 0, 0, tzinfo=timezone.utc
                    ),
                    "time_str": "Holiday",
                    "is_holiday": True,
                }
            ]
        }
