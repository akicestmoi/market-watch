"""Generic Redis distributed locks."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import redis
from django.conf import settings
from rest_framework.exceptions import APIException

from core.services import logger

DEFAULT_LOCK_TIMEOUT_SECONDS = 30 * 60


class ResourceLocked(APIException):
    """Raised when a Redis lock could not be acquired."""

    status_code = 409
    default_detail = "Resource is already locked."
    default_code = "resource_locked"


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.CELERY_BROKER_URL)


@contextmanager
def redis_lock(
    key: str,
    *,
    timeout: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
    raise_if_locked: bool = True,
    locked_detail: Optional[str] = None,
) -> Iterator[bool]:
    """Acquire a Redis lock for ``key``.

    Yields ``True`` when acquired. If the lock is held elsewhere: raises
    ``ResourceLocked`` when ``raise_if_locked`` is True, otherwise yields
    ``False``.
    """
    client = _redis_client()
    lock = client.lock(key, timeout=timeout, blocking_timeout=0)
    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.warning("Could not acquire Redis lock for key=%s", key)
        if raise_if_locked:
            raise ResourceLocked(
                detail=locked_detail or f"Resource is already locked ({key})."
            )
        yield False
        return

    try:
        yield True
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            logger.warning(
                "Could not release Redis lock for key=%s "
                "(expired or already released).",
                key,
            )


def try_acquire_redis_lock(
    key: str,
    timeout: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
):
    """Non-context acquire for callers that release explicitly (e.g. Celery)."""
    client = _redis_client()
    lock = client.lock(key, timeout=timeout, blocking_timeout=0)
    if lock.acquire(blocking=False):
        return lock
    return None


@contextmanager
def redis_locks(
    keys: list[str],
    *,
    timeout: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
    raise_if_locked: bool = True,
    locked_detail: Optional[str] = None,
) -> Iterator[bool]:
    """Acquire multiple Redis locks (sorted for stable ordering)."""
    unique_keys = sorted(set(keys))
    acquired_locks = []
    try:
        for key in unique_keys:
            lock = try_acquire_redis_lock(key, timeout=timeout)
            if lock is None:
                logger.warning("Could not acquire Redis lock for key=%s", key)
                if raise_if_locked:
                    raise ResourceLocked(
                        detail=locked_detail or f"Resource is already locked ({key})."
                    )
                yield False
                return
            acquired_locks.append(lock)
        yield True
    finally:
        for lock in reversed(acquired_locks):
            try:
                lock.release()
            except redis.exceptions.LockError:
                logger.warning("Could not release one of the Redis locks.")
