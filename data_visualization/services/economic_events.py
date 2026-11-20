"""Build upcoming economic events for the Economic Events visualization page."""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import NotRequired, TypedDict

from dateutil.relativedelta import relativedelta
from django.db.models import Max, Q

import market_overview.services.earnings as earnings
import market_overview.services.holidays as holidays
from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel
from core.services.calendar import convert_to_display_timezone, get_local_today
from data_visualization.services.config import ECONOMIC_EVENTS_LOCATIONS
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicDataModel,
    EconomicPublicationFrequencyChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from market_overview.models.common import LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel
from market_overview.services.config import HOLIDAY_COUNTRIES

# Codes / label ranks for the Economic Events country allowlist (US → FR → JP → EU).
_ECONOMIC_EVENTS_LOCATION_CODES: frozenset[str] = frozenset(
    location.value for location in ECONOMIC_EVENTS_LOCATIONS
)
_ECONOMIC_EVENTS_LOCATION_ORDER_BY_LABEL: dict[str, int] = {
    str(location.label): index
    for index, location in enumerate(ECONOMIC_EVENTS_LOCATIONS)
}
_UNKNOWN_LOCATION_ORDER = len(_ECONOMIC_EVENTS_LOCATION_ORDER_BY_LABEL)

# Focus week plus the next seven ISO weeks (Mon–Fri slots only).
_MAX_UPCOMING_EVENT_WEEKS = 8

_PERIOD_STEP_BY_FREQUENCY: dict[EconomicPublicationFrequencyChoices, relativedelta] = {
    EconomicPublicationFrequencyChoices.MONTHLY: relativedelta(months=1),
    EconomicPublicationFrequencyChoices.QUARTERLY: relativedelta(months=3),
    EconomicPublicationFrequencyChoices.ANNUAL: relativedelta(years=1),
}


class _UpcomingEventType(str, Enum):
    """Which filter group an Economic Events row belongs to."""

    ECONOMIC = "economic"
    EARNINGS = "earnings"
    HOLIDAY = "holiday"


class _UpcomingEvent(TypedDict):
    """Single upcoming calendar event for the Economic Events page."""

    name: str
    location: str  # Display label (Choices.label), not the stored code
    publication_date: datetime
    time_str: str
    is_holiday: bool
    event_type: _UpcomingEventType
    # Covered observation period label; empty when unknown or not applicable.
    period: str


class _UpcomingEventGroup(TypedDict):
    """Upcoming events for a single calendar day."""

    date: str
    date_display: str
    events: list[_UpcomingEvent]
    is_today: NotRequired[bool]  # Europe/Paris calendar day; set on week day slots


def _format_day_label(day: date) -> str:
    """Full weekday label, e.g. 'Monday 26 October 2026'."""
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}"


def _get_utc_lookback_start(start_date: date) -> datetime:
    """UTC lower bound one calendar day before 'start_date' (display-TZ buffer)."""
    return datetime.combine(
        start_date - timedelta(days=1), datetime.min.time()
    ).replace(tzinfo=timezone.utc)


def _get_upcoming_events_window_end(start_date: date) -> date:
    """Inclusive Friday of the last week shown from 'start_date' (a Monday)."""
    last_week_start = start_date + timedelta(weeks=_MAX_UPCOMING_EVENT_WEEKS - 1)
    return last_week_start + timedelta(days=4)


def _advance_period(
    period: date,
    frequency: EconomicPublicationFrequencyChoices,
    steps: int = 1,
) -> date:
    """Move 'period' forward by 'steps' publication frequencies."""
    if steps == 0:
        return period
    delta = _PERIOD_STEP_BY_FREQUENCY[frequency]
    advanced_period = period
    for _ in range(steps):
        advanced_period += delta
    return advanced_period


def _format_covered_period_label(
    period: date,
    frequency: EconomicPublicationFrequencyChoices,
) -> str:
    """Format a covered observation period the same way as economic-data displays."""
    match frequency:
        case EconomicPublicationFrequencyChoices.MONTHLY:
            month_str = period.strftime("%b")
            year_short = period.strftime("%y")
            return f"{month_str}.{year_short}"
        case EconomicPublicationFrequencyChoices.QUARTERLY:
            quarter = (period.month - 1) // 3 + 1
            year_short = period.year % 100
            return f"{year_short:02d}Q{quarter}"
        case EconomicPublicationFrequencyChoices.ANNUAL:
            return period.strftime("%Y")
        case _:
            raise ValueError(f"Unsupported publication frequency: {frequency!r}.")


