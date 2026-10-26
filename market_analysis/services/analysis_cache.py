"""Redis cache for same-day article analyses (keyed by URL + prompt version)."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, NotRequired, TypedDict
from urllib.parse import quote

import redis
from django.conf import settings
from django.utils import timezone as dj_timezone

from core.services import logger
from market_analysis.llm.config import PROMPT_VERSION
from market_analysis.llm.schemas import EventType, Sentiment

if TYPE_CHECKING:
    from market_analysis.services.llm_market_recap import AnalyzedArticle

ARTICLE_CACHE_TTL_SECONDS = 24 * 60 * 60
_KEY_PREFIX = "market_analysis:article_analysis"


class CachedAnalysisPayload(TypedDict):
    """Cached analysis payload dictionnary."""

    source_url: str
    cached_at: str
    prompt_version: str
    analysis: AnalyzedArticle


def _get_redis_client() -> redis.Redis:
    """Return a Redis client using the Celery broker URL."""
    redis_client = redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
    if not redis_client:
        raise ValueError("Failed to create Redis client")
    return redis_client


def _build_entry_key(reporting_date: date, source_url: str) -> str:
    """Build the Redis key for one article analysis entry."""
    return (
        f"{_KEY_PREFIX}:{reporting_date.isoformat()}:"
        f"{PROMPT_VERSION}:{quote(source_url.strip(), safe="")}"
    )


def _build_index_key(reporting_date: date) -> str:
    """Build the Redis set key listing cached URLs for a reporting date."""
    return f"{_KEY_PREFIX}:index:{reporting_date.isoformat()}:{PROMPT_VERSION}"


def _serialize_payload(article: AnalyzedArticle, source_url: str) -> str:
    """Serialize an analyzed article into a Redis cache payload JSON string."""
    payload = CachedAnalysisPayload(
        source_url=source_url,
        cached_at=dj_timezone.now().isoformat(),
        prompt_version=PROMPT_VERSION,
        analysis=article,
    )
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_payload(raw: str) -> CachedAnalysisPayload | None:
    """Parse a Redis cache payload; return None if invalid."""
    # Circular: analysis_cache ↔ llm_market_recap
    from market_analysis.services.llm_market_recap import AnalyzedArticle

    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "analysis" not in data:
        return None
    raw_analysis = data["analysis"]
    if not isinstance(raw_analysis, dict):
        return None
    source_url = str(data.get("source_url") or "")

    event_types_raw = raw_analysis.get("event_types")
    if not event_types_raw and raw_analysis.get("event_type"):
        event_types_raw = [raw_analysis["event_type"]]
    event_types: list[EventType] = []
    if isinstance(event_types_raw, list):
        for event_type in event_types_raw:
            try:
                event_types.append(EventType(str(event_type)))
            except ValueError:
                continue
    companies_raw = raw_analysis.get("companies")
    sectors_raw = raw_analysis.get("sectors")
    key_facts_raw = raw_analysis.get("key_facts")
    uncertainties_raw = raw_analysis.get("uncertainties")
    try:
        sentiment = Sentiment(str(raw_analysis.get("sentiment") or "NEUTRAL"))
    except ValueError:
        sentiment = Sentiment.NEUTRAL
    analysis = AnalyzedArticle(
        title=str(raw_analysis.get("title") or ""),
        summary=str(raw_analysis.get("summary") or ""),
        event_types=event_types,
        companies=(
            [str(item) for item in companies_raw]
            if isinstance(companies_raw, list)
            else []
        ),
        sectors=(
            [str(item) for item in sectors_raw] if isinstance(sectors_raw, list) else []
        ),
        sentiment=sentiment,
        key_facts=(
            [str(item) for item in key_facts_raw]
            if isinstance(key_facts_raw, list)
            else []
        ),
        uncertainties=(
            [str(item) for item in uncertainties_raw]
            if isinstance(uncertainties_raw, list)
            else []
        ),
        source_url=str(raw_analysis.get("source_url") or source_url or ""),
    )
    return CachedAnalysisPayload(
        source_url=source_url,
        cached_at=str(data.get("cached_at") or ""),
        prompt_version=str(data.get("prompt_version") or ""),
        analysis=analysis,
    )


def get_cached_analysis(
    reporting_date: date, source_url: str
) -> CachedAnalysisPayload | None:
    """Fetch one cached analysis by reporting date and article URL."""
    try:
        client = _get_redis_client()
        raw = client.get(_build_entry_key(reporting_date, source_url))
    except Exception as exc:
        logger.warning("Article analysis cache get failed: %s", exc)
        return None
    if raw is None:
        return None
    assert isinstance(
        raw, str
    ), f"Expected str from Redis GET, got {type(raw).__name__}"
    return _deserialize_payload(raw)


def set_cached_analysis(
    reporting_date: date,
    article: AnalyzedArticle,
    source_url: str,
) -> None:
    """Store an analysis digest keyed by reporting date and article URL."""
    try:
        client = _get_redis_client()
        key = _build_entry_key(reporting_date, source_url)
        index = _build_index_key(reporting_date)
        pipe = client.pipeline()
        pipe.setex(
            key,
            ARTICLE_CACHE_TTL_SECONDS,
            _serialize_payload(article, source_url=source_url),
        )
        pipe.sadd(index, source_url)
        pipe.expire(index, ARTICLE_CACHE_TTL_SECONDS)
        pipe.execute()
    except Exception as exc:
        logger.warning("Article analysis cache set failed: %s", exc)


class CachedAnalysesListResult(TypedDict):
    """Cached analyses list result dictionnary."""

    reporting_date: str
    prompt_version: str
    ttl_seconds: int
    count: int
    items: list[CachedAnalysisPayload]
    error: NotRequired[str]


def list_cached_analyses(
    reporting_date: date,
    source_url: str | None = None,
) -> CachedAnalysesListResult:
    """List or fetch cached article analyses for a reporting day."""
    try:
        client = _get_redis_client()
    except Exception as exc:
        logger.warning("Article analysis cache list failed: %s", exc)
        return CachedAnalysesListResult(
            reporting_date=reporting_date.isoformat(),
            prompt_version=PROMPT_VERSION,
            ttl_seconds=ARTICLE_CACHE_TTL_SECONDS,
            count=0,
            items=[],
            error=str(exc),
        )

    if source_url:
        payload = get_cached_analysis(reporting_date, source_url)
        items = [payload] if payload else []
        return CachedAnalysesListResult(
            reporting_date=reporting_date.isoformat(),
            prompt_version=PROMPT_VERSION,
            ttl_seconds=ARTICLE_CACHE_TTL_SECONDS,
            count=len(items),
            items=items,
        )

    urls: list[str] = []
    try:
        members = client.smembers(_build_index_key(reporting_date))
        assert isinstance(
            members, (set, list)
        ), f"Expected Redis set members, got {type(members).__name__}"
        urls.extend(str(member) for member in members)
    except Exception as exc:
        return CachedAnalysesListResult(
            reporting_date=reporting_date.isoformat(),
            prompt_version=PROMPT_VERSION,
            ttl_seconds=ARTICLE_CACHE_TTL_SECONDS,
            count=0,
            items=[],
            error=str(exc),
        )

    items: list[CachedAnalysisPayload] = []
    for url in sorted(urls):
        payload = get_cached_analysis(reporting_date, url)
        if payload:
            items.append(payload)

    return CachedAnalysesListResult(
        reporting_date=reporting_date.isoformat(),
        prompt_version=PROMPT_VERSION,
        ttl_seconds=ARTICLE_CACHE_TTL_SECONDS,
        count=len(items),
        items=items,
    )
