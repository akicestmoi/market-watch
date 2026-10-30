"""Manage central bank meeting calendars and related metadata."""

from datetime import datetime, timezone
from typing import TypedDict

from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel
from central_banks_overview.services.config import NB_MEETINGS_TO_INGEST
from central_banks_overview.services.scrapers.boj_meetings import (
    extract_boj_meeting_dates,
)
from central_banks_overview.services.scrapers.ecb_meetings import (
    extract_ecb_meeting_dates,
)
from central_banks_overview.services.scrapers.fomc_meetings import (
    extract_fomc_meeting_dates,
)
from core.services import logger

CB_MEETINGS_EXTRACT_MAP = {
    CentralBankChoices.FRB: lambda: extract_fomc_meeting_dates(),
    CentralBankChoices.ECB: lambda: extract_ecb_meeting_dates(),
    CentralBankChoices.BOJ: lambda: extract_boj_meeting_dates(),
}


def ingest_central_bank_meeting_dates(central_bank: CentralBankChoices):
    """Ingest specific central bank meeting dates.

    Updates or creates meeting dates in the database and deletes any past meetings.
    """
    if central_bank not in CB_MEETINGS_EXTRACT_MAP:
        return []
    meeting_dates = CB_MEETINGS_EXTRACT_MAP[central_bank]()

    now = datetime.now(timezone.utc)
    meeting_dates = [date for date in meeting_dates if date >= now]
    meeting_dates = meeting_dates[:NB_MEETINGS_TO_INGEST]
    logger.info(f"Ingesting meeting dates for {central_bank.label}")

    existing_meetings = {
        m.date: m
        for m in CentralBankMeetingModel.objects.filter(central_bank=central_bank)
    }
    meetings_to_create = []
    meetings_to_update = []

    for i, meeting_date in enumerate(meeting_dates):
        order = i + 1
        if meeting_date in existing_meetings:
            # Update existing meeting if order changed
            existing_meeting = existing_meetings[meeting_date]
            if existing_meeting.order != order:
                existing_meeting.order = order
                meetings_to_update.append(existing_meeting)
        else:
            # Create new meeting
            meetings_to_create.append(
                CentralBankMeetingModel(
                    central_bank=central_bank, date=meeting_date, order=order
                )
            )

    if meetings_to_create:
        CentralBankMeetingModel.objects.bulk_create(meetings_to_create)
    if meetings_to_update:
        CentralBankMeetingModel.objects.bulk_update(meetings_to_update, ["order"])
    CentralBankMeetingModel.objects.filter(central_bank=central_bank).exclude(
        date__in=set(meeting_dates)
    ).delete()


def ingest_all_central_bank_meeting_dates():
    """Ingest all central banks meeting dates."""
    for central_bank in CentralBankChoices:
        ingest_central_bank_meeting_dates(central_bank)


class CentralBankMeetingDates(TypedDict):
    """Central Bank Meeting Dates."""

    central_bank: CentralBankChoices
    meeting_dates: list[datetime]


def get_central_bank_meeting_dates(
    central_banks: list[CentralBankChoices] = [],
) -> list[CentralBankMeetingDates]:
    """Get central bank meeting dates."""
    query = CentralBankMeetingModel.objects.all()
    if central_banks:
        query = query.filter(central_bank__in=[cb.value for cb in central_banks])

    distinct_central_banks = (
        query.values_list("central_bank", flat=True).distinct().order_by("central_bank")
    )
    return [
        CentralBankMeetingDates(
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
    """Get central bank next meeting date."""
    meeting_dates_by_bank = get_central_bank_meeting_dates([central_bank])
    if not meeting_dates_by_bank:
        return None
    meeting_dates = meeting_dates_by_bank[0]["meeting_dates"]
    if not meeting_dates:
        return None
    return meeting_dates[0]
