"""Cache computed economic and sector-analysis display payloads in Redis."""

import hashlib
from datetime import date
from enum import Enum
from typing import TypeVar

from django.db.models import Count, Max
from pydantic import TypeAdapter

from core.services.cache import UI_CACHE_TTL_SECONDS, get_cached_json, set_cached_json
from economic_overview.models.economic_indicators import (
    EconomicDataModel,
    EconomicIndicatorInformationModel,
)
from market_overview.models.common import LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel
from market_overview.models.sector_analysis import IndexSubsectorDailyMoveModel

_ECONOMIC_KEY_PREFIX = "data_visualization:economic_display"
_SECTOR_ANALYSIS_KEY_PREFIX = "data_visualization:sector_analysis_page"
_TTL_SECONDS = UI_CACHE_TTL_SECONDS
_ECONOMIC_LOG_LABEL = "Economic display cache"
_SECTOR_ANALYSIS_LOG_LABEL = "Sector analysis page cache"

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
    return f"{_ECONOMIC_KEY_PREFIX}:{cache_type.value}:{version}:{fingerprint_digest}"


def get_cached_economic_display(
    cache_type: EconomicDisplayCacheType,
    fingerprint: str,
    adapter: TypeAdapter[T],
) -> T | None:
    """Fetch and validate a cached economic display payload."""
    return get_cached_json(
        _format_economic_display_cache_key(cache_type, fingerprint),
        adapter,
        log_label=_ECONOMIC_LOG_LABEL,
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
        log_label=_ECONOMIC_LOG_LABEL,
    )


def get_cache_version_for_sector_analysis_page() -> str:
    """Build a cache version stamp from sector-move / earnings table state.

    When ingestion upserts moves or the earnings watchlist changes, the stamp
    changes and old Redis keys miss without an explicit invalidate call.
    """
    move_stats = IndexSubsectorDailyMoveModel.objects.aggregate(
        move_count=Count("id"),
        latest_id=Max("id"),
        latest_date=Max("date"),
        latest_modified=Max("last_modified"),
    )
    earnings_stats = EarningsWatchlistModel.objects.aggregate(
        watchlist_count=Count("id"),
        latest_modified=Max("last_modified"),
    )
    move_modified = move_stats["latest_modified"]
    move_modified_token = (
        move_modified.isoformat() if move_modified is not None else "none"
    )
    latest_date = move_stats["latest_date"]
    latest_date_token = latest_date.isoformat() if latest_date is not None else "none"
    earnings_modified = earnings_stats["latest_modified"]
    earnings_modified_token = (
        earnings_modified.isoformat() if earnings_modified is not None else "none"
    )
    return (
        f"moves{move_stats['move_count']}:"
        f"id{move_stats['latest_id'] or 0}:"
        f"date{latest_date_token}:"
        f"mod{move_modified_token}:"
        f"earn{earnings_stats['watchlist_count']}:"
        f"earnmod{earnings_modified_token}"
    )


def _format_sector_analysis_page_cache_key(
    location: LocationChoices, as_of: date
) -> str:
    """Build a Redis key for one sector-analysis page payload."""
    fingerprint = f"{location.value}|{as_of.isoformat()}"
    fingerprint_digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]
    version = get_cache_version_for_sector_analysis_page()
    return f"{_SECTOR_ANALYSIS_KEY_PREFIX}:{version}:{fingerprint_digest}"


def get_cached_sector_analysis_page(
    location: LocationChoices,
    as_of: date,
    adapter: TypeAdapter[T],
) -> T | None:
    """Fetch and validate a cached sector-analysis page payload."""
    return get_cached_json(
        _format_sector_analysis_page_cache_key(location, as_of),
        adapter,
        log_label=_SECTOR_ANALYSIS_LOG_LABEL,
    )


def set_cached_sector_analysis_page(
    location: LocationChoices,
    as_of: date,
    payload: T,
) -> None:
    """Store a computed sector-analysis page payload in Redis."""
    set_cached_json(
        _format_sector_analysis_page_cache_key(location, as_of),
        payload,
        _TTL_SECONDS,
        log_label=_SECTOR_ANALYSIS_LOG_LABEL,
    )
