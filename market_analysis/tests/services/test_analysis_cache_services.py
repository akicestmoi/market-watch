"""Tests for analysis_cache_services."""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase

from market_analysis.llm.config import PROMPT_VERSION
from market_analysis.services import analysis_cache_services
from market_analysis.services.llm_market_recap_services import AnalyzedArticle


def _sample_analyzed() -> AnalyzedArticle:
    return AnalyzedArticle(
        title="t",
        summary="s",
        event_types=["MACRO"],
        companies=["Acme"],
        sectors=["Tech"],
        sentiment="NEUTRAL",
        key_facts=["f1"],
        uncertainties=[],
        source_url="https://example.com/a",
    )


class AnalysisCacheServicesTests(TestCase):
    @patch("market_analysis.services.analysis_cache_services._get_redis_client")
    def test_set_get_list_roundtrip(self, mock_redis_factory):
        """
        GIVEN a mocked Redis client and an analyzed article
        WHEN the analysis is cached then fetched and listed
        THEN the stored payload matches the article and prompt version
        """
        store: dict = {}
        index: set = set()

        client = MagicMock()

        def setex(key, ttl, value):
            store[key] = value

        def get(key):
            return store.get(key)

        def sadd(key, member):
            index.add(member)

        def smembers(key):
            return {m.encode() if isinstance(m, str) else m for m in index}

        def expire(key, ttl):
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
        analysis_cache_services.set_cached_analysis(
            day, article, source_url=article["source_url"]
        )
        key = analysis_cache_services._build_entry_key(day, article["source_url"])
        assert key in store

        got = analysis_cache_services.get_cached_analysis(day, article["source_url"])
        assert got is not None
        assert got["source_url"] == article["source_url"]
        assert got["analysis"]["title"] == "t"
        assert got["prompt_version"] == PROMPT_VERSION

        listed = analysis_cache_services.list_cached_analyses(day)
        assert listed["count"] == 1
        assert listed["items"][0]["analysis"]["companies"] == ["Acme"]
