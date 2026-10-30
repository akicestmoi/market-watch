"""Redis cache for computed economic recap / charts display payloads."""

import hashlib
from enum import Enum
from typing import TypeVar

from django.db.models import Count, Max
from pydantic import TypeAdapter

from core.cache import CACHE_TTL_SECONDS, get_cached_json, set_cached_json
from economic_overview.models import (
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


def get_economic_display_cache_version() -> str:
    """Build a cache version stamp from indicator / observation table state.

    When rows are ingested or indicators reseeded, the stamp changes and old
    Redis keys miss without an explicit invalidate call.
    """
    observation_stats = EconomicDataModel.objects.aggregate(
        row_count=Count("id"),
        latest_id=Max("id"),
        latest_modified=Max("last_modified"),
    )
    indicator_count = EconomicIndicatorInformationModel.objects.count()
    latest_modified = observation_stats["latest_modified"]
    latest_token = (
        latest_modified.isoformat() if latest_modified is not None else "none"
    )
    latest_id = observation_stats["latest_id"]
    return (
        f"ind{indicator_count}:obs{observation_stats['row_count']}:"
        f"id{latest_id or 0}:{latest_token}"
    )


def build_economic_display_cache_key(
    cache_type: EconomicDisplayCacheType, fingerprint: str
) -> str:
    """Build a Redis key for one computed economic display payload."""
    fingerprint_digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]
    version = get_economic_display_cache_version()
    return f"{_KEY_PREFIX}:{cache_type.value}:{version}:{fingerprint_digest}"


def get_cached_economic_display(
    cache_type: EconomicDisplayCacheType,
    fingerprint: str,
    adapter: TypeAdapter[T],
) -> T | None:
    """Fetch and validate a cached economic display payload."""
    return get_cached_json(
        build_economic_display_cache_key(cache_type, fingerprint),
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
        build_economic_display_cache_key(cache_type, fingerprint),
        payload,
        _TTL_SECONDS,
        log_label=_LOG_LABEL,
    )
