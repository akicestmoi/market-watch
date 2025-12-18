import re
from datetime import datetime, time, timezone
from typing import List, Optional, Tuple, TypedDict

from cachetools.func import ttl_cache

from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel
from core.services import fetch_html, logger

FOMC_MEETING_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BOJ_MPM_URL = "https://www.boj.or.jp/mopo/mpmsche_minu/index.htm"
ECB_MEETING_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"

# FOMC meetings typically start at 2:00 PM ET (13:00 UTC during standard time)
FOMC_MEETING_HOUR_UTC = 13
# BoJ meetings typically start at 9:00 AM JST (4:00 UTC during standard time)
BOJ_MEETING_HOUR_UTC = 4
# ECB meetings typically start at 2:15 PM CET (13:15 UTC during standard time)
ECB_MEETING_HOUR_UTC = 13
ECB_MEETING_MINUTE_UTC = 15

MONTH_ABBREVIATIONS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

NB_MEETINGS_TO_INGEST = 15

CB_MEETINGS_EXTRACT_MAP = {
    CentralBankChoices.FRB: lambda: _extract_fomc_meeting_dates(),
    CentralBankChoices.ECB: lambda: _extract_ecb_meeting_dates(),
    CentralBankChoices.BOJ: lambda: _extract_boj_meeting_dates(),
}


class CentralBankMeetingDates(TypedDict):
    """Central Bank Meeting Dates."""

    central_bank: CentralBankChoices
    meeting_dates: List[datetime]


@ttl_cache(maxsize=128, ttl=10 * 60)
def _extract_fomc_meeting_dates() -> List[datetime]:
    """Extract FOMC meeting dates from the Federal Reserve website.

    Returns:
        Sorted list of future FOMC meeting dates (UTC timezone).

    Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    """
    soup = fetch_html(FOMC_MEETING_URL)
    if not soup:
        return []

    panels = soup.find_all("div", class_="panel panel-default")
    meeting_dates: List[datetime] = []

    for panel in panels:
        heading = panel.find("h4")
        if not heading:
            continue

        year_match = re.search(r"(\d{4})", heading.get_text(strip=True))
        if not year_match:
            continue
        year = int(year_match.group(1))

        for row in panel.find_all("div", class_=re.compile(r"fomc-meeting")):
            month_el = row.find("div", class_=re.compile("fomc-meeting__month"))
            date_el = row.find("div", class_=re.compile("fomc-meeting__date"))
            if not month_el or not date_el:
                continue

            month_text = month_el.get_text(strip=True).lower()
            date_text = date_el.get_text(strip=True)

            # Skip meetings with parentheses (unscheduled, notation, cancelled)
            # Must be a date range (e.g. "30-31")
            if "(" in date_text or "-" not in date_text:
                continue

            # Parse end day from date range
            date_text = date_text.replace("*", "").strip()
            try:
                _, end_day = map(int, date_text.split("-", 1))
            except ValueError:
                continue

            # Parse month(s) - handle "Jan/Feb" format
            months = [
                m.strip()[:3] for m in re.split(r"[/\s]+", month_text) if m.strip()
            ]
            if not months:
                continue

            # This handles regular meetings, cross-month (like Jan/Feb 31-1) meetings
            # and single-month meetings
            start_month = MONTH_ABBREVIATIONS.get(months[0])
            end_month = MONTH_ABBREVIATIONS.get(months[-1])
            if not start_month or not end_month:
                continue

            # Handle cross-year transition (e.g., Dec/Jan)
            meeting_year = year if start_month <= end_month else year + 1

            try:
                meeting_dates.append(
                    datetime(
                        meeting_year,
                        end_month,
                        end_day,
                        FOMC_MEETING_HOUR_UTC,
                        tzinfo=timezone.utc,
                    )
                )
            except ValueError:
                continue

    return sorted(meeting_dates)


@ttl_cache(maxsize=128, ttl=10 * 60)
def _extract_ecb_meeting_dates() -> List[datetime]:
    """Extract ECB meeting dates from the ECB website.

    Returns:
        Sorted list of future ECB meeting dates (UTC timezone).

    Source: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
    """
    soup = fetch_html(ECB_MEETING_URL)
    if not soup:
        return []

    meeting_dates: List[datetime] = []

    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        date_text = dt.get_text(strip=True)
        description_text = dd.get_text(strip=True)

        if "Day 2" in description_text:
            meeting_dates.append(
                datetime.combine(
                    datetime.strptime(date_text, "%d/%m/%Y").date(),
                    time(ECB_MEETING_HOUR_UTC, ECB_MEETING_MINUTE_UTC),
                    tzinfo=timezone.utc,
                )
            )
    return sorted(meeting_dates)


