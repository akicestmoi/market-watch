"""Shared Redis client, JSON cache helpers, and TTL defaults."""

import json
from functools import lru_cache
from typing import TypeVar

import redis
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from core.services import logger

# Used by @ttl_cache decorators and Redis JSON caches for consistent TTLs.
CACHE_MAXSIZE = 128  # Maximum number of cached entries per function
CACHE_TTL_SECONDS = 10 * 60  # Time-to-live: 10 minutes (600 seconds)

CachedPayloadT = TypeVar("CachedPayloadT")


@lru_cache(maxsize=2)
def get_redis_client(*, decode_responses: bool = False) -> redis.Redis:
    """Return a shared Redis client for ``CELERY_BROKER_URL``.

    One client is memoized per ``decode_responses`` value. Use
    ``decode_responses=True`` for JSON/string caches; leave False for binary
    lock tokens (``core.locks``).
    """
    redis_client = redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=decode_responses,
    )
    if not redis_client:
        raise ValueError("Failed to create Redis client")
    return redis_client


def get_cached_json(
    key: str,
    adapter: TypeAdapter[CachedPayloadT],
    *,
    log_label: str = "Redis JSON cache",
) -> CachedPayloadT | None:
    """Fetch a Redis JSON string and validate it with ``adapter``.

    Returns ``None`` on miss, Redis errors, or invalid payloads.
    """
    try:
        client = get_redis_client(decode_responses=True)
        raw = client.get(key)
    except Exception as exc:
        logger.warning("%s get failed: %s", log_label, exc)
        return None
    if raw is None:
        return None
    assert isinstance(
        raw, str
    ), f"Expected str from Redis GET, got {type(raw).__name__}"
    try:
        return adapter.validate_python(json.loads(raw))
    except (TypeError, json.JSONDecodeError, ValidationError) as exc:
        logger.warning("%s payload invalid: %s", log_label, exc)
        return None


def set_cached_json(
    key: str,
    payload: CachedPayloadT,
    ttl_seconds: int,
    *,
    log_label: str = "Redis JSON cache",
) -> None:
    """Store ``payload`` as JSON under ``key`` with ``ttl_seconds``."""
    try:
        client = get_redis_client(decode_responses=True)
        client.setex(
            key,
            ttl_seconds,
            json.dumps(payload, ensure_ascii=False, default=str),
        )
    except Exception as exc:
        logger.warning("%s set failed: %s", log_label, exc)
