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
from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import (
    convert_local_wall_time_to_utc,
    fetch_html,
)


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

    panels = soup.find_all("div", class_="panel panel-default")
    meeting_dates: list[datetime] = []

    for panel in panels:
        if not isinstance(panel, Tag):
            continue
        heading = panel.find("h4")
        if not isinstance(heading, Tag):
            continue

        year_match = re.search(r"(\d{4})", heading.get_text(strip=True))
        if not year_match:
            continue
        year = int(year_match.group(1))

        for row in panel.find_all("div", class_=re.compile(r"fomc-meeting")):
            if not isinstance(row, Tag):
                continue
            month_el = row.find("div", class_=re.compile("fomc-meeting__month"))
            date_el = row.find("div", class_=re.compile("fomc-meeting__date"))
            if not isinstance(month_el, Tag) or not isinstance(date_el, Tag):
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
            start_month = MONTH_NUMBER_BY_ABBREVIATION.get(months[0])
            end_month = MONTH_NUMBER_BY_ABBREVIATION.get(months[-1])
            if not start_month or not end_month:
                continue

            # Handle cross-year transition (e.g., Dec/Jan)
            meeting_year = year if start_month <= end_month else year + 1

            try:
                meeting_dates.append(
                    convert_local_wall_time_to_utc(
                        meeting_year,
                        end_month,
                        end_day,
                        FOMC_ANNOUNCEMENT_HOUR,
                        FOMC_ANNOUNCEMENT_MINUTE,
                        source_timezone=FOMC_SOURCE_TIMEZONE,
                    )
                )
            except ValueError:
                continue

    return sorted(meeting_dates)
