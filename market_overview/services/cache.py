"""Redis cache for earnings watchlist GET payloads."""

import hashlib
from typing import TypeVar

from django.db.models import Count, Max
from pydantic import TypeAdapter

from core.services.cache import UI_CACHE_TTL_SECONDS, get_cached_json, set_cached_json
from market_overview.models.common import LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel

_KEY_PREFIX = "market_overview:earnings_watchlist_companies"
_TTL_SECONDS = UI_CACHE_TTL_SECONDS
_LOG_LABEL = "Earnings watchlist companies cache"

T = TypeVar("T")


def get_cache_version_for_earnings_watchlist() -> str:
    """Build a cache version stamp from earnings-watchlist table state."""
    earnings_stats = EarningsWatchlistModel.objects.aggregate(
        watchlist_count=Count("id"),
        latest_id=Max("id"),
        latest_modified=Max("last_modified"),
    )
    latest_modified = earnings_stats["latest_modified"]
    latest_modified_token = (
        latest_modified.isoformat() if latest_modified is not None else "none"
    )
    return (
        f"watchlists{earnings_stats['watchlist_count']}:"
        f"id{earnings_stats['latest_id'] or 0}:"
        f"mod{latest_modified_token}"
    )


def _format_earnings_watchlist_companies_cache_key(location: LocationChoices) -> str:
    """Build a Redis key for one region's earnings watchlist companies payload."""
    fingerprint_digest = hashlib.sha256(location.value.encode("utf-8")).hexdigest()[:32]
    version = get_cache_version_for_earnings_watchlist()
    return f"{_KEY_PREFIX}:{version}:{fingerprint_digest}"


def get_cached_earnings_watchlist_companies(
    location: LocationChoices,
    adapter: TypeAdapter[T],
) -> T | None:
    """Fetch and validate cached earnings watchlist companies for one region."""
    return get_cached_json(
        _format_earnings_watchlist_companies_cache_key(location),
        adapter,
        log_label=_LOG_LABEL,
    )


def set_cached_earnings_watchlist_companies(
    location: LocationChoices,
    payload: T,
) -> None:
    """Store earnings watchlist companies for one region in Redis."""
    set_cached_json(
        _format_earnings_watchlist_companies_cache_key(location),
        payload,
        _TTL_SECONDS,
        log_label=_LOG_LABEL,
    )
