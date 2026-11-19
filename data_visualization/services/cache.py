"""Redis cache for computed economic recap / charts display payloads."""

import hashlib
from enum import Enum
from typing import TypeVar

from django.db.models import Count, Max
from pydantic import TypeAdapter

from core.services.cache import CACHE_TTL_SECONDS, get_cached_json, set_cached_json
from economic_overview.models.economic_indicators import (
    EconomicDataModel,
    EconomicIndicatorInformationModel,
)

_KEY_PREFIX = "data_visualization:economic_display"
_TTL_SECONDS = CACHE_TTL_SECONDS
_LOG_LABEL = "Economic display cache"

T = TypeVar("T")


class EconomicDisplayCacheType(str, Enum):
    """Redis namespace for economic display payload caches."""

    CHARTS = "charts"
    RECAP = "recap"


def get_cache_version_for_economic_display() -> str:
    """Build a cache version stamp from indicator / economic-data table state.

    When economic data is ingested or indicators are reseeded, the stamp changes
    and old Redis keys miss without an explicit invalidate call. Code-only
    payload shape changes rely on the normal TTL instead.
    """
    economic_data_stats = EconomicDataModel.objects.aggregate(
        value_count=Count("id"),
        latest_id=Max("id"),
        latest_modified=Max("last_modified"),
    )
    indicator_stats = EconomicIndicatorInformationModel.objects.aggregate(
        indicator_count=Count("id"),
        latest_modified=Max("last_modified"),
    )
    latest_modified = economic_data_stats["latest_modified"]
    latest_token = (
        latest_modified.isoformat() if latest_modified is not None else "none"
    )
    indicator_modified = indicator_stats["latest_modified"]
    indicator_modified_token = (
        indicator_modified.isoformat() if indicator_modified is not None else "none"
    )
    latest_id = economic_data_stats["latest_id"]
    return (
        f"ind{indicator_stats['indicator_count']}:"
        f"indmod{indicator_modified_token}:"
        f"vals{economic_data_stats['value_count']}:"
        f"id{latest_id or 0}:{latest_token}"
    )


def _format_economic_display_cache_key(
    cache_type: EconomicDisplayCacheType, fingerprint: str
) -> str:
    """Build a Redis key for one computed economic display payload."""
    fingerprint_digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]
    version = get_cache_version_for_economic_display()
    return f"{_KEY_PREFIX}:{cache_type.value}:{version}:{fingerprint_digest}"


def get_cached_economic_display(
    cache_type: EconomicDisplayCacheType,
    fingerprint: str,
    adapter: TypeAdapter[T],
) -> T | None:
    """Fetch and validate a cached economic display payload."""
    return get_cached_json(
        _format_economic_display_cache_key(cache_type, fingerprint),
        adapter,
        log_label=_LOG_LABEL,
    )


def set_cached_economic_display(
    cache_type: EconomicDisplayCacheType,
    fingerprint: str,
    payload: T,
) -> None:
    """Store a computed economic display payload in Redis."""
    set_cached_json(
        _format_economic_display_cache_key(cache_type, fingerprint),
        payload,
        _TTL_SECONDS,
        log_label=_LOG_LABEL,
    )
