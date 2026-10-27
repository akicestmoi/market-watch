"""Build upcoming economic events for the Economic Events visualization page."""

from datetime import date, datetime, timedelta, timezone
from typing import TypedDict

import central_banks_overview.services.central_banks_meetings as central_banks_meetings
import market_overview.services.holidays as holidays
from central_banks_overview.models import CENTRAL_BANK_LOCATION_MAP, CentralBankChoices
from core.services import convert_to_display_timezone, get_local_today
from economic_overview.models import (
    EconomicDataLocationChoices,
    PublicationScheduleModel,
)
from market_overview.models import LocationChoices
from market_overview.services.holidays import HOLIDAY_COUNTRIES


class UpcomingEvent(TypedDict):
    """Single upcoming calendar event for the Economic Events page."""

    name: str
    location: str  # Display label (Choices.label), not the stored code
    publication_date: datetime
    time_str: str
    is_holiday: bool


class UpcomingEventGroup(TypedDict):
    """Upcoming events for a single calendar day."""

    date: str
    date_display: str
    events: list[UpcomingEvent]


def _format_day_label(day: date) -> str:
    """Full weekday label, e.g. ``Monday 26 October 2026``."""
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}"


def _get_upcoming_events_from_publication_schedules(
    start_date: date,
) -> dict[str, list[UpcomingEvent]]:
    """Get upcoming events from publication schedules."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    upcoming_schedules = (
        PublicationScheduleModel.objects.filter(
            current_publication_date__gte=start_date
        )
        .select_related("indicator")
        .order_by("next_publication_date")[:100]
    )

    for schedule in upcoming_schedules:
        publication_date = schedule.current_publication_date
        if not publication_date:
            continue

        display_dt = convert_to_display_timezone(publication_date)
        event = UpcomingEvent(
            name=schedule.indicator.type,
            location=str(
                EconomicDataLocationChoices(schedule.indicator.location).label
            ),
            publication_date=publication_date,
            time_str=display_dt.strftime("%H:%M"),
            is_holiday=False,
        )

        date_key = display_dt.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return events_by_date


def _get_upcoming_central_bank_events() -> dict[str, list[UpcomingEvent]]:
    """Get upcoming central bank events."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    for (
        central_bank_meeting_date
    ) in central_banks_meetings.get_central_bank_meeting_dates():
        central_bank = CentralBankChoices(central_bank_meeting_date["central_bank"])
        central_bank_location = CENTRAL_BANK_LOCATION_MAP[central_bank]
        meeting_date = central_bank_meeting_date["meeting_dates"][0]
        display_dt = convert_to_display_timezone(meeting_date)

        event = UpcomingEvent(
            name=f"{central_bank.label} Rates Decision",
            location=str(EconomicDataLocationChoices(central_bank_location).label),
            publication_date=meeting_date,
            time_str=display_dt.strftime("%H:%M"),
            is_holiday=False,
        )

        date_key = display_dt.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return events_by_date


def _get_upcoming_holidays_events(start_date: date) -> dict[str, list[UpcomingEvent]]:
    """Get upcoming holidays events."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    current_month = start_date.month
    current_year = start_date.year
    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year if current_month < 12 else current_year + 1

    for location in HOLIDAY_COUNTRIES:
        current_month_holidays = holidays.get_holidays(
            location=location,
            year=current_year,
            months=[current_month],
        )
        next_month_holidays = holidays.get_holidays(
            location=location,
            year=next_year,
            months=[next_month],
        )

        for holiday in list(current_month_holidays) + list(next_month_holidays):
            if holiday.date < start_date:
                continue

            holiday_datetime = datetime.combine(
                holiday.date, datetime.min.time()
            ).replace(tzinfo=timezone.utc)

            event = UpcomingEvent(
                name=holiday.name,
                location=str(LocationChoices(holiday.location).label),
                publication_date=holiday_datetime,
                time_str="Holiday",
                is_holiday=True,
            )

            date_key = holiday.date.strftime("%Y-%m-%d")
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)

    return events_by_date


def _merge_events_by_date(
    base: dict[str, list[UpcomingEvent]],
    new: dict[str, list[UpcomingEvent]],
) -> dict[str, list[UpcomingEvent]]:
    """Merge events dictionaries by extending lists when keys exist."""
    for date_key, events in new.items():
        if date_key in base:
            base[date_key].extend(events)
        else:
            base[date_key] = events
    return base


def _get_upcoming_events() -> list[UpcomingEventGroup]:
    """Build day-level upcoming events for the Economic Events page."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    today = get_local_today()

    _merge_events_by_date(
        events_by_date, _get_upcoming_events_from_publication_schedules(today)
    )
    _merge_events_by_date(events_by_date, _get_upcoming_central_bank_events())
    _merge_events_by_date(events_by_date, _get_upcoming_holidays_events(today))
    upcoming_events: list[UpcomingEventGroup] = []
    for date_key in sorted(events_by_date.keys()):
        day = date.fromisoformat(date_key)
        upcoming_events.append(
            {
                "date": date_key,
                "date_display": _format_day_label(day),
                "events": events_by_date[date_key],
            }
        )

    return upcoming_events