def _append_upcoming_event(
    events_by_date: dict[str, list[_UpcomingEvent]],
    event: _UpcomingEvent,
) -> None:
    """Append 'event' under its display calendar date key."""
    # Usage of dict: keys are runtime YYYY-MM-DD display dates; values are events.
    date_key = convert_to_display_timezone(event["publication_date"]).strftime(
        "%Y-%m-%d"
    )
    if date_key not in events_by_date:
        events_by_date[date_key] = []
    events_by_date[date_key].append(event)


def _sort_day_events(events: list[_UpcomingEvent]) -> list[_UpcomingEvent]:
    """Sort one day's events: holidays first, then clock time, then country."""
    return sorted(
        events,
        key=lambda event: (
            not event["is_holiday"],
            "" if event["is_holiday"] else event["time_str"],
            _ECONOMIC_EVENTS_LOCATION_ORDER_BY_LABEL.get(
                event["location"], _UNKNOWN_LOCATION_ORDER
            ),
            event["name"],
        ),
    )


def _get_latest_period_by_indicator_id(
    indicator_ids: list[int],
) -> dict[int, date]:
    """Map each indicator id to the newest stored observation period start date."""
    # Usage of dict: indicator id → latest stored observation period start date.
    return {
        indicator_period["indicator_id"]: indicator_period["latest_period"]
        for indicator_period in EconomicDataModel.objects.filter(
            indicator_id__in=indicator_ids,
            period__isnull=False,
        )
        .values("indicator_id")
        .annotate(latest_period=Max("period"))
    }


def _append_upcoming_events_for_publication_schedule(
    events_by_date: dict[str, list[_UpcomingEvent]],
    schedule: PublicationScheduleModel,
    *,
    latest_period: date | None,
    start_date: date,
    end_date: date,
) -> None:
    """Append upcoming events for one publication schedule within the display window."""
    frequency = EconomicPublicationFrequencyChoices(schedule.indicator.frequency)
    location_label = str(EconomicDataLocationChoices(schedule.indicator.location).label)
    dated_slots: list[datetime] = []
    for publication_date in (
        schedule.previous_publication_date,
        schedule.current_publication_date,
    ):
        if publication_date is None:
            continue
        display_day = convert_to_display_timezone(publication_date).date()
        if display_day < start_date or display_day > end_date:
            continue
        dated_slots.append(publication_date)
    dated_slots.sort()
    for slot_index, publication_date in enumerate(dated_slots):
        display_dt = convert_to_display_timezone(publication_date)
        period_label = ""
        if latest_period is not None:
            covered_period = _advance_period(
                latest_period, frequency, steps=slot_index + 1
            )
            period_label = _format_covered_period_label(covered_period, frequency)
        _append_upcoming_event(
            events_by_date,
            _UpcomingEvent(
                name=schedule.indicator.series_label,
                location=location_label,
                publication_date=publication_date,
                time_str=display_dt.strftime("%H:%M"),
                is_holiday=False,
                event_type=_UpcomingEventType.ECONOMIC,
                period=period_label,
            ),
        )


