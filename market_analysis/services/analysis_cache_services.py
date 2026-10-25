"""Redis cache for same-day article analyses (keyed by URL + prompt version)."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, List, NotRequired, Optional, TypedDict
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone as dj_timezone

import redis

from core.services import logger
from market_analysis.llm.config import PROMPT_VERSION

if TYPE_CHECKING:
    from market_analysis.services.llm_market_recap_services import AnalyzedArticle

ARTICLE_CACHE_TTL_SECONDS = 24 * 60 * 60
_KEY_PREFIX = "market_analysis:article_analysis"


class CachedAnalysisPayload(TypedDict):
    """Cached analysis payload dictionnary."""

    source_url: str
    cached_at: str
    prompt_version: str
    analysis: dict


class CachedAnalysesListResult(TypedDict):
    """Cached analyses list result dictionnary."""

    reporting_date: str
    prompt_version: str
    ttl_seconds: int
    count: int
    items: List[CachedAnalysisPayload]
    error: NotRequired[str]


def _get_redis_client():
    """Return a Redis client using the Celery broker URL."""
    return redis.from_url(settings.CELERY_BROKER_URL)


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
        analysis=dict(article),
    )
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_payload(raw: str) -> Optional[CachedAnalysisPayload]:
    """Parse a Redis cache payload; return None if invalid."""
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "analysis" not in data:
        return None
    return CachedAnalysisPayload(
        source_url=str(data.get("source_url") or ""),
        cached_at=str(data.get("cached_at") or ""),
        prompt_version=str(data.get("prompt_version") or ""),
        analysis=data["analysis"] if isinstance(data["analysis"], dict) else {},
    )


def analyzed_from_cache_payload(payload: CachedAnalysisPayload) -> AnalyzedArticle:
    """Rebuild an ``AnalyzedArticle`` TypedDict from a cache payload."""
    from market_analysis.services.llm_market_recap_services import AnalyzedArticle

    analysis = payload["analysis"]
    event_types = analysis.get("event_types")
    if not event_types and analysis.get("event_type"):
        event_types = [analysis["event_type"]]
    return AnalyzedArticle(
        title=analysis.get("title", ""),
        summary=analysis.get("summary", ""),
        event_types=[str(event_type) for event_type in (event_types or [])],
        companies=list(analysis.get("companies") or []),
        sectors=list(analysis.get("sectors") or []),
        sentiment=analysis.get("sentiment", "NEUTRAL"),
        key_facts=list(analysis.get("key_facts") or []),
        uncertainties=list(analysis.get("uncertainties") or []),
        source_url=analysis.get("source_url") or payload.get("source_url") or "",
    )


def get_cached_analysis(
    reporting_date: date, source_url: str
) -> Optional[CachedAnalysisPayload]:
    """Fetch one cached analysis by reporting date and article URL."""
    try:
        client = _get_redis_client()
        raw = client.get(_build_entry_key(reporting_date, source_url))
    except Exception as exc:
        logger.warning("Article analysis cache get failed: %s", exc)
        return None
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
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


def list_cached_analyses(
    reporting_date: date,
    source_url: Optional[str] = None,
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

    urls: List[str] = []
    try:
        members = client.smembers(_build_index_key(reporting_date))
        for member in members or []:
            urls.append(
                member.decode("utf-8") if isinstance(member, bytes) else str(member)
            )
    except Exception as exc:
        return CachedAnalysesListResult(
            reporting_date=reporting_date.isoformat(),
            prompt_version=PROMPT_VERSION,
            ttl_seconds=ARTICLE_CACHE_TTL_SECONDS,
            count=0,
            items=[],
            error=str(exc),
        )

    items: List[CachedAnalysisPayload] = []
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