class UpcomingWeekGroup(TypedDict):
    """Upcoming events for one ISO week (Mon–Fri day slots).

    The UI pages these two-by-two; only one pair is visible at a time.
    """

    week_start: str
    week_label: str
    is_current_week: bool
    days: list[UpcomingEventGroup]


def _get_week_start_date(day: date) -> date:
    """Return Monday of the ISO week containing day."""
    return day - timedelta(days=day.weekday())


def _get_focus_week_start(today: date) -> date:
    """Monday of the first week shown in the pager.

    Mon–Fri: current ISO week. Sat–Sun (after Friday): next Monday's week.
    """
    if today.weekday() >= 5:  # Saturday or Sunday
        return today + timedelta(days=(7 - today.weekday()))
    return _get_week_start_date(today)


def _format_week_label(week_start: date) -> str:
    """Mon–Fri date range label without a 'Week of' prefix."""
    week_friday = week_start + timedelta(days=4)
    return f"{week_start.strftime('%d %b %Y')}" f" – {week_friday.strftime('%d %b %Y')}"


def _build_week_days(
    week_start: date,
    days_by_date: dict[str, UpcomingEventGroup],
) -> list[UpcomingEventGroup]:
    """Always return Mon–Fri day slots for a week (empty days included)."""
    days: list[UpcomingEventGroup] = []
    for day_offset in range(5):
        day = week_start + timedelta(days=day_offset)
        day_key = day.isoformat()
        existing = days_by_date.get(day_key)
        days.append(
            {
                "date": day_key,
                "date_display": _format_day_label(day),
                "events": existing["events"] if existing is not None else [],
            }
        )
    return days


def group_upcoming_events_by_week(
    upcoming_events: list[UpcomingEventGroup] | None = None,
    today: date | None = None,
) -> list[UpcomingWeekGroup]:
    """Group day-level upcoming events into weeks for two-by-two paging.

    Starts at the focus week and continues through the last week that has
    events (at least focus + next). Pads to an even week count so each page
    shows exactly two weeks. Every week includes Mon–Fri day slots.
    """
    if upcoming_events is None:
        upcoming_events = _get_upcoming_events()
    if today is None:
        today = get_local_today()

    focus_week_start = _get_focus_week_start(today)
    last_week_start = focus_week_start + timedelta(days=7)
    days_by_date = {day_group["date"]: day_group for day_group in upcoming_events}
    for day_group in upcoming_events:
        day = date.fromisoformat(day_group["date"])
        week_start = _get_week_start_date(day)
        if week_start >= focus_week_start:
            last_week_start = max(last_week_start, week_start)

    result: list[UpcomingWeekGroup] = []
    week_start = focus_week_start
    while week_start <= last_week_start:
        result.append(
            {
                "week_start": week_start.isoformat(),
                "week_label": _format_week_label(week_start),
                "is_current_week": week_start == focus_week_start,
                "days": _build_week_days(week_start, days_by_date),
            }
        )
        week_start += timedelta(days=7)

    if len(result) % 2 == 1:
        pad_week_start = week_start
        result.append(
            {
                "week_start": pad_week_start.isoformat(),
                "week_label": _format_week_label(pad_week_start),
                "is_current_week": False,
                "days": _build_week_days(pad_week_start, days_by_date),
            }
        )

    return result
