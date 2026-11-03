"""Manage central bank meeting calendars and related metadata."""

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple, TypedDict

import central_banks_overview.services.central_banks_data as central_banks_data
from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankMeetingModel,
    CentralBankMeetingStatusChoices,
)
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
from core.locks import release_redis_lock, try_acquire_redis_lock
from core.services import (
    convert_to_display_timezone,
    get_market_watch_as_of_date,
    logger,
)

CB_MEETINGS_EXTRACT_MAP = {
    CentralBankChoices.FRB: lambda: extract_fomc_meeting_dates(),
    CentralBankChoices.ECB: lambda: extract_ecb_meeting_dates(),
    CentralBankChoices.BOJ: lambda: extract_boj_meeting_dates(),
}


def _get_upcoming_meetings_cutoff(as_of: date) -> datetime:
    """Return the UTC start of the calendar day after 'as_of'.

    Meetings on 'as_of' have already occurred from the tool's end-of-day view;
    meetings on 'as_of + 1 day' (e.g. today when 'as_of' is T-1) are still next.
    """
    return datetime.combine(
        as_of + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )


class _MeetingDatesToKeep(NamedTuple):
    """Upcoming scrape dates plus lookback past dates that should stay in the DB."""

    upcoming_meeting_dates_to_keep: list[datetime]
    past_meeting_dates_to_keep: list[datetime]


def _list_meeting_dates_to_keep(
    central_bank: CentralBankChoices,
    scraped_meeting_dates: list[datetime],
) -> _MeetingDatesToKeep:
    """Build the upcoming + lookback past dates that should stay in the DB."""
    as_of = get_market_watch_as_of_date()
    upcoming_cutoff = _get_upcoming_meetings_cutoff(as_of)
    lookback_first_date = as_of - timedelta(days=MEETING_HISTORY_LOOKBACK_DAYS - 1)
    lookback_last_date = as_of + timedelta(days=1)

    # Keep at most the next NB_MEETINGS_TO_INGEST upcoming dates from the scrape.
    upcoming_meeting_dates_to_keep = sorted(
        meeting_date
        for meeting_date in scraped_meeting_dates
        if meeting_date >= upcoming_cutoff
    )[:NB_MEETINGS_TO_INGEST]
    upcoming_meeting_dates_set = set(upcoming_meeting_dates_to_keep)

    # Keep already-stored meetings whose display day is still in the lookback
    # window, including "today" (as_of + 1). A same-day UTC afternoon meeting can
    # be >= upcoming cutoff, so a naive date__lt=cutoff lookback would drop it
    # once the scrape stops listing it after the announcement.
    past_meeting_dates_to_keep = [
        meeting.date
        for meeting in CentralBankMeetingModel.objects.filter(central_bank=central_bank)
        if meeting.date not in upcoming_meeting_dates_set
        and lookback_first_date
        <= convert_to_display_timezone(meeting.date).date()
        <= lookback_last_date
    ]
    return _MeetingDatesToKeep(
        upcoming_meeting_dates_to_keep=upcoming_meeting_dates_to_keep,
        past_meeting_dates_to_keep=past_meeting_dates_to_keep,
    )


class _UpcomingMeetingsToUpsert(NamedTuple):
    """Lists meetings to bulk-create or bulk-update for the upcoming calendar."""

    meetings_to_create: list[CentralBankMeetingModel]
    meetings_to_update: list[CentralBankMeetingModel]


def _list_upcoming_meetings_to_upsert(
    central_bank: CentralBankChoices,
    upcoming_meeting_dates: list[datetime],
    existing_meetings_by_date: dict[datetime, CentralBankMeetingModel],
) -> _UpcomingMeetingsToUpsert:
    """List create/update meetings so upcoming ones exist with status 'UPCOMING'."""
    meetings_to_create: list[CentralBankMeetingModel] = []
    meetings_to_update: list[CentralBankMeetingModel] = []
    for meeting_date in upcoming_meeting_dates:
        existing_meeting = existing_meetings_by_date.get(meeting_date)
        if existing_meeting is not None:
            if existing_meeting.status != CentralBankMeetingStatusChoices.UPCOMING:
                existing_meeting.status = CentralBankMeetingStatusChoices.UPCOMING
                meetings_to_update.append(existing_meeting)
            continue
        meetings_to_create.append(
            CentralBankMeetingModel(
                central_bank=central_bank,
                date=meeting_date,
                status=CentralBankMeetingStatusChoices.UPCOMING,
            )
        )
    return _UpcomingMeetingsToUpsert(
        meetings_to_create=meetings_to_create,
        meetings_to_update=meetings_to_update,
    )


