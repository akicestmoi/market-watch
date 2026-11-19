"""Tests for shared calendar helpers in 'core.services.calendar'."""

from datetime import date, datetime, timezone

from django.test import TestCase
from freezegun import freeze_time

from core.services.calendar import (
    convert_local_wall_time_to_utc,
    convert_to_display_timezone,
    get_first_business_day_of_month,
    get_local_today,
    get_market_watch_as_of_date,
    get_previous_business_day,
    get_source_timezone,
)


class TestSourceTimezone(TestCase):
    """Test cases for source local-time → UTC helpers."""

    def test_get_source_timezone_us_is_new_york(self):
        """
        GIVEN the US location code
        WHEN get_source_timezone is called
        THEN America/New_York is returned
        """
        assert str(get_source_timezone("US")) == "America/New_York"

    def test_convert_local_wall_time_to_utc_fomc_winter(self):
        """
        GIVEN a 14:00 America/New_York local announcement time in January
        WHEN converting to UTC
        THEN 19:00 UTC (EST) is returned
        """
        utc_datetime = convert_local_wall_time_to_utc(
            2025,
            1,
            29,
            14,
            source_timezone="America/New_York",
        )
        assert utc_datetime == datetime(2025, 1, 29, 19, 0, 0, tzinfo=timezone.utc)

    def test_convert_local_wall_time_to_utc_fomc_summer(self):
        """
        GIVEN a 14:00 America/New_York local announcement time in June
        WHEN converting to UTC
        THEN 18:00 UTC (EDT) is returned
        """
        utc_datetime = convert_local_wall_time_to_utc(
            2025,
            6,
            18,
            14,
            source_timezone="America/New_York",
        )
        assert utc_datetime == datetime(2025, 6, 18, 18, 0, 0, tzinfo=timezone.utc)

    def test_fomc_new_york_displays_as_paris_20_00(self):
        """
        GIVEN an FOMC announcement stored from 14:00 New York time
        WHEN converting for display
        THEN Paris shows 20:00 in both winter and summer
        """
        winter_utc = convert_local_wall_time_to_utc(
            2025,
            1,
            29,
            14,
            source_timezone="America/New_York",
        )
        summer_utc = convert_local_wall_time_to_utc(
            2025,
            6,
            18,
            14,
            source_timezone="America/New_York",
        )
        assert convert_to_display_timezone(winter_utc).strftime("%H:%M") == "20:00"
        assert convert_to_display_timezone(summer_utc).strftime("%H:%M") == "20:00"


class TestDisplayTimezone(TestCase):
    """Test cases for display timezone helpers."""

    def test_convert_to_display_timezone_paris_winter(self):
        """
        GIVEN a UTC datetime in winter
        WHEN converting for display
        THEN Europe/Paris CET (+01:00) is applied
        """
        utc_dt = datetime(2025, 12, 5, 7, 45, 0, tzinfo=timezone.utc)
        paris = convert_to_display_timezone(utc_dt)
        assert paris.strftime("%H:%M") == "08:45"
        assert str(paris.tzinfo) == "Europe/Paris"


class TestMarketWatchAsOfDate(TestCase):
    """Project T-1 business-day perspective helpers."""

    @freeze_time("2026-10-30 16:00:00")
    def test_get_market_watch_as_of_date_is_previous_business_day(self):
        """
        GIVEN a Friday system calendar day
        WHEN resolving the Market Watch as-of date
        THEN the previous business day (Thursday) is returned
        """
        assert get_local_today() == date(2026, 10, 30)
        assert get_market_watch_as_of_date() == date(2026, 10, 29)
        assert get_previous_business_day(date(2026, 10, 30)) == date(2026, 10, 29)

    @freeze_time("2026-10-26 12:00:00")
    def test_get_market_watch_as_of_date_skips_weekend(self):
        """
        GIVEN a Monday
        WHEN resolving the Market Watch as-of date
        THEN Friday (not Sunday) is returned
        """
        assert get_market_watch_as_of_date() == date(2026, 10, 23)

    def test_get_first_business_day_of_month_rolls_weekend_start(self):
        """
        GIVEN a month that begins on Saturday
        WHEN resolving the first business day
        THEN the following Monday is returned
        """
        # November 2026 starts on Sunday; first Mon–Fri is Monday 2nd.
        assert get_first_business_day_of_month(date(2026, 11, 15)) == date(2026, 11, 2)

    def test_get_first_business_day_of_month_keeps_weekday_start(self):
        """
        GIVEN a month that begins on a weekday
        WHEN resolving the first business day
        THEN the 1st is returned
        """
        # December 2026 starts on Tuesday.
        assert get_first_business_day_of_month(date(2026, 12, 20)) == date(2026, 12, 1)
