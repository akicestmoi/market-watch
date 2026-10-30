"""Scrape BoJ Monetary Policy Meeting (MPM) dates from the BoJ website."""

import re
from datetime import datetime
from typing import NamedTuple

from bs4 import Tag
from cachetools.func import ttl_cache

from central_banks_overview.services.config import (
    BOJ_ANNOUNCEMENT_HOUR,
    BOJ_ANNOUNCEMENT_MINUTE,
    BOJ_MPM_URL,
    BOJ_SOURCE_TIMEZONE,
)
from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import (
    convert_local_wall_time_to_utc,
    fetch_html,
)


class MonthDay(NamedTuple):
    """Calendar month and day of month."""

    month: int
    day: int


def _parse_boj_meeting_date(cell_text: str, year: int) -> datetime | None:
    """Parse BoJ meeting end date from a Japanese date string.

    Args:
        cell_text: Japanese date string (e.g., '4月30日（水）・5月 1日（木）')
        year: Base year for the meeting

    Returns:
        Meeting end date as datetime, or None if parsing fails.

    Example:
        '4月30日（水）・5月 1日（木）' → 2025-05-01 15:30 Asia/Tokyo (06:30 UTC)
    """
    MONTH_PATTERN = re.compile(r"(\d{1,2})月")
    DAY_PATTERN = re.compile(r"(\d{1,2})日")

    # Normalize and clean text
    text = re.sub(r"\[.*?\]", "", cell_text)  # Remove [PDF ...]
    text = re.sub(r"\([^)]*\)", "", text)  # Remove day of week (曜)
    text = text.replace("・", ",")  # Replace middle dot with comma
    text = re.sub(r"\s+", " ", text.strip())

    # Find all (month, day) pairs
    month_day_pairs: list[MonthDay] = []
    current_month = None

    for part in text.split(","):
        part = part.strip()
        month_match = MONTH_PATTERN.search(part)
        day_match = DAY_PATTERN.search(part)

        if month_match:
            current_month = int(month_match.group(1))

        if current_month and day_match:
            day = int(day_match.group(1))
            month_day_pairs.append(MonthDay(month=current_month, day=day))

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
        return convert_local_wall_time_to_utc(
            end_year,
            end_month,
            end_day,
            BOJ_ANNOUNCEMENT_HOUR,
            BOJ_ANNOUNCEMENT_MINUTE,
            source_timezone=BOJ_SOURCE_TIMEZONE,
        )
    except ValueError:
        return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def extract_boj_meeting_dates() -> list[datetime]:
    """Extract BoJ MPM (Monetary Policy Meeting) dates from the BoJ website.

    Returns:
        Sorted list of BoJ meeting dates (UTC timezone).

    Source: https://www.boj.or.jp/mopo/mpmsche_minu/index.htm
    """
    soup = fetch_html(BOJ_MPM_URL)
    if not soup:
        return []

    meeting_dates: list[datetime] = []

    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        caption = table.find("caption", class_="non-caption")
        if not isinstance(caption, Tag):
            continue

        year_match = re.search(r"(\d{4})", caption.get_text())
        if not year_match:
            continue

        year = int(year_match.group(1))

        for row in table.select("tbody tr"):
            if not isinstance(row, Tag):
                continue
            first_td = row.find("td")
            if not isinstance(first_td, Tag):
                continue

            cell_text = first_td.get_text(" ", strip=True)
            meeting_date = _parse_boj_meeting_date(cell_text, year)
            if meeting_date:
                meeting_dates.append(meeting_date)

    return sorted(meeting_dates)