def _get_upcoming_events_from_publication_schedules(
    start_date: date,
    end_date: date,
) -> dict[str, list[_UpcomingEvent]]:
    """Return publication events from 'start_date' through 'end_date' (inclusive).

    After ingest, a just-released value often lives only on
    'previous_publication_date' while 'current' advances — both must count
    when their Europe/Paris display day is on or after 'start_date'.
    Only US / FR / JP / EU indicators are included (no DE / ES / IT).

    Each release is labeled with the observation period it covers: the next period
    after the latest stored value, then one more step for each later slot of
    the same indicator.
    """
    # Usage of dict: keys are runtime YYYY-MM-DD display dates; values are events.
    events_by_date: dict[str, list[_UpcomingEvent]] = {}
    # UTC day-before buffer: Paris calendar start_date can still be prior-day UTC
    # (e.g. Mon 08:45 CET = Sun 23:45 UTC). Exact Paris day filter is below.
    lookback_utc = _get_utc_lookback_start(start_date)
    publication_schedules = list(
        PublicationScheduleModel.objects.filter(
            indicator__is_hidden=False,
            indicator__location__in=_ECONOMIC_EVENTS_LOCATION_CODES,
        )
        .filter(
            Q(current_publication_date__gte=lookback_utc)
            | Q(previous_publication_date__gte=lookback_utc)
        )
        .select_related("indicator")
    )
    indicator_ids = [schedule.indicator.pk for schedule in publication_schedules]
    latest_period_by_indicator_id = _get_latest_period_by_indicator_id(indicator_ids)

    for schedule in publication_schedules:
        _append_upcoming_events_for_publication_schedule(
            events_by_date,
            schedule,
            latest_period=latest_period_by_indicator_id.get(schedule.indicator.pk),
            start_date=start_date,
            end_date=end_date,
        )

    return events_by_date


def _get_upcoming_central_bank_events(
    start_date: date,
    end_date: date,
) -> dict[str, list[_UpcomingEvent]]:
    """Return central-bank rate decisions from 'start_date' through 'end_date'."""
    # Usage of dict: keys are runtime YYYY-MM-DD display dates; values are events.
    events_by_date: dict[str, list[_UpcomingEvent]] = {}
    # Same UTC day-before buffer as publication schedules (Paris vs UTC).
    lookback_utc = _get_utc_lookback_start(start_date)
    for meeting in CentralBankMeetingModel.objects.filter(
        date__gte=lookback_utc
    ).order_by("date"):
        display_dt = convert_to_display_timezone(meeting.date)
        display_day = display_dt.date()
        if display_day < start_date or display_day > end_date:
            continue
        central_bank = CentralBankChoices(meeting.central_bank)
        meeting_location = central_bank.get_location()
        if meeting_location.value not in _ECONOMIC_EVENTS_LOCATION_CODES:
            continue
        _append_upcoming_event(
            events_by_date,
            _UpcomingEvent(
                name=f"{central_bank.label} Rates Decision",
                location=str(EconomicDataLocationChoices(meeting_location.value).label),
                publication_date=meeting.date,
                time_str=display_dt.strftime("%H:%M"),
                is_holiday=False,
                event_type=_UpcomingEventType.ECONOMIC,
                period="",
            ),
        )

    return events_by_date


def _format_month_year_label(reporting_period_end: date) -> str:
    """Format a fiscal period end as month.year (for example '10.26')."""
    return f"{reporting_period_end.month}.{reporting_period_end.year % 100:02d}"


def _format_earnings_period_label(
    upcoming_reporting_period_end: date | None,
    last_reporting_period_end: date | None,
) -> str:
    """Format the covered earnings window as end month.year - start month.year.

    Upcoming is the end of the window; last reported is the start. When the last
    reported period is missing, the start is shown as '...'. Example:
    '12.26 - 10.26' or '10.26 - ...'.
    """
    if upcoming_reporting_period_end is None:
        return ""
    end_label = _format_month_year_label(upcoming_reporting_period_end)
    if last_reporting_period_end is None:
        return f"{end_label} - ..."
    start_label = _format_month_year_label(last_reporting_period_end)
    return f"{end_label} - {start_label}"


def _append_upcoming_event_for_earnings_watchlist(
    events_by_date: dict[str, list[_UpcomingEvent]],
    earnings_watchlist: EarningsWatchlistModel,
    announcement_datetime: datetime,
    *,
    start_date: date,
    end_date: date,
) -> None:
    """Append one earnings announcement when its display day is in the window."""
    display_dt = convert_to_display_timezone(announcement_datetime)
    display_day = display_dt.date()
    if display_day < start_date or display_day > end_date:
        return
    location = earnings.get_location_for_earnings_watchlist(earnings_watchlist)
    _append_upcoming_event(
        events_by_date,
        _UpcomingEvent(
            name=f"{earnings_watchlist.company} earnings",
            location=str(location.label),
            publication_date=announcement_datetime,
            time_str=display_dt.strftime("%H:%M"),
            is_holiday=False,
            event_type=_UpcomingEventType.EARNINGS,
            period=_format_earnings_period_label(
                earnings_watchlist.upcoming_reporting_period_end,
                earnings_watchlist.current_reporting_period_end,
            ),
        ),
    )


