"""Tests for Redis-backed central-bank probability matrix caching."""

from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.cache import (
    build_probability_matrix_cache_fingerprint,
    build_probability_matrix_cache_key,
    get_cached_probability_matrix,
    set_cached_probability_matrix,
)
from central_banks_overview.services.central_banks_inference import (
    CentralBankProbabilityMatrix,
    _ProbabilitiesByStep,
)


class TestProbabilityMatrixCache(TestCase):
    """Tests for probability-matrix Redis helpers."""

    def setUp(self):
        """Create a STIR futures row used in fingerprint tests."""
        self.future_price = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="Z5",
            first_accrual_date=date(2025, 12, 17),
            last_accrual_date=date(2026, 3, 17),
            date=date(2025, 12, 15),
            price=97.5,
            source=StirFuturesSourceChoices.YAHOO,
        )

    def test_build_probability_matrix_cache_fingerprint_is_stable(self):
        """
        GIVEN the same bank, date, meetings, rate, and futures inputs
        WHEN building a cache fingerprint twice
        THEN both fingerprints match
        """
        meeting_dates = [datetime(2026, 1, 22, 13, 15, tzinfo=timezone.utc)]
        first_fingerprint = build_probability_matrix_cache_fingerprint(
            CentralBankChoices.ECB,
            date(2025, 12, 15),
            meeting_dates,
            2.0,
            [self.future_price],
        )
        second_fingerprint = build_probability_matrix_cache_fingerprint(
            CentralBankChoices.ECB,
            date(2025, 12, 15),
            meeting_dates,
            2.0,
            [self.future_price],
        )
        assert first_fingerprint == second_fingerprint
        assert first_fingerprint.startswith("ECB|2025-12-15|")

    def test_build_probability_matrix_cache_key_uses_digest(self):
        """
        GIVEN a fingerprint string
        WHEN building a Redis key
        THEN the key uses the probability-matrix prefix and a digest
        """
        key = build_probability_matrix_cache_key("ECB|2025-12-15|probe")
        assert key.startswith("central_banks_overview:probability_matrix:")
        assert len(key.split(":")[-1]) == 32

    @patch("core.cache.get_redis_client")
    def test_set_and_get_cached_probability_matrix(self, mock_get_redis_client):
        """
        GIVEN a Redis client that stores setex values
        WHEN setting then getting a probability matrix
        THEN the validated payload is returned
        """
        stored: dict[str, str] = {}

        class FakeRedis:
            """Minimal Redis stand-in for setex / get."""

            def setex(self, key: str, _ttl: int, value: str) -> None:
                """Store a value under key."""
                stored[key] = value

            def get(self, key: str) -> str | None:
                """Return a previously stored value."""
                return stored.get(key)

        mock_get_redis_client.return_value = FakeRedis()
        payload = CentralBankProbabilityMatrix(
            central_bank=CentralBankChoices.ECB,
            meeting_dates=[date(2026, 1, 22)],
            probability_matrix=[
                _ProbabilitiesByStep(expected_rate_step=0, probabilities=[0.6]),
                _ProbabilitiesByStep(expected_rate_step=-25, probabilities=[0.4]),
            ],
        )

        set_cached_probability_matrix("ecb-probe", payload)
        result = get_cached_probability_matrix("ecb-probe")

        assert result == payload
        assert stored
