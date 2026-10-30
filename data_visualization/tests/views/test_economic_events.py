"""Tests for economic events visualization views."""

from django.test import Client, TestCase
from freezegun import freeze_time

from core.testing import read_file_content
from data_visualization.services.economic_events import (
    _UpcomingEventGroup,
    _UpcomingWeekGroup,
)

_EXPECTED_HTML = read_file_content(
    "data_visualization/tests/mock_web_data/economic_events/empty_weeks.html"
)


@freeze_time("2025-12-16")
class TestEconomicEventsView(TestCase):
    """Test cases for economic_events_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/economic-events/"

    def test_economic_events_view_success(self):
        """
        GIVEN the economic events page with no scheduled events
        WHEN accessing the view
        THEN empty focus + next weeks are in context and the page renders
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        assert response.context["upcoming_weeks"] == [
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
        ]
        assert response.content == _EXPECTED_HTML