def _get_upcoming_earnings_events(
    start_date: date,
    end_date: date,
) -> dict[str, list[_UpcomingEvent]]:
    """Return watchlist earnings announcements from 'start_date' through 'end_date'."""
    # Usage of dict: keys are runtime YYYY-MM-DD display dates; values are events.
    events_by_date: dict[str, list[_UpcomingEvent]] = {}
    lookback_utc = _get_utc_lookback_start(start_date)
    window_end_utc = datetime.combine(end_date, datetime.max.time()).replace(
        tzinfo=timezone.utc
    )
    for (
        earnings_watchlist
    ) in earnings.list_earnings_watchlist_models_for_announcement_window(
        lookback_utc,
        window_end_utc,
    ):
        if earnings_watchlist.upcoming_announcement_datetime is not None:
            _append_upcoming_event_for_earnings_watchlist(
                events_by_date,
                earnings_watchlist,
                earnings_watchlist.upcoming_announcement_datetime,
                start_date=start_date,
                end_date=end_date,
            )
    return events_by_date


def _list_holiday_months(start_date: date, end_date: date) -> list[tuple[int, int]]:
    """Return distinct (year, month) pairs spanning 'start_date' through 'end_date'."""
    holiday_months: list[tuple[int, int]] = []
    cursor = date(start_date.year, start_date.month, 1)
    end_month_start = date(end_date.year, end_date.month, 1)
    while cursor <= end_month_start:
        holiday_months.append((cursor.year, cursor.month))
        cursor += relativedelta(months=1)
    return holiday_months


def _get_upcoming_holidays_events(
    start_date: date,
    end_date: date,
) -> dict[str, list[_UpcomingEvent]]:
    """Return holiday events from 'start_date' through 'end_date'."""
    # Usage of dict: keys are runtime YYYY-MM-DD holiday dates; values are events.
    events_by_date: dict[str, list[_UpcomingEvent]] = {}
    holiday_months = _list_holiday_months(start_date, end_date)

    for location in HOLIDAY_COUNTRIES:
        # Usage of dict: year → months requested for that year.
        months_by_year: dict[int, list[int]] = {}
        for year, month in holiday_months:
            months_by_year.setdefault(year, []).append(month)
        for year, months in months_by_year.items():
            for holiday in holidays.get_holidays(
                location=location,
                year=year,
                months=months,
            ):
                if holiday.date < start_date or holiday.date > end_date:
                    continue

                holiday_datetime = datetime.combine(
                    holiday.date, datetime.min.time()
                ).replace(tzinfo=timezone.utc)

                event = _UpcomingEvent(
                    name=holiday.name,
                    location=str(LocationChoices(holiday.location).label),
                    publication_date=holiday_datetime,
                    time_str="Holiday",
                    is_holiday=True,
                    event_type=_UpcomingEventType.HOLIDAY,
                    period="",
                )

                date_key = holiday.date.strftime("%Y-%m-%d")
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                events_by_date[date_key].append(event)

    return events_by_date


def _merge_events_by_date(
    events_by_date: dict[str, list[_UpcomingEvent]],
    events_to_merge: dict[str, list[_UpcomingEvent]],
) -> dict[str, list[_UpcomingEvent]]:
    """Merge day-keyed event maps by extending lists when dates already exist."""
    # Usage of dict: keys are runtime YYYY-MM-DD display dates; values are events.
    for date_key, day_events in events_to_merge.items():
        if date_key in events_by_date:
            events_by_date[date_key].extend(day_events)
        else:
            events_by_date[date_key] = day_events
    return events_by_date


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


