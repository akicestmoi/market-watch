"""Shared utilities (logging, HTML fetch helpers) used across apps."""

import logging
from datetime import date, datetime, timezone
from enum import Enum
from typing import TypeVar
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone as dj_timezone
from rest_framework.exceptions import NotFound

from .models import BaseLogModel, BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
L = TypeVar("L", bound=BaseLogModel)

# Source wall-clock zones for location codes (economic / market location choices).
# Naive publish times from a source are interpreted in this zone, then stored as UTC.
SOURCE_TIMEZONE_BY_LOCATION_CODE: dict[str, str] = {
    "US": "America/New_York",
    "EU": "Europe/Berlin",
    "FR": "Europe/Paris",
    "JP": "Asia/Tokyo",
    "DE": "Europe/Berlin",
}


class ValueChangeOutput(str, Enum):
    """Which scalar ``calculate_value_change`` should return."""

    ABSOLUTE = "absolute"
    PERCENT = "percent"
    BPS = "bps"
    ANNUALIZED_PERCENT = "annualized_percent"


def calculate_value_change(
    current: float | None,
    previous: float | None,
    output: ValueChangeOutput,
    annualized_ratio: float | None = None,
) -> float | None:
    """Compute one change metric from ``previous`` to ``current``.

    Period labels (DoD / WoW / MoM / QoQ / QoQy / YoY) are caller concerns: pick
    the comparison value and ``output``. Returns None when either input is None.

    - ``ABSOLUTE`` — ``current - previous``
    - ``PERCENT`` — ``(absolute / previous) * 100`` (None if ``previous`` is 0)
    - ``BPS`` — ``absolute * 100`` (yields quoted in percent)
    - ``ANNUALIZED_PERCENT`` — ``((current / previous) ** annualized_ratio - 1) *
      100`` (requires ``annualized_ratio``; None if ``previous`` is 0 or the
      ratio is non-positive)
    """
    if current is None or previous is None:
        return None
    absolute = current - previous
    match output:
        case ValueChangeOutput.ABSOLUTE:
            return absolute
        case ValueChangeOutput.BPS:
            return absolute * 100
        case ValueChangeOutput.PERCENT:
            return None if previous == 0 else (absolute / previous) * 100
        case ValueChangeOutput.ANNUALIZED_PERCENT:
            if annualized_ratio is None or previous == 0:
                return None
            ratio = current / previous
            if ratio <= 0:
                return None
            return ((ratio**annualized_ratio) - 1) * 100


