"""Tests for economic events visualization services."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from freezegun import freeze_time

from data_visualization.services.economic_events import (
    _get_upcoming_events,
    _get_upcoming_events_from_publication_schedules,
    _get_upcoming_holidays_events,
    _UpcomingEvent,
    _UpcomingEventGroup,
    _UpcomingWeekGroup,
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
        this_week_event = _UpcomingEvent(
            name="This Week",
            location="France",
            publication_date=datetime(2025, 12, 16, 10, 0, 0, tzinfo=timezone.utc),
            time_str="10:00",
            is_holiday=False,
        )
        next_week_event = _UpcomingEvent(
            name="Next Week",
            location="United States",
            publication_date=datetime(2025, 12, 22, 14, 0, 0, tzinfo=timezone.utc),
            time_str="14:00",
            is_holiday=False,
        )
        upcoming: list[_UpcomingEventGroup] = [
            _UpcomingEventGroup(
                date="2025-12-16",
                date_display="Tuesday 16 December 2025",
                events=[this_week_event],
            ),
            _UpcomingEventGroup(
                date="2025-12-22",
                date_display="Monday 22 December 2025",
                events=[next_week_event],
            ),
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert result == [
            _UpcomingWeekGroup(
                week_start="2025-12-15",
                week_label="15 Dec 2025 – 19 Dec 2025",
                is_current_week=True,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-15",
                        date_display="Monday 15 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-16",
                        date_display="Tuesday 16 December 2025",
                        events=[this_week_event],
                        is_today=True,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-17",
                        date_display="Wednesday 17 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-18",
                        date_display="Thursday 18 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-19",
                        date_display="Friday 19 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
            _UpcomingWeekGroup(
                week_start="2025-12-22",
                week_label="22 Dec 2025 – 26 Dec 2025",
                is_current_week=False,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-22",
                        date_display="Monday 22 December 2025",
                        events=[next_week_event],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-23",
                        date_display="Tuesday 23 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-24",
                        date_display="Wednesday 24 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-25",
                        date_display="Thursday 25 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-26",
                        date_display="Friday 26 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
        ]

    def test_group_upcoming_events_focus_week_after_friday(self):
        """
        GIVEN today is Saturday and only next-week events exist
        WHEN grouping by week
        THEN the focus week is next Monday–Friday and the following week is included
        """
        today = date(2025, 12, 20)  # Saturday
        next_week_event = _UpcomingEvent(
            name="Next Week",
            location="France",
            publication_date=datetime(2025, 12, 22, 10, 0, 0, tzinfo=timezone.utc),
            time_str="10:00",
            is_holiday=False,
        )
        upcoming: list[_UpcomingEventGroup] = [
            _UpcomingEventGroup(
                date="2025-12-22",
                date_display="Monday 22 December 2025",
                events=[next_week_event],
            ),
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert result == [
            _UpcomingWeekGroup(
                week_start="2025-12-22",
                week_label="22 Dec 2025 – 26 Dec 2025",
                is_current_week=True,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-22",
                        date_display="Monday 22 December 2025",
                        events=[next_week_event],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-23",
                        date_display="Tuesday 23 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-24",
                        date_display="Wednesday 24 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-25",
                        date_display="Thursday 25 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-26",
                        date_display="Friday 26 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
            _UpcomingWeekGroup(
                week_start="2025-12-29",
                week_label="29 Dec 2025 – 02 Jan 2026",
                is_current_week=False,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-29",
                        date_display="Monday 29 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-30",
                        date_display="Tuesday 30 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-31",
                        date_display="Wednesday 31 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-01",
                        date_display="Thursday 1 January 2026",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-02",
                        date_display="Friday 2 January 2026",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
        ]

    def test_group_upcoming_events_includes_empty_weekdays(self):
        """
        GIVEN events on only one weekday
        WHEN grouping by week
        THEN Mon–Fri slots are all present and empty days have no events
        """
        today = date(2025, 12, 16)
        wednesday_event = _UpcomingEvent(
            name="Only Wednesday",
            location="France",
            publication_date=datetime(2025, 12, 17, 10, 0, 0, tzinfo=timezone.utc),
            time_str="10:00",
            is_holiday=False,
        )
        upcoming: list[_UpcomingEventGroup] = [
            _UpcomingEventGroup(
                date="2025-12-17",
                date_display="Wednesday 17 December 2025",
                events=[wednesday_event],
            ),
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert result == [
            _UpcomingWeekGroup(
                week_start="2025-12-15",
                week_label="15 Dec 2025 – 19 Dec 2025",
                is_current_week=True,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-15",
                        date_display="Monday 15 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-16",
                        date_display="Tuesday 16 December 2025",
                        events=[],
                        is_today=True,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-17",
                        date_display="Wednesday 17 December 2025",
                        events=[wednesday_event],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-18",
                        date_display="Thursday 18 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-19",
                        date_display="Friday 19 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
            _UpcomingWeekGroup(
                week_start="2025-12-22",
                week_label="22 Dec 2025 – 26 Dec 2025",
                is_current_week=False,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-22",
                        date_display="Monday 22 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-23",
                        date_display="Tuesday 23 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-24",
                        date_display="Wednesday 24 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-25",
                        date_display="Thursday 25 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-26",
                        date_display="Friday 26 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
        ]

    def test_group_upcoming_events_extends_and_pads_even_weeks(self):
        """
        GIVEN events three weeks out
        WHEN grouping by week
        THEN weeks run through that week and the count is even for paging
        """
        today = date(2025, 12, 16)
        far_event = _UpcomingEvent(
            name="Far Ahead",
            location="France",
            publication_date=datetime(2026, 1, 5, 10, 0, 0, tzinfo=timezone.utc),
            time_str="10:00",
            is_holiday=False,
        )
        upcoming: list[_UpcomingEventGroup] = [
            _UpcomingEventGroup(
                date="2026-01-05",
                date_display="Monday 5 January 2026",
                events=[far_event],
            ),
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert result == [
            _UpcomingWeekGroup(
                week_start="2025-12-15",
                week_label="15 Dec 2025 – 19 Dec 2025",
                is_current_week=True,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-15",
                        date_display="Monday 15 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-16",
                        date_display="Tuesday 16 December 2025",
                        events=[],
                        is_today=True,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-17",
                        date_display="Wednesday 17 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-18",
                        date_display="Thursday 18 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-19",
                        date_display="Friday 19 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
            _UpcomingWeekGroup(
                week_start="2025-12-22",
                week_label="22 Dec 2025 – 26 Dec 2025",
                is_current_week=False,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-22",
                        date_display="Monday 22 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-23",
                        date_display="Tuesday 23 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-24",
                        date_display="Wednesday 24 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-25",
                        date_display="Thursday 25 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-26",
                        date_display="Friday 26 December 2025",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
            _UpcomingWeekGroup(
                week_start="2025-12-29",
                week_label="29 Dec 2025 – 02 Jan 2026",
                is_current_week=False,
                days=[
                    _UpcomingEventGroup(
                        date="2025-12-29",
                        date_display="Monday 29 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-30",
                        date_display="Tuesday 30 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2025-12-31",
                        date_display="Wednesday 31 December 2025",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-01",
                        date_display="Thursday 1 January 2026",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-02",
                        date_display="Friday 2 January 2026",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
            _UpcomingWeekGroup(
                week_start="2026-01-05",
                week_label="05 Jan 2026 – 09 Jan 2026",
                is_current_week=False,
                days=[
                    _UpcomingEventGroup(
                        date="2026-01-05",
                        date_display="Monday 5 January 2026",
                        events=[far_event],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-06",
                        date_display="Tuesday 6 January 2026",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-07",
                        date_display="Wednesday 7 January 2026",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-08",
                        date_display="Thursday 8 January 2026",
                        events=[],
                        is_today=False,
                    ),
                    _UpcomingEventGroup(
                        date="2026-01-09",
                        date_display="Friday 9 January 2026",
                        events=[],
                        is_today=False,
                    ),
                ],
            ),
        ]


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
