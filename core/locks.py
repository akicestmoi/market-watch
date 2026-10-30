"""Generic Redis distributed locks."""

import atexit
import os
import signal
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import FrameType

import redis
import redis.lock
from redis.exceptions import LockError
from rest_framework.exceptions import APIException

from core.cache import get_redis_client
from core.services import logger

DEFAULT_LOCK_TIMEOUT_SECONDS = 30 * 60

# Usage of dict: keys are runtime Redis lock key strings held by this process.
_held_lock_tokens: dict[str, bytes] = {}
_termination_handlers_installed = False


def _get_lock_token(lock: redis.lock.Lock) -> bytes | None:
    """Return the ownership token for ``lock``, if any."""
    token = getattr(lock.local, "token", None)
    if token is None:
        return None
    if isinstance(token, bytes):
        return token
    return str(token).encode()


def _unregister_held_lock(key: str) -> None:
    """Stop tracking a lock after a normal release."""
    _held_lock_tokens.pop(key, None)


def _force_delete_lock_if_token_matches(key: str, token: bytes) -> bool:
    """Delete ``key`` only when Redis still holds our ``token``."""
    client = get_redis_client()
    current = client.get(key)
    if current == token:
        client.delete(key)
        return True
    return False


def release_redis_lock(lock: redis.lock.Lock, key: str) -> None:
    """Release ``lock``; force-delete ``key`` if we still own the token.

    Use after ``try_acquire_redis_lock`` (Celery tasks) and from context managers
    so ingestion errors / LockError / flaky Redis still clear our lock.
    """
    token = _get_lock_token(lock)
    try:
        lock.release()
        _unregister_held_lock(key)
        return
    except LockError:
        logger.warning(
            "Could not release Redis lock for key=%s " "(expired or already released).",
            key,
        )
    except Exception as exc:
        logger.warning("Error releasing Redis lock for key=%s: %s", key, exc)

    if token is not None:
        try:
            if _force_delete_lock_if_token_matches(key, token):
                logger.warning(
                    "Force-cleared Redis lock key=%s after failed release.", key
                )
        except Exception as exc:
            logger.warning("Could not force-clear Redis lock key=%s: %s", key, exc)
    _unregister_held_lock(key)


class ResourceLocked(APIException):
    """Raised when a Redis lock could not be acquired."""

    status_code = 409
    default_detail = "Resource is already locked."
    default_code = "resource_locked"


SignalHandler = Callable[[int, FrameType | None], None] | int | signal.Handlers | None


def _release_held_locks_on_exit() -> None:
    """Best-effort clear of locks still held when the process exits."""
    if not _held_lock_tokens:
        return
    for key, token in list(_held_lock_tokens.items()):
        try:
            if _force_delete_lock_if_token_matches(key, token):
                logger.warning(
                    "Cleared Redis lock key=%s on process exit "
                    "(likely interrupted mid-critical-section).",
                    key,
                )
        except Exception as exc:
            logger.warning(
                "Could not clear Redis lock key=%s on process exit: %s", key, exc
            )
    _held_lock_tokens.clear()


def _handle_termination_signal(
    signum: int, frame: FrameType | None, previous: SignalHandler
) -> None:
    """Release held locks, then defer to the previous SIGTERM/SIGINT handler."""
    _release_held_locks_on_exit()
    if callable(previous):
        previous(signum, frame)
        return
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def _ensure_termination_handlers() -> None:
    """Install once-per-process handlers so autoreload/SIGTERM clears locks."""
    global _termination_handlers_installed
    if _termination_handlers_installed:
        return
    atexit.register(_release_held_locks_on_exit)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            previous: SignalHandler = signal.getsignal(sig)
            signal.signal(
                sig,
                lambda signum, frame, previous=previous: _handle_termination_signal(
                    signum, frame, previous
                ),
            )
        except (ValueError, OSError):
            # Not the main thread / signals unavailable (e.g. some worker setups).
            pass
    _termination_handlers_installed = True


def _register_held_lock(key: str, token: bytes) -> None:
    """Track a lock held by this process for emergency release on exit."""
    _held_lock_tokens[key] = token
    _ensure_termination_handlers()


def try_acquire_redis_lock(
    key: str,
    timeout: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> redis.lock.Lock | None:
    """Non-context acquire for callers that release explicitly (e.g. Celery)."""
    client = get_redis_client()
    lock = client.lock(key, timeout=timeout, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return None
    token = _get_lock_token(lock)
    if token is not None:
        _register_held_lock(key, token)
    return lock


@contextmanager
def acquire_redis_lock(
    key: str,
    *,
    timeout: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
    raise_if_locked: bool = True,
    locked_detail: str | None = None,
) -> Iterator[bool]:
    """Acquire a Redis lock for ``key``.

    Yields ``True`` when acquired. If the lock is held elsewhere: raises
    ``ResourceLocked`` when ``raise_if_locked`` is True, otherwise yields
    ``False``.

    Always releases on exit (success, exception, or ingestion error). Process
    termination (e.g. Django autoreload SIGTERM) also clears locks we still own.
    """
    client = get_redis_client()
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

    token = _get_lock_token(lock)
    if token is not None:
        _register_held_lock(key, token)

    try:
        yield True
    finally:
        release_redis_lock(lock, key)


@contextmanager
def acquire_redis_locks(
    keys: list[str],
    *,
    timeout: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
    raise_if_locked: bool = True,
    locked_detail: str | None = None,
) -> Iterator[bool]:
    """Acquire multiple Redis locks (sorted for stable ordering)."""
    unique_keys = sorted(set(keys))
    acquired_locks: list[tuple[str, redis.lock.Lock]] = []
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
            acquired_locks.append((key, lock))
        yield True
    finally:
        for key, lock in reversed(acquired_locks):
            release_redis_lock(lock, key)