def _delete_unnecessary_meetings_data(
    central_bank: CentralBankChoices,
    meeting_dates_to_keep: _MeetingDatesToKeep,
) -> None:
    """Delete stored meetings for 'central_bank' that are not upcoming or lookback."""
    dates_to_keep = set(meeting_dates_to_keep.upcoming_meeting_dates_to_keep) | set(
        meeting_dates_to_keep.past_meeting_dates_to_keep
    )
    CentralBankMeetingModel.objects.filter(central_bank=central_bank).exclude(
        date__in=dates_to_keep
    ).delete()


def ingest_central_bank_meeting_dates(central_bank: CentralBankChoices) -> None:
    """Ingest meeting dates for one central bank.

    Updates or creates the next 'NB_MEETINGS_TO_INGEST' upcoming meetings from
    the T-1 business-day perspective. Recently past meetings already in the DB
    whose Paris display date falls in
    '[as_of - (LOOKBACK - 1 days), as_of + 1 day]' (through "today") are
    retained so day-event UIs still show a rates decision after the source
    calendar drops the meeting; older meetings are deleted.
    """
    if central_bank not in CB_MEETINGS_EXTRACT_MAP:
        return

    logger.info(f"Ingesting meeting dates for {central_bank.label}")
    scraped_meeting_dates = CB_MEETINGS_EXTRACT_MAP[central_bank]()
    meeting_dates_to_keep = _list_meeting_dates_to_keep(
        central_bank, scraped_meeting_dates
    )
    existing_meetings_by_date = {
        meeting.date: meeting
        for meeting in CentralBankMeetingModel.objects.filter(central_bank=central_bank)
    }

    upcoming_meetings_to_upsert = _list_upcoming_meetings_to_upsert(
        central_bank,
        meeting_dates_to_keep.upcoming_meeting_dates_to_keep,
        existing_meetings_by_date,
    )
    for meeting_date in meeting_dates_to_keep.past_meeting_dates_to_keep:
        existing_meeting = existing_meetings_by_date.get(meeting_date)
        # 'mark_meeting_status' only allows UPCOMING → OCCURRED; leave OCCURRED /
        # RATES_INGESTED alone.
        if (
            existing_meeting is None
            or existing_meeting.status != CentralBankMeetingStatusChoices.UPCOMING
        ):
            continue
        mark_meeting_status(existing_meeting, CentralBankMeetingStatusChoices.OCCURRED)

    if upcoming_meetings_to_upsert.meetings_to_create:
        CentralBankMeetingModel.objects.bulk_create(
            upcoming_meetings_to_upsert.meetings_to_create
        )
    if upcoming_meetings_to_upsert.meetings_to_update:
        CentralBankMeetingModel.objects.bulk_update(
            upcoming_meetings_to_upsert.meetings_to_update, ["status"]
        )
    _delete_unnecessary_meetings_data(central_bank, meeting_dates_to_keep)


def ingest_all_central_bank_meeting_dates() -> None:
    """Ingest meeting dates for every central bank."""
    for central_bank in CentralBankChoices:
        ingest_central_bank_meeting_dates(central_bank)


class _CentralBankMeetingDates(TypedDict):
    """Meeting calendar dates for one central bank."""

    central_bank: CentralBankChoices
    meeting_dates: list[datetime]


