"""Scrape ECB monetary policy meeting dates from the ECB website."""

from datetime import datetime

from bs4 import Tag
from cachetools.func import ttl_cache

from central_banks_overview.services.config import (
    ECB_ANNOUNCEMENT_HOUR,
    ECB_ANNOUNCEMENT_MINUTE,
    ECB_MEETING_URL,
    ECB_SOURCE_TIMEZONE,
)
from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import (
    convert_local_wall_time_to_utc,
    fetch_html,
)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def extract_ecb_meeting_dates() -> list[datetime]:
    """Extract ECB meeting dates from the ECB website.

    Returns:
        Sorted list of future ECB meeting dates (UTC timezone).

    Source: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
    """
    soup = fetch_html(ECB_MEETING_URL)
    if not soup:
        return []

    meeting_dates: list[datetime] = []

    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        if not isinstance(dt, Tag) or not isinstance(dd, Tag):
            continue
        date_text = dt.get_text(strip=True)
        description_text = dd.get_text(strip=True)

        if "Day 2" in description_text:
            meeting_day = datetime.strptime(date_text, "%d/%m/%Y").date()
            meeting_dates.append(
                convert_local_wall_time_to_utc(
                    meeting_day.year,
                    meeting_day.month,
                    meeting_day.day,
                    ECB_ANNOUNCEMENT_HOUR,
                    ECB_ANNOUNCEMENT_MINUTE,
                    source_timezone=ECB_SOURCE_TIMEZONE,
                )
            )
    return sorted(meeting_dates)
