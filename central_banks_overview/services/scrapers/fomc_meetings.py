"""Scrape FOMC meeting dates from the Federal Reserve website."""

import re
from datetime import datetime

from bs4 import Tag
from cachetools.func import ttl_cache

from central_banks_overview.services.config import (
    FOMC_ANNOUNCEMENT_HOUR,
    FOMC_ANNOUNCEMENT_MINUTE,
    FOMC_MEETING_URL,
    FOMC_SOURCE_TIMEZONE,
    MONTH_NUMBER_BY_ABBREVIATION,
)
from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from core.services.scraping import fetch_html


def _parse_fomc_meeting_block_datetime(
    year: int,
    month_el: Tag,
    date_el: Tag,
) -> datetime | None:
    """Parse one FOMC meeting block into an announcement datetime in UTC."""
    month_text = month_el.get_text(strip=True).lower()
    date_text = date_el.get_text(strip=True)

    # Skip meetings with parentheses (unscheduled, notation, cancelled)
    # Must be a date range (e.g. "30-31")
    if "(" in date_text or "-" not in date_text:
        return None

    date_text = date_text.replace("*", "").strip()
    try:
        _, end_day = map(int, date_text.split("-", 1))
    except ValueError:
        return None

    months = [m.strip()[:3] for m in re.split(r"[/\s]+", month_text) if m.strip()]
    if not months:
        return None

    # Index 0 is start month; index -1 is end (same for a single month).
    start_month = MONTH_NUMBER_BY_ABBREVIATION.get(months[0])
    end_month = MONTH_NUMBER_BY_ABBREVIATION.get(months[-1])
    if not start_month or not end_month:
        return None

    meeting_year = year if start_month <= end_month else year + 1

    try:
        return convert_local_wall_time_to_utc(
            meeting_year,
            end_month,
            end_day,
            FOMC_ANNOUNCEMENT_HOUR,
            FOMC_ANNOUNCEMENT_MINUTE,
            source_timezone=FOMC_SOURCE_TIMEZONE,
        )
    except ValueError:
        return None


def _extract_fomc_meeting_dates_from_panel(panel: Tag) -> list[datetime]:
    """Extract FOMC meeting datetimes from one calendar year panel."""
    heading = panel.find("h4")
    if not isinstance(heading, Tag):
        return []

    year_match = re.search(r"(\d{4})", heading.get_text(strip=True))
    if not year_match:
        return []
    year = int(year_match.group(1))

    meeting_dates: list[datetime] = []
    for meeting_block in panel.find_all("div", class_=re.compile(r"fomc-meeting")):
        if not isinstance(meeting_block, Tag):
            continue
        month_el = meeting_block.find("div", class_=re.compile("fomc-meeting__month"))
        date_el = meeting_block.find("div", class_=re.compile("fomc-meeting__date"))
        if not isinstance(month_el, Tag) or not isinstance(date_el, Tag):
            continue

        meeting_datetime = _parse_fomc_meeting_block_datetime(year, month_el, date_el)
        if meeting_datetime is not None:
            meeting_dates.append(meeting_datetime)

    return meeting_dates


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def extract_fomc_meeting_dates() -> list[datetime]:
    """Extract FOMC meeting dates from the Federal Reserve website.

    Returns:
        Sorted list of future FOMC meeting dates (UTC timezone).

    Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    """
    soup = fetch_html(FOMC_MEETING_URL)
    if not soup:
        return []

    meeting_dates: list[datetime] = []
    for panel in soup.find_all("div", class_="panel panel-default"):
        if not isinstance(panel, Tag):
            continue
        meeting_dates.extend(_extract_fomc_meeting_dates_from_panel(panel))

    return sorted(meeting_dates)
