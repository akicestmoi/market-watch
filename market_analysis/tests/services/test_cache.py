"""Tests for market analysis Redis cache helpers."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase
from freezegun import freeze_time

from market_analysis.llm.config import PROMPT_VERSION
from market_analysis.llm.schemas import EventType, Sentiment
from market_analysis.services import cache
from market_analysis.services.cache import (
    ARTICLE_CACHE_TTL_SECONDS,
    _CachedAnalysesListResult,
    _CachedAnalysisPayload,
)
from market_analysis.services.llm_market_recap import AnalyzedArticle

_FREEZE_TIME = datetime(2025, 12, 12, 15, 30, 0, tzinfo=timezone.utc)


def _sample_analyzed() -> AnalyzedArticle:
    """Return a sample AnalyzedArticle for cache tests."""
    return AnalyzedArticle(
        title="t",
        summary="s",
        event_types=[EventType.MACRO],
        companies=["Acme"],
        sectors=["Tech"],
        sentiment=Sentiment.NEUTRAL,
        key_facts=["f1"],
        uncertainties=[],
        source_url="https://example.com/a",
    )


class AnalysisCacheServicesTests(TestCase):
    """Tests for article-analysis Redis cache helpers."""

    @freeze_time(_FREEZE_TIME)
    @patch("market_analysis.services.cache.get_redis_client")
    @patch("core.cache.get_redis_client")
    def test_set_get_list_roundtrip(self, mock_core_redis, mock_local_redis):
        """
        GIVEN a mocked Redis client and an analyzed article
        WHEN the analysis is cached then fetched and listed
        THEN the stored payload matches the article and prompt version
        """
        store: dict[str, str] = {}
        index: set[str] = set()

        client = MagicMock()

        def setex(key, ttl, value):
            """Store a value under key in the fake Redis store."""
            store[key] = value

        def get(key):
            """Return a value from the fake Redis store by key."""
            return store.get(key)

        def sadd(key, member):
            """Add a member to the fake Redis set index."""
            index.add(member)

        def smembers(key):
            """Return members of the fake Redis set index as strings."""
            return set(index)

        def expire(key, ttl):
            """No-op expire that always succeeds for the fake Redis client."""
            return True

        pipe = MagicMock()
        pipe.setex.side_effect = lambda *a, **k: setex(*a, **k)
        pipe.sadd.side_effect = lambda *a, **k: sadd(*a, **k)
        pipe.expire.side_effect = lambda *a, **k: expire(*a, **k)
        pipe.execute.return_value = []
        client.pipeline.return_value = pipe
        client.get.side_effect = get
        client.smembers.side_effect = smembers
        mock_core_redis.return_value = client
        mock_local_redis.return_value = client

        day = date(2025, 12, 12)
        article = _sample_analyzed()
        expected_payload = _CachedAnalysisPayload(
            source_url=article["source_url"],
            cached_at=_FREEZE_TIME.isoformat(),
            prompt_version=PROMPT_VERSION,
            analysis=article,
        )
        cache.set_cached_analysis(day, article, source_url=article["source_url"])
        key = cache._build_entry_key(day, article["source_url"])
        assert key in store

        got = cache.get_cached_analysis(day, article["source_url"])
        assert got == expected_payload

        listed = cache.list_cached_analyses(day)
        assert listed == _CachedAnalysesListResult(
            reporting_date=day.isoformat(),
            prompt_version=PROMPT_VERSION,
            ttl_seconds=ARTICLE_CACHE_TTL_SECONDS,
            count=1,
            items=[expected_payload],
        )
