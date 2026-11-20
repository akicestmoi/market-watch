"""Tests for economic events visualization services."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from freezegun import freeze_time

from data_visualization.services.economic_events import (
    _get_upcoming_earnings_events,
    _get_upcoming_events,
    _get_upcoming_events_from_publication_schedules,
    _get_upcoming_events_window_end,
    _get_upcoming_holidays_events,
    _sort_day_events,
    _UpcomingEvent,
    _UpcomingEventGroup,
    _UpcomingEventType,
    _UpcomingWeekGroup,
    group_upcoming_events_by_week,
)
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
from economic_overview.models.publication import PublicationScheduleModel
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel
from market_overview.models.market_prices import HolidayModel


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
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        next_week_event = _UpcomingEvent(
            name="Next Week",
            location="United States",
            publication_date=datetime(2025, 12, 22, 14, 0, 0, tzinfo=timezone.utc),
            time_str="14:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
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
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
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
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
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
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
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

    def test_group_upcoming_events_caps_at_eight_weeks(self):
        """
        GIVEN an event more than eight weeks after the focus Monday
        WHEN grouping by week
        THEN at most eight weeks are returned and the far event is omitted
        """
        today = date(2025, 12, 16)
        far_event = _UpcomingEvent(
            name="Too Far",
            location="France",
            publication_date=datetime(2026, 2, 16, 10, 0, 0, tzinfo=timezone.utc),
            time_str="10:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        upcoming: list[_UpcomingEventGroup] = [
            _UpcomingEventGroup(
                date="2026-02-16",
                date_display="Monday 16 February 2026",
                events=[far_event],
            ),
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert len(result) == 2
        assert result[0]["week_start"] == "2025-12-15"
        assert result[1]["week_start"] == "2025-12-22"
        assert all(not day["events"] for week in result for day in week["days"])


@freeze_time("2025-12-16")
class TestUpcomingEvents(TestCase):
    """Tests for upcoming event aggregation."""

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
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "",
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
                        "event_type": _UpcomingEventType.ECONOMIC,
                        "period": "",
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
        end_date = _get_upcoming_events_window_end(today)
        future_date = datetime.combine(today, time(10, 30, 0)).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=5)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=future_date,
            next_publication_date=future_date + timedelta(days=30),
        )

        result = _get_upcoming_events_from_publication_schedules(today, end_date)
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
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "",
                }
            ]
        }

    def test_get_upcoming_events_from_publication_schedules_includes_previous(self):
        """
        GIVEN a schedule whose just-released value is only on previous_publication_date
        WHEN listing events from the focus-week Monday
        THEN that previous slot appears on its display day
        """
        week_monday = date(2025, 12, 15)
        end_date = _get_upcoming_events_window_end(week_monday)
        previous_publication = datetime(2025, 12, 16, 9, 0, 0, tzinfo=timezone.utc)
        next_publication = datetime(2026, 1, 16, 9, 0, 0, tzinfo=timezone.utc)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=previous_publication,
            current_publication_date=next_publication,
            next_publication_date=next_publication + timedelta(days=30),
        )

        result = _get_upcoming_events_from_publication_schedules(week_monday, end_date)
        assert result == {
            "2025-12-16": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": previous_publication,
                    "time_str": "10:00",
                    "is_holiday": False,
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "",
                }
            ],
            "2026-01-16": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": next_publication,
                    "time_str": "10:00",
                    "is_holiday": False,
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "",
                }
            ],
        }

    def test_get_upcoming_events_from_publication_schedules_covered_period(self):
        """
        GIVEN quarterly data through Q1 and a later publication slot
        WHEN listing upcoming publication events
        THEN the event is labeled with Q2 (next period after the latest print)
        """
        today = date(2025, 12, 16)
        end_date = _get_upcoming_events_window_end(today)
        self.indicator.frequency = EconomicPublicationFrequencyChoices.QUARTERLY
        self.indicator.save(update_fields=["frequency"])
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=date(2025, 1, 1),
            data_value=1.0,
        )
        future_date = datetime(2025, 12, 21, 10, 30, 0, tzinfo=timezone.utc)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=future_date,
            next_publication_date=future_date + timedelta(days=90),
        )

        result = _get_upcoming_events_from_publication_schedules(today, end_date)
        assert result == {
            "2025-12-21": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": future_date,
                    "time_str": "11:30",
                    "is_holiday": False,
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "25Q2",
                }
            ]
        }

    @patch("data_visualization.services.economic_events.get_local_today")
    def test_get_upcoming_events_starts_from_focus_week_monday(
        self, mock_get_local_today
    ):
        """
        GIVEN today is mid-week and a release fell earlier in the same week
        WHEN building upcoming events for the Economic Events page
        THEN that earlier-week release is included (not only today+)
        """
        mock_get_local_today.return_value = date(2025, 12, 18)  # Thursday
        monday_release = datetime(2025, 12, 15, 9, 0, 0, tzinfo=timezone.utc)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=monday_release,
            current_publication_date=datetime(
                2026, 1, 15, 9, 0, 0, tzinfo=timezone.utc
            ),
            next_publication_date=datetime(2026, 2, 15, 9, 0, 0, tzinfo=timezone.utc),
        )

        result = _get_upcoming_events()
        monday_group = next(group for group in result if group["date"] == "2025-12-15")
        assert monday_group == {
            "date": "2025-12-15",
            "date_display": "Monday 15 December 2025",
            "events": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": monday_release,
                    "time_str": "10:00",
                    "is_holiday": False,
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "",
                }
            ],
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
        end_date = _get_upcoming_events_window_end(today)
        result = _get_upcoming_holidays_events(today, end_date)
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
                    "event_type": _UpcomingEventType.HOLIDAY,
                    "period": "",
                }
            ]
        }

    def test_get_upcoming_events_from_publication_schedules_excludes_de_es_it(self):
        """
        GIVEN DE / ES / IT publication schedules alongside a FR schedule
        WHEN getting upcoming events from publication schedules
        THEN only the FR event is returned
        """
        today = date(2025, 12, 16)
        end_date = _get_upcoming_events_window_end(today)
        future_date = datetime.combine(today, time(10, 30, 0)).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=5)
        for location, indicator_id in (
            (EconomicDataLocationChoices.DE, 101),
            (EconomicDataLocationChoices.ES, 102),
            (EconomicDataLocationChoices.IT, 103),
        ):
            excluded_indicator = EconomicIndicatorInformationModel.objects.create(
                id=indicator_id,
                location=location,
                category=EconomicDataCategoryChoices.BUSINESS,
                subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
                series_label=f"{location.value} Indicator",
                full_name=f"{location.value} Indicator Name",
                technical_name=f"{location.value.lower()}_indicator",
                frequency=EconomicPublicationFrequencyChoices.MONTHLY,
                source=EconomicDataSourceChoices.EUROSTAT,
                ticker=f"ex_{location.value.lower()}",
            )
            PublicationScheduleModel.objects.create(
                indicator=excluded_indicator,
                current_publication_date=future_date,
                next_publication_date=future_date + timedelta(days=30),
            )
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=future_date,
            next_publication_date=future_date + timedelta(days=30),
        )

        result = _get_upcoming_events_from_publication_schedules(today, end_date)
        assert result == {
            "2025-12-21": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": datetime(
                        2025, 12, 21, 10, 30, 0, tzinfo=timezone.utc
                    ),
                    "time_str": "11:30",
                    "is_holiday": False,
                    "event_type": _UpcomingEventType.ECONOMIC,
                    "period": "",
                }
            ]
        }


class TestSortDayEvents(TestCase):
    """Within-day Economic Events ordering."""

    def test_sort_day_events_by_time_then_country(self):
        """
        GIVEN same-day events with mixed times and countries plus a holiday
        WHEN sorting the day
        THEN holidays come first, then earlier times, then US → FR → JP → EU
        """
        shared_date = datetime(2025, 12, 16, 12, 0, 0, tzinfo=timezone.utc)
        holiday = _UpcomingEvent(
            name="Christmas",
            location="France",
            publication_date=shared_date,
            time_str="Holiday",
            is_holiday=True,
            event_type=_UpcomingEventType.HOLIDAY,
            period="",
        )
        late_us = _UpcomingEvent(
            name="US Late",
            location="United States",
            publication_date=shared_date,
            time_str="15:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        early_eu = _UpcomingEvent(
            name="EU Early",
            location="Europe",
            publication_date=shared_date,
            time_str="08:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        early_jp = _UpcomingEvent(
            name="JP Early",
            location="Japan",
            publication_date=shared_date,
            time_str="08:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        early_fr = _UpcomingEvent(
            name="FR Early",
            location="France",
            publication_date=shared_date,
            time_str="08:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        early_us = _UpcomingEvent(
            name="US Early",
            location="United States",
            publication_date=shared_date,
            time_str="08:00",
            is_holiday=False,
            event_type=_UpcomingEventType.ECONOMIC,
            period="",
        )
        assert _sort_day_events(
            [late_us, early_eu, holiday, early_jp, early_fr, early_us]
        ) == [
            holiday,
            early_us,
            early_fr,
            early_jp,
            early_eu,
            late_us,
        ]


class TestEarningsOnEconomicEvents(TestCase):
    """Test cases for earnings announcements on the Economic Events calendar."""

    def test_get_upcoming_earnings_events(self):
        """
        GIVEN a watchlist company with an upcoming announcement and no last report
        WHEN _get_upcoming_earnings_events is called
        THEN one Nvidia earnings event is returned with period end and '...'
        """
        EarningsWatchlistModel.objects.create(
            company="Nvidia",
            ticker="NVDA",
            equity_index=EquityIndexChoices.SPX.value,
            upcoming_announcement_datetime=datetime(
                2026, 11, 19, 21, 0, tzinfo=timezone.utc
            ),
            upcoming_reporting_period_end=date(2026, 10, 31),
            upcoming_eps_expected=1.0,
        )

        result = _get_upcoming_earnings_events(
            date(2026, 11, 16),
            date(2026, 11, 20),
        )

        assert result == {
            "2026-11-19": [
                _UpcomingEvent(
                    name="Nvidia earnings",
                    location="United States",
                    publication_date=datetime(2026, 11, 19, 21, 0, tzinfo=timezone.utc),
                    time_str="22:00",
                    is_holiday=False,
                    event_type=_UpcomingEventType.EARNINGS,
                    period="10.26 - ...",
                )
            ]
        }

    def test_get_upcoming_earnings_events_period_window(self):
        """
        GIVEN upcoming and last reported period ends on a watchlist company
        WHEN _get_upcoming_earnings_events is called
        THEN the period label is end month.year - start month.year
        """
        EarningsWatchlistModel.objects.create(
            company="Nvidia",
            ticker="NVDA",
            equity_index=EquityIndexChoices.SPX.value,
            upcoming_announcement_datetime=datetime(
                2026, 11, 19, 21, 0, tzinfo=timezone.utc
            ),
            upcoming_reporting_period_end=date(2026, 10, 31),
            upcoming_eps_expected=1.0,
            current_reporting_period_end=date(2026, 7, 31),
        )

        result = _get_upcoming_earnings_events(
            date(2026, 11, 16),
            date(2026, 11, 20),
        )

        assert result == {
            "2026-11-19": [
                _UpcomingEvent(
                    name="Nvidia earnings",
                    location="United States",
                    publication_date=datetime(2026, 11, 19, 21, 0, tzinfo=timezone.utc),
                    time_str="22:00",
                    is_holiday=False,
                    event_type=_UpcomingEventType.EARNINGS,
                    period="10.26 - 7.26",
                )
            ]
        }
