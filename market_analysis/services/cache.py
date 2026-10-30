"""Redis cache for same-day article analyses (keyed by URL + prompt version)."""

import json
from datetime import date
from typing import TYPE_CHECKING, NotRequired, TypedDict
from urllib.parse import quote

from django.utils import timezone as dj_timezone
from pydantic import TypeAdapter

from core.cache import get_cached_json, get_redis_client
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
    analysis: "AnalyzedArticle"


class CachedAnalysisWireAnalysis(TypedDict, total=False):
    """Wire-format analysis object as stored in Redis JSON (fields we read)."""

    title: str
    summary: str
    event_types: list[str]
    event_type: str
    companies: list[str]
    sectors: list[str]
    sentiment: str
    key_facts: list[str]
    uncertainties: list[str]
    source_url: str


class CachedAnalysisWirePayload(TypedDict, total=False):
    """Wire-format Redis cache JSON root (fields we read before mapping inward)."""

    source_url: str
    cached_at: str
    prompt_version: str
    analysis: CachedAnalysisWireAnalysis


_CACHED_ANALYSIS_WIRE_ADAPTER = TypeAdapter(CachedAnalysisWirePayload)


def _build_entry_key(reporting_date: date, source_url: str) -> str:
    """Build the Redis key for one article analysis entry."""
    return (
        f"{_KEY_PREFIX}:{reporting_date.isoformat()}:"
        f"{PROMPT_VERSION}:{quote(source_url.strip(), safe="")}"
    )


def _build_index_key(reporting_date: date) -> str:
    """Build the Redis set key listing cached URLs for a reporting date."""
    return f"{_KEY_PREFIX}:index:{reporting_date.isoformat()}:{PROMPT_VERSION}"


def _map_wire_payload_to_cached(
    data: CachedAnalysisWirePayload,
) -> CachedAnalysisPayload | None:
    """Map validated Redis wire JSON into an inward CachedAnalysisPayload."""
    # Circular: cache ↔ llm_market_recap
    from market_analysis.services.llm_market_recap import AnalyzedArticle

    raw_analysis = data.get("analysis") or {}
    if not raw_analysis and "analysis" not in data:
        return None
    source_url = data.get("source_url") or ""

    event_types_raw = raw_analysis.get("event_types")
    legacy_event_type = raw_analysis.get("event_type")
    if not event_types_raw and legacy_event_type:
        event_types_raw = [legacy_event_type]
    event_types: list[EventType] = []
    if event_types_raw:
        for event_type in event_types_raw:
            try:
                event_types.append(EventType(str(event_type)))
            except ValueError:
                continue
    try:
        sentiment = Sentiment(str(raw_analysis.get("sentiment") or "NEUTRAL"))
    except ValueError:
        sentiment = Sentiment.NEUTRAL
    analysis = AnalyzedArticle(
        title=raw_analysis.get("title") or "",
        summary=raw_analysis.get("summary") or "",
        event_types=event_types,
        companies=list(raw_analysis.get("companies") or []),
        sectors=list(raw_analysis.get("sectors") or []),
        sentiment=sentiment,
        key_facts=list(raw_analysis.get("key_facts") or []),
        uncertainties=list(raw_analysis.get("uncertainties") or []),
        source_url=raw_analysis.get("source_url") or source_url or "",
    )
    return CachedAnalysisPayload(
        source_url=source_url,
        cached_at=data.get("cached_at") or "",
        prompt_version=data.get("prompt_version") or "",
        analysis=analysis,
    )


def get_cached_analysis(
    reporting_date: date, source_url: str
) -> CachedAnalysisPayload | None:
    """Fetch one cached analysis by reporting date and article URL."""
    wire = get_cached_json(
        _build_entry_key(reporting_date, source_url),
        _CACHED_ANALYSIS_WIRE_ADAPTER,
        log_label="Article analysis cache",
    )
    if wire is None:
        return None
    return _map_wire_payload_to_cached(wire)


def set_cached_analysis(
    reporting_date: date,
    article: "AnalyzedArticle",
    source_url: str,
) -> None:
    """Store an analysis digest keyed by reporting date and article URL.

    Uses a Redis pipeline so the entry and day index stay in sync (beyond the
    plain ``set_cached_json`` helper).
    """
    try:
        client = get_redis_client(decode_responses=True)
        key = _build_entry_key(reporting_date, source_url)
        index = _build_index_key(reporting_date)
        payload = CachedAnalysisPayload(
            source_url=source_url,
            cached_at=dj_timezone.now().isoformat(),
            prompt_version=PROMPT_VERSION,
            analysis=article,
        )
        pipe = client.pipeline()
        pipe.setex(
            key,
            ARTICLE_CACHE_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
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
        client = get_redis_client(decode_responses=True)
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
