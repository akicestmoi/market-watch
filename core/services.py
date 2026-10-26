"""Shared utilities (logging, HTML fetch helpers) used across apps."""

import logging
from datetime import date, datetime, timezone
from typing import TypeVar
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone as dj_timezone
from rest_framework.exceptions import NotFound

from .models import BaseLogModel, BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
L = TypeVar("L", bound=BaseLogModel)

# Cache configuration constants
# Used by @ttl_cache decorators across the codebase for consistent caching behavior
CACHE_MAXSIZE = 128  # Maximum number of cached entries per function
CACHE_TTL_SECONDS = 10 * 60  # Time-to-live: 10 minutes (600 seconds)


def get(model: type[T], *args, **kwargs) -> T:
    """Get entity from database."""
    try:
        return model.objects.get(*args, **kwargs)
    except ObjectDoesNotExist:
        raise NotFound(detail=f"No {model.__name__} found matching {kwargs}")


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
    except ObjectDoesNotExist:
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


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO / RFC-ish datetime string to UTC-aware datetime when possible.

    Naive inputs are treated as UTC (backend storage convention). See
    ``docs/GUIDELINES.md``.
    """
    if not value:
        return None
    try:
        parsed_datetime = date_parser.parse(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed_datetime.tzinfo is None:
        parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
    return parsed_datetime.astimezone(timezone.utc)


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
