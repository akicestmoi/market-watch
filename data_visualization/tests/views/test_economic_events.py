"""Tests for economic events visualization views."""

from django.test import Client, TestCase
from freezegun import freeze_time


@freeze_time("2025-12-16")
class TestEconomicEventsView(TestCase):
    """Test cases for economic_events_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/economic-events/"

    def test_economic_events_view_success(self):
        """
        GIVEN the economic events page
        WHEN accessing the view
        THEN upcoming weeks are in context and the page renders
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        assert "upcoming_weeks" in response.context
        upcoming_weeks = response.context.get("upcoming_weeks")
        assert isinstance(upcoming_weeks, list)
        assert len(upcoming_weeks) >= 2
        assert len(upcoming_weeks) % 2 == 0
        assert upcoming_weeks[0].get("is_current_week") is True
        assert len(upcoming_weeks[0]["days"]) == 5
        today_slots = [
            day for week in upcoming_weeks for day in week["days"] if day.get("is_today")
        ]
        assert len(today_slots) == 1
        assert today_slots[0]["date"] == "2025-12-16"
        assert b"Upcoming Economic Events" in response.content
        assert b"upcoming-week-pair" in response.content
        assert b"is-today" in response.content
        assert b"Today" in response.content
        assert b"No events" in response.content
        assert b"location_flags." in response.content
        assert b"economic_events." in response.content
