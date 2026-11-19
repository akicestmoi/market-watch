"""Shared HTTP / HTML fetch and datetime-parse helpers for scrapers."""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


def fetch_html(url: str) -> BeautifulSoup | None:
    """Fetch and parse HTML from a URL with error handling."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code >= 400:
            logger.warning(f"Error fetching {url}: HTTP {response.status_code}")
            return
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return


def parse_datetime(
    value: str | None,
    *,
    naive_timezone: str | ZoneInfo | None = None,
) -> datetime | None:
    """Parse an ISO / RFC-ish datetime string to UTC-aware datetime when possible.

    Aware inputs keep their offset and are normalized to UTC. Naive inputs use
    'naive_timezone' when given (source local time, e.g. America/New_York for
    US releases); otherwise they are treated as UTC. See 'docs/GUIDELINES.md'.
    """
    if not value:
        return None
    try:
        parsed_datetime = date_parser.parse(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed_datetime.tzinfo is None:
        if naive_timezone is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
        else:
            source_zone = (
                ZoneInfo(naive_timezone)
                if isinstance(naive_timezone, str)
                else naive_timezone
            )
            parsed_datetime = parsed_datetime.replace(tzinfo=source_zone)
    return parsed_datetime.astimezone(timezone.utc)
