"""Tests for analysis_cache."""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase

from market_analysis.llm.config import PROMPT_VERSION
from market_analysis.llm.schemas import EventType, Sentiment
from market_analysis.services import analysis_cache
from market_analysis.services.llm_market_recap import AnalyzedArticle


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
    """Tests for analysis_cache Redis cache helpers."""

    @patch("market_analysis.services.analysis_cache._get_redis_client")
    def test_set_get_list_roundtrip(self, mock_redis_factory):
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
        mock_redis_factory.return_value = client

        day = date(2025, 12, 12)
        article = _sample_analyzed()
        analysis_cache.set_cached_analysis(
            day, article, source_url=article["source_url"]
        )
        key = analysis_cache._build_entry_key(day, article["source_url"])
        assert key in store

        got = analysis_cache.get_cached_analysis(day, article["source_url"])
        assert got is not None
        assert got["source_url"] == article["source_url"]
        assert got["analysis"]["title"] == "t"
        assert got["prompt_version"] == PROMPT_VERSION

        listed = analysis_cache.list_cached_analyses(day)
        assert listed["count"] == 1
        assert listed["items"][0]["analysis"]["companies"] == ["Acme"]