def _get_upcoming_events() -> list[_UpcomingEventGroup]:
    """Build day-level events from the focus-week Monday through later dates.

    Past Mon–Fri slots in the current week keep already-released schedules
    ('previous_publication_date' / still-current past days), not only today+.
    The window stops after eight ISO weeks (inclusive Friday).
    """
    # Usage of dict: keys are runtime YYYY-MM-DD display dates; values are events.
    events_by_date: dict[str, list[_UpcomingEvent]] = {}
    today = get_local_today()
    start_date = _get_focus_week_start(today)
    end_date = _get_upcoming_events_window_end(start_date)

    _merge_events_by_date(
        events_by_date,
        _get_upcoming_events_from_publication_schedules(start_date, end_date),
    )
    _merge_events_by_date(
        events_by_date, _get_upcoming_central_bank_events(start_date, end_date)
    )
    _merge_events_by_date(
        events_by_date, _get_upcoming_earnings_events(start_date, end_date)
    )
    _merge_events_by_date(
        events_by_date, _get_upcoming_holidays_events(start_date, end_date)
    )
    upcoming_events: list[_UpcomingEventGroup] = []
    for date_key in sorted(events_by_date.keys()):
        day = date.fromisoformat(date_key)
        upcoming_events.append(
            _UpcomingEventGroup(
                date=date_key,
                date_display=_format_day_label(day),
                events=_sort_day_events(events_by_date[date_key]),
            )
        )

    return upcoming_events


class _UpcomingWeekGroup(TypedDict):
    """Upcoming events for one ISO week (Mon–Fri day slots).

    The UI pages these two-by-two; only one pair is visible at a time.
    """

    week_start: str
    week_label: str
    is_current_week: bool
    days: list[_UpcomingEventGroup]


def _format_week_label(week_start: date) -> str:
    """Mon–Fri date range label without a 'Week of' prefix."""
    week_friday = week_start + timedelta(days=4)
    return f"{week_start.strftime('%d %b %Y')}" f" – {week_friday.strftime('%d %b %Y')}"


def _list_week_day_slots(
    week_start: date,
    days_by_date: dict[str, _UpcomingEventGroup],
    today: date,
) -> list[_UpcomingEventGroup]:
    """Always return Mon–Fri day slots for a week (empty days included)."""
    # Usage of dict: keys are runtime YYYY-MM-DD display dates with events.
    days: list[_UpcomingEventGroup] = []
    for day_offset in range(5):
        day = week_start + timedelta(days=day_offset)
        day_key = day.isoformat()
        existing = days_by_date.get(day_key)
        days.append(
            _UpcomingEventGroup(
                date=day_key,
                date_display=_format_day_label(day),
                events=existing["events"] if existing is not None else [],
                is_today=day == today,
            )
        )
    return days


def group_upcoming_events_by_week(
    upcoming_events: list[_UpcomingEventGroup] | None = None,
    today: date | None = None,
) -> list[_UpcomingWeekGroup]:
    """Group day-level upcoming events into weeks for two-by-two paging.

    Starts at the focus week and continues through the last week that has
    events (at least focus + next), capped at eight weeks. Pads to an even
    week count so each page shows exactly two weeks when under the cap.
    Every week includes Mon–Fri day slots.
    """
    if upcoming_events is None:
        upcoming_events = _get_upcoming_events()
    if today is None:
        today = get_local_today()

    focus_week_start = _get_focus_week_start(today)
    max_week_start = focus_week_start + timedelta(weeks=_MAX_UPCOMING_EVENT_WEEKS - 1)
    last_week_start = focus_week_start + timedelta(days=7)
    days_by_date = {day_group["date"]: day_group for day_group in upcoming_events}
    for day_group in upcoming_events:
        day = date.fromisoformat(day_group["date"])
        week_start = _get_week_start_date(day)
        if focus_week_start <= week_start <= max_week_start:
            last_week_start = max(last_week_start, week_start)
    last_week_start = min(last_week_start, max_week_start)

    result: list[_UpcomingWeekGroup] = []
    week_start = focus_week_start
    while week_start <= last_week_start:
        result.append(
            _UpcomingWeekGroup(
                week_start=week_start.isoformat(),
                week_label=_format_week_label(week_start),
                is_current_week=week_start == focus_week_start,
                days=_list_week_day_slots(week_start, days_by_date, today),
            )
        )
        week_start += timedelta(days=7)

    if len(result) % 2 == 1 and week_start <= max_week_start:
        pad_week_start = week_start
        result.append(
            _UpcomingWeekGroup(
                week_start=pad_week_start.isoformat(),
                week_label=_format_week_label(pad_week_start),
                is_current_week=False,
                days=_list_week_day_slots(pad_week_start, days_by_date, today),
            )
        )

    return result