def _parse_boj_meeting_date(cell_text: str, year: int) -> Optional[datetime]:
    """Parse BoJ meeting end date from a Japanese date string.

    Args:
        cell_text: Japanese date string (e.g., '4月30日（水）・5月 1日（木）')
        year: Base year for the meeting

    Returns:
        Meeting end date as datetime, or None if parsing fails.

    Example:
        '4月30日（水）・5月 1日（木）' → datetime(2025, 5, 1, 4, tzinfo=timezone.utc)
    """
    MONTH_PATTERN = re.compile(r"(\d{1,2})月")
    DAY_PATTERN = re.compile(r"(\d{1,2})日")

    # Normalize and clean text
    text = re.sub(r"\[.*?\]", "", cell_text)  # Remove [PDF ...]
    text = re.sub(r"\([^)]*\)", "", text)  # Remove day of week (曜)
    text = text.replace("・", ",")  # Replace middle dot with comma
    text = re.sub(r"\s+", " ", text.strip())

    # Find all (month, day) pairs
    month_day_pairs: List[Tuple[int, int]] = []
    current_month = None

    for part in text.split(","):
        part = part.strip()
        month_match = MONTH_PATTERN.search(part)
        day_match = DAY_PATTERN.search(part)

        if month_match:
            current_month = int(month_match.group(1))

        if current_month and day_match:
            day = int(day_match.group(1))
            month_day_pairs.append((current_month, day))

    if not month_day_pairs:
        return None

    # For single-day meetings, use the same date as start and end
    if len(month_day_pairs) == 1:
        month_day_pairs.append(month_day_pairs[0])

    start_month, _ = month_day_pairs[0]
    end_month, end_day = month_day_pairs[-1]

    # Handle year rollover (Dec → Jan)
    end_year = year + 1 if end_month < start_month else year

    try:
        return datetime(
            end_year, end_month, end_day, BOJ_MEETING_HOUR_UTC, tzinfo=timezone.utc
        )
    except ValueError:
        return None


@ttl_cache(maxsize=128, ttl=10 * 60)
def _extract_boj_meeting_dates() -> List[datetime]:
    """Extract BoJ MPM (Monetary Policy Meeting) dates from the BoJ website.

    Returns:
        Sorted list of BoJ meeting dates (UTC timezone).

    Source: https://www.boj.or.jp/mopo/mpmsche_minu/index.htm
    """
    soup = fetch_html(BOJ_MPM_URL)
    if not soup:
        return []

    meeting_dates: List[datetime] = []

    for table in soup.find_all("table"):
        caption = table.find("caption", class_="non-caption")
        if not caption:
            continue

        year_match = re.search(r"(\d{4})", caption.get_text())
        if not year_match:
            continue

        year = int(year_match.group(1))

        for row in table.select("tbody tr"):
            first_td = row.find("td")
            if not first_td:
                continue

            cell_text = first_td.get_text(" ", strip=True)
            meeting_date = _parse_boj_meeting_date(cell_text, year)
            if meeting_date:
                meeting_dates.append(meeting_date)

    return sorted(meeting_dates)


def _ingest_specific_central_bank_meeting_dates(
    central_bank: CentralBankChoices, meeting_dates: List[datetime]
):
    """Ingest specific central bank meeting dates.

    Updates or creates meeting dates in the database and deletes any past meetings.
    """
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


def ingest_central_bank_meeting_dates():
    """Ingest all central banks meeting dates."""
    for central_bank in CentralBankChoices:
        if central_bank not in CB_MEETINGS_EXTRACT_MAP:
            continue
        meeting_dates = CB_MEETINGS_EXTRACT_MAP[central_bank]()
        _ingest_specific_central_bank_meeting_dates(central_bank, meeting_dates)


def get_central_bank_meeting_dates(
    central_banks: List[CentralBankChoices] = [],
) -> List[CentralBankMeetingDates]:
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
) -> Optional[datetime]:
    """Get central bank next meeting date."""
    meeting_dates_by_bank = get_central_bank_meeting_dates([central_bank])
    if not meeting_dates_by_bank:
        return None
    meeting_dates = meeting_dates_by_bank[0]["meeting_dates"]
    if not meeting_dates:
        return None
    return meeting_dates[0]
