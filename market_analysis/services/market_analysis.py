"""End-to-end market analysis: extract → analyze → save daily recap."""

import logging
from datetime import date
from typing import NotRequired, TypedDict

from core.services.locks import release_redis_lock, try_acquire_redis_lock
from market_analysis.models import DailyRecapModel
from market_analysis.services import article_extraction, llm_market_recap
from market_analysis.services.article_extraction import (
    ArticleData,
    ArticleExtractionResult,
    ExtractedArticles,
)
from market_analysis.services.llm_market_recap import ArticleAnalysisFailure

logger = logging.getLogger(__name__)

PIPELINE_LOCK_KEY_PREFIX = "market_analysis:pipeline:"


class MarketAnalysisResult(TypedDict):
    """Outcome of the daily market-analysis pipeline for one reporting date."""

    status: str
    reporting_date: str
    reason: NotRequired[str]
    message: NotRequired[str]
    sources: NotRequired[list[ArticleExtractionResult]]
    analyzed: NotRequired[int]
    analysis_failed: NotRequired[list[ArticleAnalysisFailure]]
    cache_hits: NotRequired[int]
    cache_misses: NotRequired[int]
    recap_id: NotRequired[int]
    recap_title: NotRequired[str]


def _skip_daily_analysis_when_recap_exists(
    reporting_date: date,
    force: bool,
) -> MarketAnalysisResult | None:
    """Return a skipped pipeline outcome when a recap exists and force is false."""
    if force:
        return None
    if not DailyRecapModel.objects.filter(reporting_date=reporting_date).exists():
        return None
    logger.info(
        "Market analysis pipeline skipped for %s: a daily recap already exists",
        reporting_date.isoformat(),
    )
    return MarketAnalysisResult(
        status="skipped",
        reason="Daily recap already exists",
        reporting_date=reporting_date.isoformat(),
    )


def _extract_articles_for_daily_pipeline(
    reporting_date: date,
) -> ExtractedArticles:
    """Run article extraction and log stage boundaries for the daily pipeline."""
    logger.info("Pipeline stage: article extraction starting for %s", reporting_date)
    extracted_articles = article_extraction.extract_all_articles(
        reporting_date=reporting_date
    )
    logger.info(
        "Pipeline stage: article extraction finished for %s "
        "(%s article(s) from %s source(s))",
        reporting_date.isoformat(),
        len(extracted_articles["articles"]),
        len(extracted_articles["sources"]),
    )
    return extracted_articles


def _analyze_articles_for_daily_pipeline(
    reporting_date: date,
    articles: list[ArticleData],
) -> llm_market_recap._ArticleBatchAnalysisResult:
    """Run batch article analysis and log stage boundaries."""
    logger.info(
        "Pipeline stage: article analysis starting for %s (%s article(s))",
        reporting_date.isoformat(),
        len(articles),
    )
    analyzed = llm_market_recap.analyze_extracted_articles(
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
    return analyzed


def _generate_daily_recap_for_pipeline(
    reporting_date: date,
    extracted_articles: ExtractedArticles,
    analyzed,
) -> DailyRecapModel:
    """Run daily recap generation and log stage boundaries."""
    logger.info(
        "Pipeline stage: daily recap generation starting for %s",
        reporting_date.isoformat(),
    )
    daily_recap = llm_market_recap.generate_daily_recap(
        reporting_date,
        analyses=analyzed["analyses"],
        extraction_sources=extracted_articles["sources"],
        analysis_failures=analyzed["failed"],
    )
    logger.info(
        "Pipeline stage: daily recap generation finished for %s "
        "(recap_id=%s, title=%r)",
        reporting_date.isoformat(),
        daily_recap.pk,
        daily_recap.title,
    )
    return daily_recap


def _build_pipeline_success_result(
    reporting_date: date,
    extracted_articles: ExtractedArticles,
    analyzed_count: int,
    analysis_failed: list[ArticleAnalysisFailure],
    cache_hits: int,
    cache_misses: int,
    daily_recap: DailyRecapModel,
) -> MarketAnalysisResult:
    """Format the successful daily pipeline outcome for API and task callers."""
    return MarketAnalysisResult(
        status="success",
        reporting_date=reporting_date.isoformat(),
        sources=extracted_articles["sources"],
        analyzed=analyzed_count,
        analysis_failed=analysis_failed,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        recap_id=daily_recap.pk,
        recap_title=daily_recap.title,
    )


def run_daily_analysis_pipeline(
    reporting_date: date,
    force: bool = False,
) -> MarketAnalysisResult:
    """Extract news → analyze in memory → save recap with DB market context.

    Skips when a recap already exists (unless `force` is True).
    """
    skipped = _skip_daily_analysis_when_recap_exists(reporting_date, force)
    if skipped is not None:
        return skipped

    logger.info(
        "Market analysis pipeline starting for %s (force=%s)",
        reporting_date.isoformat(),
        force,
    )

    extracted_articles = _extract_articles_for_daily_pipeline(reporting_date)
    analyzed = _analyze_articles_for_daily_pipeline(
        reporting_date, extracted_articles["articles"]
    )
    daily_recap = _generate_daily_recap_for_pipeline(
        reporting_date, extracted_articles, analyzed
    )

    logger.info(
        "Market analysis pipeline finished successfully for %s",
        reporting_date.isoformat(),
    )
    return _build_pipeline_success_result(
        reporting_date,
        extracted_articles,
        analyzed["analyzed_count"],
        analyzed["failed"],
        analyzed.get("cache_hits", 0),
        analyzed.get("cache_misses", 0),
        daily_recap,
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
        release_redis_lock(lock, lock_key)
