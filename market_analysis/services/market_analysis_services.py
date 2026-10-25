"""End-to-end market analysis: extract → analyze → save daily recap."""

from __future__ import annotations

from datetime import date
from typing import List, NotRequired, TypedDict

from core.locks import try_acquire_redis_lock
from core.services import logger
from market_analysis.models import DailyRecapModel
from market_analysis.services import (
    article_extraction_services,
    llm_market_recap_services,
)
from market_analysis.services.article_extraction_services import ArticleExtractionResult
from market_analysis.services.llm_market_recap_services import ArticleAnalysisFailure

PIPELINE_LOCK_KEY_PREFIX = "market_analysis:pipeline:"


class MarketAnalysisResult(TypedDict):
    """Analysis pipeline result dictionnary."""

    status: str
    reporting_date: str
    reason: NotRequired[str]
    message: NotRequired[str]
    sources: NotRequired[List[ArticleExtractionResult]]
    analyzed: NotRequired[int]
    analysis_failed: NotRequired[List[ArticleAnalysisFailure]]
    cache_hits: NotRequired[int]
    cache_misses: NotRequired[int]
    recap_id: NotRequired[int]
    recap_title: NotRequired[str]


def run_daily_analysis_pipeline(
    reporting_date: date,
    force: bool = False,
) -> MarketAnalysisResult:
    """Extract news → analyze in memory → save recap with DB market context.

    Skips when a recap already exists (unless `force` is True).
    """
    if (
        not force
        and DailyRecapModel.objects.filter(reporting_date=reporting_date).exists()
    ):
        logger.info(
            "Market analysis pipeline skipped for %s: a daily recap already exists",
            reporting_date.isoformat(),
        )
        return MarketAnalysisResult(
            status="skipped",
            reason="Daily recap already exists",
            reporting_date=reporting_date.isoformat(),
        )

    logger.info(
        "Market analysis pipeline starting for %s (force=%s)",
        reporting_date.isoformat(),
        force,
    )

    logger.info("Pipeline stage: article extraction starting for %s", reporting_date)
    extracted_articles = article_extraction_services.extract_all_articles(
        reporting_date=reporting_date
    )
    articles = extracted_articles["articles"]
    logger.info(
        "Pipeline stage: article extraction finished for %s "
        "(%s article(s) from %s source(s))",
        reporting_date.isoformat(),
        len(articles),
        len(extracted_articles["sources"]),
    )

    logger.info(
        "Pipeline stage: article analysis starting for %s (%s article(s))",
        reporting_date.isoformat(),
        len(articles),
    )
    analyzed = llm_market_recap_services.analyze_extracted_articles(
        articles,
        reporting_date=reporting_date,
    )
    logger.info(
        "Pipeline stage: article analysis finished for %s "
        "(analyzed=%s, failed=%s, cache_hits=%s, cache_misses=%s)",
        reporting_date.isoformat(),
        analyzed["analyzed_count"],
        len(analyzed["failed"]),
        analyzed.get("cache_hits", 0),
        analyzed.get("cache_misses", 0),
    )

    logger.info(
        "Pipeline stage: daily recap generation starting for %s",
        reporting_date.isoformat(),
    )
    daily_recap = llm_market_recap_services.generate_daily_recap(
        reporting_date,
        analyses=analyzed["analyses"],
        extraction_sources=extracted_articles["sources"],
        analysis_failures=analyzed["failed"],
    )
    logger.info(
        "Pipeline stage: daily recap generation finished for %s "
        "(recap_id=%s, title=%r)",
        reporting_date.isoformat(),
        daily_recap.id,
        daily_recap.title,
    )

    logger.info(
        "Market analysis pipeline finished successfully for %s",
        reporting_date.isoformat(),
    )
    return MarketAnalysisResult(
        status="success",
        reporting_date=reporting_date.isoformat(),
        sources=extracted_articles["sources"],
        analyzed=analyzed["analyzed_count"],
        analysis_failed=analyzed["failed"],
        cache_hits=analyzed.get("cache_hits", 0),
        cache_misses=analyzed.get("cache_misses", 0),
        recap_id=daily_recap.id,
        recap_title=daily_recap.title,
    )


def run_daily_analysis_pipeline_with_lock(
    reporting_date: date,
    force: bool = False,
) -> MarketAnalysisResult:
    """Run the pipeline under a per-date Redis lock (HTTP and Celery share this)."""
    lock_key = f"{PIPELINE_LOCK_KEY_PREFIX}{reporting_date.isoformat()}"
    lock = try_acquire_redis_lock(lock_key)
    if lock is None:
        logger.info(
            "Market analysis pipeline skipped for %s: already in progress",
            reporting_date.isoformat(),
        )
        return MarketAnalysisResult(
            status="skipped",
            reason="Market analysis pipeline already in progress",
            message="Market analysis pipeline already in progress",
            reporting_date=reporting_date.isoformat(),
        )
    try:
        return run_daily_analysis_pipeline(reporting_date, force=force)
    finally:
        try:
            lock.release()
        except Exception:
            logger.warning(
                "Could not release market analysis pipeline lock for %s",
                reporting_date.isoformat(),
            )