def get_central_bank_meeting_dates(
    central_banks: list[CentralBankChoices] | None = None,
) -> list[_CentralBankMeetingDates]:
    """Return upcoming central bank meeting dates from the Market Watch as-of date.

    Cutoff is always 'get_market_watch_as_of_date()' (Paris T-1 business day).
    Meetings on the calendar day after that as-of (including "today") remain
    upcoming.
    """
    upcoming_cutoff = _get_upcoming_meetings_cutoff(get_market_watch_as_of_date())
    query = CentralBankMeetingModel.objects.filter(date__gte=upcoming_cutoff)
    if central_banks:
        query = query.filter(
            central_bank__in=[central_bank.value for central_bank in central_banks]
        )

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
    # The query asked for one bank, so index 0 is that bank's meeting-date payload.
    meeting_dates = meeting_dates_by_bank[0]["meeting_dates"]
    if not meeting_dates:
        return None
    # Dates are ordered earliest upcoming first, so index 0 is the next meeting.
    return meeting_dates[0]


def has_past_meeting(central_bank: CentralBankChoices) -> bool:
    """Return whether 'central_bank' has any meeting whose UTC time is already past."""
    return CentralBankMeetingModel.objects.filter(
        central_bank=central_bank,
        date__lt=datetime.now(timezone.utc),
    ).exists()


def list_past_meetings_pending_rates_ingest(
    central_bank: CentralBankChoices,
) -> list[CentralBankMeetingModel]:
    """Return past meetings for 'central_bank' that still need key-rate ingest.

    Includes meetings with 'date' before the current UTC time, and excludes
    meetings already marked 'RATES_INGESTED'. Results are oldest first so a
    missed decision day is ingested before a newer one.
    """
    return list(
        CentralBankMeetingModel.objects.filter(
            central_bank=central_bank,
            date__lt=datetime.now(timezone.utc),
        )
        .exclude(status=CentralBankMeetingStatusChoices.RATES_INGESTED)
        .order_by("date")
    )


def mark_meeting_status(
    meeting: CentralBankMeetingModel,
    status: CentralBankMeetingStatusChoices,
) -> CentralBankMeetingModel:
    """Move a meeting to 'status' along the allowed lifecycle.

    Allowed: UPCOMING → OCCURRED → RATES_INGESTED. Same status is a no-op.
    'RATES_INGESTED' cannot be set from 'UPCOMING'.
    """
    current_status = CentralBankMeetingStatusChoices(meeting.status)
    if current_status == status:
        return meeting
    match (current_status, status):
        case (
            CentralBankMeetingStatusChoices.UPCOMING,
            CentralBankMeetingStatusChoices.OCCURRED,
        ):
            meeting.status = CentralBankMeetingStatusChoices.OCCURRED
            meeting.save(update_fields=["status", "last_modified"])
            return meeting
        case (
            CentralBankMeetingStatusChoices.OCCURRED,
            CentralBankMeetingStatusChoices.RATES_INGESTED,
        ):
            meeting.status = CentralBankMeetingStatusChoices.RATES_INGESTED
            meeting.save(update_fields=["status", "last_modified"])
            return meeting
        case _:
            raise ValueError(
                f"Cannot mark meeting id={meeting.pk} as {status.value} "
                f"from {current_status.value}."
            )


def ingest_pending_decision_day_key_rates(central_bank: CentralBankChoices) -> None:
    """Ingest key rates for past meetings still pending rates ingest.

    Marks each meeting 'OCCURRED', upserts key rates on the display calendar day
    under a Redis lock, then marks 'RATES_INGESTED' when ingest finishes.
    """
    for meeting in list_past_meetings_pending_rates_ingest(central_bank):
        mark_meeting_status(meeting, CentralBankMeetingStatusChoices.OCCURRED)
        # Ingest key rates on the meeting's display calendar day so market
        # recap economic releases can join them via that event date.
        key_rate_date = convert_to_display_timezone(meeting.date).date()
        lock_key = central_banks_data.get_cb_data_ingestion_lock_key(
            central_bank, key_rate_date
        )
        lock = try_acquire_redis_lock(lock_key)
        if lock is None:
            logger.warning(
                "Skipping CB data ingestion for %s on %s: already in progress.",
                central_bank.value,
                key_rate_date.isoformat(),
            )
            continue
        try:
            central_banks_data.ingest_central_bank_data(
                central_bank=central_bank,
                date_to_ingest=key_rate_date,
            )
            mark_meeting_status(meeting, CentralBankMeetingStatusChoices.RATES_INGESTED)
        finally:
            release_redis_lock(lock, lock_key)
