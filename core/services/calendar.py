"""Shared timezone, display-clock, and business-day helpers."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone as dj_timezone
from pandas.tseries.offsets import BDay

# Source local-time zones for location codes (economic / market location choices).
# Naive publish times from a source are interpreted in this zone, then stored as UTC.
SOURCE_TIMEZONE_BY_LOCATION_CODE: dict[str, str] = {
    "US": "America/New_York",
    "EU": "Europe/Berlin",
    "FR": "Europe/Paris",
    "JP": "Asia/Tokyo",
    "DE": "Europe/Berlin",
    "ES": "Europe/Madrid",
    "IT": "Europe/Rome",
}


def get_source_timezone(location_code: str) -> ZoneInfo:
    """Return the source local-time zone for a location code (e.g. US → New York)."""
    timezone_name = SOURCE_TIMEZONE_BY_LOCATION_CODE.get(location_code)
    if timezone_name is None:
        raise ValueError(f"No source timezone mapped for location {location_code!r}")
    return ZoneInfo(timezone_name)


def convert_local_wall_time_to_utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    *,
    source_timezone: str | ZoneInfo,
) -> datetime:
    """Interpret a source-local civil time and return the matching UTC instant.

    Use at ingest when a calendar publishes a local announcement time in a known
    zone (e.g. FOMC 14:00 America/New_York) but storage must be UTC-aware.
    """
    source_zone = (
        ZoneInfo(source_timezone)
        if isinstance(source_timezone, str)
        else source_timezone
    )
    local_datetime = datetime(year, month, day, hour, minute, tzinfo=source_zone)
    return local_datetime.astimezone(timezone.utc)


def _get_display_timezone() -> ZoneInfo:
    """Return the display zone ('TIME_ZONE', Europe/Paris).

    Use when you need the zone object itself. For a datetime or calendar date,
    prefer 'convert_to_display_timezone' / 'get_local_today'.
    """
    return ZoneInfo(settings.TIME_ZONE)


def convert_to_display_timezone(value: datetime) -> datetime:
    """Convert a datetime instant to Europe/Paris (keeps the same moment).

    Use for UI clocks ('strftime' times/date chips). Naive values are assumed
    UTC. Prefer storing UTC-aware datetimes; this is a display-edge helper only.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_get_display_timezone())


def get_local_today() -> date:
    """Return today's calendar date in Europe/Paris (no clock time).

    Use for filters and week focus ('DateField' / date comparisons). Distinct
    from 'convert_to_display_timezone', which returns a full datetime.
    """
    return dj_timezone.localdate()


def get_previous_business_day(as_of: date) -> date:
    """Return the previous weekday on the business calendar before 'as_of'."""
    return (as_of - BDay(1)).date()


def get_first_business_day_of_month(as_of: date) -> date:
    """Return the first Mon–Fri calendar day of the month containing 'as_of'."""
    first_of_month = as_of.replace(day=1)
    return (first_of_month + BDay(0)).date()


def get_market_watch_as_of_date() -> date:
    """Return the project's default data perspective: Paris T-1 business day.

    Market Watch analyses, recaps, and calendars are at most previous-business-day
    (never live 'today'). Prefer this over 'date.today() - BDay(1)'.
    """
    return get_previous_business_day(get_local_today())
