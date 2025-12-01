from datetime import date, datetime, timezone
from typing import Dict, List, Optional, TypedDict

import central_banks_overview.services.cb_meetings_services as cb_meetings_services
import market_overview.services.holiday_services as holiday_services
from central_banks_overview.models import CENTRAL_BANK_LOCATION_MAP, CentralBankChoices
from economic_overview.models import (
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from market_overview.models import LocationChoices
from market_overview.services.holiday_services import HOLIDAY_COUNTRIES


class EconomicRecapItem(TypedDict):
    """Economic recap item."""

    category: str
    location: str
    name: str
    current: Optional[float]
    previous: Optional[float]
    change: Optional[float]
    period: Optional[str]


def get_economic_recap_data(locations: List[str]) -> Dict[str, List[EconomicRecapItem]]:
    """Get economic recap data."""
    indicators = EconomicIndicatorInformationModel.objects.all().order_by("id")
    economic_data: Dict[str, List[EconomicRecapItem]] = {}

    for indicator in indicators:
        category = indicator.category
        if category not in economic_data:
            economic_data[category] = []

        for location in locations:
            # Fetch the 2 most recent records
            records = list(
                EconomicDataModel.objects.filter(
                    indicator=indicator,
                    indicator__location=location,
                ).order_by("-period")[:2]
            )

            curr, prev = (records + [None, None])[:2]
            curr_value = getattr(curr, "data_value", None)
            prev_value = getattr(prev, "data_value", None)
            period = curr.get_period_display() if curr else None
            change = (
                curr_value - prev_value
                if curr_value is not None and prev_value is not None
                else None
            )

            economic_data[category].append(
                EconomicRecapItem(
                    category=category,
                    location=location,
                    name=indicator.type,
                    current=curr_value,
                    previous=prev_value,
                    change=change,
                    period=period,
                )
            )

    return economic_data


class EconomicEvent(TypedDict):
    """Economic event."""

    name: str
    location: str
    publication_date: datetime
    time_str: str


class UpcomingEventGroup(TypedDict):
    """Upcoming event group."""

    date: str
    date_display: str
    events: List[EconomicEvent]


def _get_upcoming_events_from_publication_schedules(
    start_date: date,
) -> Dict[str, List[EconomicEvent]]:
    """Get upcoming events from publication schedules."""
    events_by_date: Dict[str, List[EconomicEvent]] = {}
    upcoming_schedules = (
        PublicationScheduleModel.objects.filter(next_publication_date__gte=start_date)
        .select_related("indicator")
        .order_by("next_publication_date")[:100]
    )

    for schedule in upcoming_schedules:
        publication_date = schedule.current_publication_date
        if not publication_date:
            continue

        event = EconomicEvent(
            name=schedule.indicator.type,
            location=str(
                EconomicDataLocationChoices(schedule.indicator.location).label
            ),
            publication_date=publication_date,
            time_str=publication_date.strftime("%H:%M"),
        )

        date_key = publication_date.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return events_by_date


def _get_upcoming_central_bank_events() -> Dict[str, List[EconomicEvent]]:
    """Get upcoming central bank events."""
    events_by_date: Dict[str, List[EconomicEvent]] = {}
    for (
        central_bank_meeting_date
    ) in cb_meetings_services.get_central_bank_meeting_dates():
        central_bank = CentralBankChoices(central_bank_meeting_date["central_bank"])
        central_bank_location = CENTRAL_BANK_LOCATION_MAP[central_bank]
        meeting_date = central_bank_meeting_date["meeting_dates"][0]

        event = EconomicEvent(
            name=f"{central_bank.label} Rates Decision",
            location=str(EconomicDataLocationChoices(central_bank_location).label),
            publication_date=meeting_date,
            time_str=meeting_date.strftime("%H:%M"),
        )

        date_key = meeting_date.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return events_by_date


def _get_upcoming_holidays_events(start_date: date) -> Dict[str, List[EconomicEvent]]:
    """Get upcoming holidays events."""
    events_by_date: Dict[str, List[EconomicEvent]] = {}
    current_month = start_date.month
    current_year = start_date.year
    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year if current_month < 12 else current_year + 1

    for location in HOLIDAY_COUNTRIES:
        current_month_holidays = holiday_services.get_holidays(
            location=location,
            year=current_year,
            months=[current_month],
        )
        next_month_holidays = holiday_services.get_holidays(
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

            event = EconomicEvent(
                name=holiday.name,
                location=str(LocationChoices(holiday.location).label),
                publication_date=holiday_datetime,
                time_str="HOLIDAYS",
            )

            date_key = holiday.date.strftime("%Y-%m-%d")
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)

    return events_by_date


def _merge_events_by_date(
    base: Dict[str, List[EconomicEvent]],
    new: Dict[str, List[EconomicEvent]],
) -> Dict[str, List[EconomicEvent]]:
    """Merge events dictionaries by extending lists when keys exist.

    Args:
        base: Base dictionary to merge into
        new: New dictionary to merge from

    Returns:
        Merged dictionary with lists extended for existing keys
    """
    for date_key, events in new.items():
        if date_key in base:
            base[date_key].extend(events)
        else:
            base[date_key] = events
    return base


def get_economic_recap_upcoming_events() -> List[UpcomingEventGroup]:
    """Get economic recap upcoming events from publication schedules."""
    events_by_date: Dict[str, List[EconomicEvent]] = {}
    today = date.today()

    _merge_events_by_date(
        events_by_date, _get_upcoming_events_from_publication_schedules(today)
    )
    _merge_events_by_date(events_by_date, _get_upcoming_central_bank_events())
    _merge_events_by_date(events_by_date, _get_upcoming_holidays_events(today))
    upcoming_events: List[UpcomingEventGroup] = []
    for date_key in sorted(events_by_date.keys()):
        events_for_date = sorted(
            events_by_date[date_key], key=lambda event: event["publication_date"]
        )

        date_group: UpcomingEventGroup = {
            "date": date_key,
            "date_display": events_for_date[0]["publication_date"].strftime("%Y-%m-%d"),
            "events": events_for_date,
        }
        upcoming_events.append(date_group)

    return upcoming_events
