"""Redis cache for computed central-bank probability matrices."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from central_banks_overview.models import CentralBankChoices, StirFuturesModel
from core.cache import CACHE_TTL_SECONDS, get_cached_json, set_cached_json

if TYPE_CHECKING:
    from central_banks_overview.services.central_banks_inference import (
        CentralBankProbabilityMatrix,
    )

_KEY_PREFIX = "central_banks_overview:probability_matrix"
_TTL_SECONDS = CACHE_TTL_SECONDS
_LOG_LABEL = "Probability matrix cache"


def build_probability_matrix_cache_fingerprint(
    central_bank: CentralBankChoices,
    target_date: date,
    meeting_dates: list[datetime],
    initial_base_rate: float,
    future_prices: list[StirFuturesModel],
) -> str:
    """Build a fingerprint from the inputs that determine a probability matrix."""
    meeting_tokens = [
        (
            meeting_date.date().isoformat()
            if isinstance(meeting_date, datetime)
            else meeting_date.isoformat()
        )
        for meeting_date in meeting_dates
    ]
    future_price_tokens = [
        (
            f"{future_price.short_name}:"
            f"{future_price.maturity or ''}:"
            f"{future_price.date.isoformat()}:"
            f"{future_price.price}"
        )
        for future_price in sorted(
            future_prices,
            key=lambda row: (row.short_name, row.maturity or "", row.date.isoformat()),
        )
    ]
    return (
        f"{central_bank.value}|{target_date.isoformat()}|"
        f"{','.join(meeting_tokens)}|{initial_base_rate}|"
        f"{','.join(future_price_tokens)}"
    )


def build_probability_matrix_cache_key(fingerprint: str) -> str:
    """Build a Redis key for one computed probability matrix."""
    fingerprint_digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]
    return f"{_KEY_PREFIX}:{fingerprint_digest}"


def get_cached_probability_matrix(
    fingerprint: str,
) -> CentralBankProbabilityMatrix | None:
    """Fetch and validate a cached probability matrix."""
    # Circular: cache ↔ central_banks_inference (TypedDict lives on inference).
    from central_banks_overview.services.central_banks_inference import (
        CentralBankProbabilityMatrix as ProbabilityMatrixPayload,
    )

    return get_cached_json(
        build_probability_matrix_cache_key(fingerprint),
        TypeAdapter(ProbabilityMatrixPayload),
        log_label=_LOG_LABEL,
    )


def set_cached_probability_matrix(
    fingerprint: str,
    payload: CentralBankProbabilityMatrix,
) -> None:
    """Store a computed probability matrix in Redis."""
    set_cached_json(
        build_probability_matrix_cache_key(fingerprint),
        payload,
        _TTL_SECONDS,
        log_label=_LOG_LABEL,
    )
