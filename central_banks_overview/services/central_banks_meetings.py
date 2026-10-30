"""Manage central bank meeting calendars and related metadata."""

from datetime import date, datetime, timedelta, timezone
from typing import TypedDict

from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel
from central_banks_overview.services.config import (
    MEETING_HISTORY_LOOKBACK_DAYS,
    NB_MEETINGS_TO_INGEST,
)
from central_banks_overview.services.scrapers.boj_meetings import (
    extract_boj_meeting_dates,
)
from central_banks_overview.services.scrapers.ecb_meetings import (
    extract_ecb_meeting_dates,
)
from central_banks_overview.services.scrapers.fomc_meetings import (
    extract_fomc_meeting_dates,
)
from core.services import get_market_watch_as_of_date, logger

CB_MEETINGS_EXTRACT_MAP = {
    CentralBankChoices.FRB: lambda: extract_fomc_meeting_dates(),
    CentralBankChoices.ECB: lambda: extract_ecb_meeting_dates(),
    CentralBankChoices.BOJ: lambda: extract_boj_meeting_dates(),
}


def _get_upcoming_meetings_cutoff(as_of: date) -> datetime:
    """UTC start of the calendar day after ``as_of``.

    Meetings on ``as_of`` have already occurred from the tool's end-of-day view;
    meetings on ``as_of + 1 day`` (e.g. today when ``as_of`` is T-1) are still next.
    """
    return datetime.combine(
        as_of + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )


def ingest_central_bank_meeting_dates(central_bank: CentralBankChoices):
    """Ingest specific central bank meeting dates.

    Updates or creates the next ``NB_MEETINGS_TO_INGEST`` upcoming meetings from
    the T-1 business-day perspective. Recently past meetings (within
    ``MEETING_HISTORY_LOOKBACK_DAYS`` before that cutoff) already in the DB are
    retained so day-event UIs can still show a rates decision after announcement
    day; older meetings are deleted.
    """
    if central_bank not in CB_MEETINGS_EXTRACT_MAP:
        return []
    scraped_meeting_dates = CB_MEETINGS_EXTRACT_MAP[central_bank]()

    upcoming_cutoff = _get_upcoming_meetings_cutoff(get_market_watch_as_of_date())
    lookback_start = upcoming_cutoff - timedelta(days=MEETING_HISTORY_LOOKBACK_DAYS)
    future_meeting_dates = sorted(
        meeting_date
        for meeting_date in scraped_meeting_dates
        if meeting_date >= upcoming_cutoff
    )[:NB_MEETINGS_TO_INGEST]
    # Already-stored meetings in [lookback_start, upcoming_cutoff): keep them so
    # day-event UIs can still show a rates decision after announcement day.
    past_meeting_dates_within_lookback = list(
        CentralBankMeetingModel.objects.filter(
            central_bank=central_bank,
            date__gte=lookback_start,
            date__lt=upcoming_cutoff,
        ).values_list("date", flat=True)
    )
    meeting_dates_to_keep = set(future_meeting_dates) | set(
        past_meeting_dates_within_lookback
    )
    logger.info(f"Ingesting meeting dates for {central_bank.label}")

    existing_meetings_by_date = {
        meeting.date: meeting
        for meeting in CentralBankMeetingModel.objects.filter(central_bank=central_bank)
    }
    meetings_to_create: list[CentralBankMeetingModel] = []
    meetings_to_update: list[CentralBankMeetingModel] = []

    for order_index, meeting_date in enumerate(future_meeting_dates):
        order = order_index + 1
        existing_meeting = existing_meetings_by_date.get(meeting_date)
        if existing_meeting is not None:
            if existing_meeting.order != order:
                existing_meeting.order = order
                meetings_to_update.append(existing_meeting)
            continue
        meetings_to_create.append(
            CentralBankMeetingModel(
                central_bank=central_bank, date=meeting_date, order=order
            )
        )

    for meeting_date in past_meeting_dates_within_lookback:
        existing_meeting = existing_meetings_by_date.get(meeting_date)
        if existing_meeting is not None and existing_meeting.order != 0:
            existing_meeting.order = 0
            meetings_to_update.append(existing_meeting)

    if meetings_to_create:
        CentralBankMeetingModel.objects.bulk_create(meetings_to_create)
    if meetings_to_update:
        CentralBankMeetingModel.objects.bulk_update(meetings_to_update, ["order"])
    CentralBankMeetingModel.objects.filter(central_bank=central_bank).exclude(
        date__in=meeting_dates_to_keep
    ).delete()


def ingest_all_central_bank_meeting_dates():
    """Ingest all central banks meeting dates."""
    for central_bank in CentralBankChoices:
        ingest_central_bank_meeting_dates(central_bank)


class _CentralBankMeetingDates(TypedDict):
    """Central Bank Meeting Dates."""

    central_bank: CentralBankChoices
    meeting_dates: list[datetime]


def get_central_bank_meeting_dates(
    central_banks: list[CentralBankChoices] = [],
) -> list[_CentralBankMeetingDates]:
    """Get upcoming central bank meeting dates from the Market Watch as-of date.

    Cutoff is always ``get_market_watch_as_of_date()`` (Paris T-1 business day).
    Meetings on the calendar day after that as-of (including "today") remain
    upcoming.
    """
    upcoming_cutoff = _get_upcoming_meetings_cutoff(get_market_watch_as_of_date())
    query = CentralBankMeetingModel.objects.filter(date__gte=upcoming_cutoff)
    if central_banks:
        query = query.filter(central_bank__in=[cb.value for cb in central_banks])

    distinct_central_banks = (
        query.values_list("central_bank", flat=True).distinct().order_by("central_bank")
    )
    return [
        _CentralBankMeetingDates(
            central_bank=central_bank,
            meeting_dates=list(
                query.filter(central_bank=central_bank)
                .order_by("date")
                .values_list("date", flat=True)
            ),
        )
        for central_bank in distinct_central_banks
    ]


def get_central_bank_next_meeting_date(
    central_bank: CentralBankChoices,
) -> datetime | None:
    """Get the next central bank meeting date from the Market Watch as-of date."""
    meeting_dates_by_bank = get_central_bank_meeting_dates([central_bank])
    if not meeting_dates_by_bank:
        return None
    meeting_dates = meeting_dates_by_bank[0]["meeting_dates"]
    if not meeting_dates:
        return None
    return meeting_dates[0]