def update_with_logs(
    model_to_update: T,
    log_model: type[L],
    updates: dict,  # Polymorphic: field keys vary by model (abstract helper).
    logging_on_fields: list[str] = [],
    none_skip_fields: list[str] = [],
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs in a related log table."""
    if not none_skip_fields and not enable_none_updates:
        raise ValueError("Need to specify fields to skip or enable none updates.")

    if none_skip_fields:
        model_fields = [field.name for field in model_to_update._meta.get_fields()]
        if not all(field in model_fields for field in none_skip_fields):
            raise ValueError(f"Fields to skip must be in model: {model_fields}")

    update_logs = updates.get("logs") or ""
    has_changes = False
    field_updates = [(key, value) for key, value in updates.items() if key != "logs"]

    for field, new_value in field_updates:
        if field in none_skip_fields:
            existing_value = getattr(model_to_update, field, None)
            if existing_value is not None and new_value is None:
                return model_to_update

    for field, new_value in field_updates:
        old_value = getattr(model_to_update, field, None)
        if old_value != new_value:
            if enable_none_updates or new_value is not None:
                setattr(model_to_update, field, new_value)
                has_changes = True
                if field in logging_on_fields:
                    update_logs += f" Updated {field} from {old_value} to {new_value}."

    if has_changes:
        model_to_update.save()
        fk_field = getattr(log_model, "fk_name", None)
        log_kwargs = {fk_field: model_to_update, "logs": update_logs}
        log_model.objects.create(**log_kwargs)

    return model_to_update


def upsert_with_logs(
    model: type[T],
    log_model: type[L],
    lookup_kwargs: dict,  # Polymorphic: lookup keys vary by model (abstract helper).
    updates: dict,  # Polymorphic: field keys vary by model (abstract helper).
    logging_on_fields: list[str] = [],
    none_skip_fields: list[str] = [],
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs if exists, or create entity in database.

    Concurrent creates are safe when the model has a matching uniqueness
    constraint on ``lookup_kwargs``: a lost race raises IntegrityError and
    returns the row already written by the other process.
    """
    try:
        model_to_update = model.objects.get(**lookup_kwargs)
        return update_with_logs(
            model_to_update=model_to_update,
            log_model=log_model,
            updates=updates,
            logging_on_fields=logging_on_fields,
            none_skip_fields=none_skip_fields,
            enable_none_updates=enable_none_updates,
        )
    except NotFound:
        # BaseManager.get maps a missing row to DRF NotFound.
        create_data = {
            **lookup_kwargs,
            **{k: v for k, v in updates.items() if k != "logs"},
        }
        try:
            with transaction.atomic():
                return model.objects.create(**create_data)
        except IntegrityError:
            # Another process won the insert — leave their row unchanged.
            return model.objects.get(**lookup_kwargs)


def convert_query_to_dictionary_list(
    queryset: QuerySet,
    remove_foreign_key: bool = False,
    remove_auto_fields: bool = True,
    remove_cache_fields: bool = True,
    remove_specific_fields: list[str] = [],
) -> list[dict]:  # Polymorphic: wraps convert_to_dict until per-model TypedDicts exist.
    """Convert a query into a List of Dictionary."""
    return [
        object.convert_to_dict(
            remove_foreign_key,
            remove_auto_fields,
            remove_cache_fields,
            remove_specific_fields,
        )
        for object in queryset
    ]


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
    ``naive_timezone`` when given (source wall clock, e.g. America/New_York for
    US releases); otherwise they are treated as UTC. See ``docs/GUIDELINES.md``.
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


def get_source_timezone(location_code: str) -> ZoneInfo:
    """Return the source wall-clock zone for a location code (e.g. US → New York)."""
    timezone_name = SOURCE_TIMEZONE_BY_LOCATION_CODE.get(location_code)
    if timezone_name is None:
        raise ValueError(f"No source timezone mapped for location {location_code!r}")
    return ZoneInfo(timezone_name)


def convert_local_wall_time_to_utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    *,
    source_timezone: str | ZoneInfo,
) -> datetime:
    """Interpret a source-local civil time and return the matching UTC instant.

    Use at ingest when a calendar publishes a wall clock in a known zone
    (e.g. FOMC 14:00 America/New_York) but storage must be UTC-aware.
    """
    source_zone = (
        ZoneInfo(source_timezone)
        if isinstance(source_timezone, str)
        else source_timezone
    )
    local_datetime = datetime(year, month, day, hour, minute, tzinfo=source_zone)
    return local_datetime.astimezone(timezone.utc)


def _get_display_timezone() -> ZoneInfo:
    """Return the display zone (``TIME_ZONE``, Europe/Paris).

    Use when you need the zone object itself. For a datetime or calendar date,
    prefer ``convert_to_display_timezone`` / ``get_local_today``.
    """
    return ZoneInfo(settings.TIME_ZONE)


def convert_to_display_timezone(value: datetime) -> datetime:
    """Convert a datetime instant to Europe/Paris (keeps the same moment).

    Use for UI clocks (``strftime`` times/date chips). Naive values are assumed
    UTC. Prefer storing UTC-aware datetimes; this is a display-edge helper only.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_get_display_timezone())


def get_local_today() -> date:
    """Return today's calendar date in Europe/Paris (no clock time).

    Use for filters and week focus (``DateField`` / date comparisons). Distinct
    from ``convert_to_display_timezone``, which returns a full datetime.
    """
    return dj_timezone.localdate()
