"""Tests for Redis-backed economic display payload caching."""

from typing import TypedDict
from unittest.mock import patch

from django.test import TestCase
from pydantic import TypeAdapter

from data_visualization.services.cache import (
    EconomicDisplayCacheType,
    build_economic_display_cache_key,
    get_cached_economic_display,
    get_economic_display_cache_version,
    set_cached_economic_display,
)


class ChartCacheProbe(TypedDict):
    """Minimal payload shape used to probe Redis cache round-trips."""

    category: str
    label: str


_CHART_CACHE_PROBE_ADAPTER = TypeAdapter(list[ChartCacheProbe])


class TestEconomicDisplayCache(TestCase):
    """Tests for economic display Redis helpers."""

    @patch("core.cache.get_redis_client")
    def test_set_and_get_cached_economic_display(self, mock_get_redis_client):
        """
        GIVEN a Redis client that stores setex values
        WHEN setting then getting a typed payload
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
        payload: list[ChartCacheProbe] = [{"category": "Growth", "label": "GDP"}]

        set_cached_economic_display(
            EconomicDisplayCacheType.CHARTS, "us|5Y|GROWTH:GDP|YOY", payload
        )
        result = get_cached_economic_display(
            EconomicDisplayCacheType.CHARTS,
            "us|5Y|GROWTH:GDP|YOY",
            _CHART_CACHE_PROBE_ADAPTER,
        )

        assert result == payload
        assert stored

    @patch("core.cache.get_redis_client")
    def test_get_cached_economic_display_miss(self, mock_get_redis_client):
        """
        GIVEN Redis has no entry for the key
        WHEN getting a cached payload
        THEN None is returned
        """

        class FakeRedis:
            """Minimal Redis stand-in that always misses."""

            def get(self, _key: str) -> None:
                """Return a cache miss."""
                return None

        mock_get_redis_client.return_value = FakeRedis()

        result = get_cached_economic_display(
            EconomicDisplayCacheType.RECAP, "FR,JP,US", _CHART_CACHE_PROBE_ADAPTER
        )
        assert result is None

    def test_build_economic_display_cache_key_includes_version(self):
        """
        GIVEN the current economic table version stamp
        WHEN building a cache key
        THEN the key embeds that version and a fingerprint digest
        """
        version = get_economic_display_cache_version()
        key = build_economic_display_cache_key(EconomicDisplayCacheType.RECAP, "FR,US")
        assert version in key
        assert key.startswith("data_visualization:economic_display:recap:")
