"""Celery entry points that queue or run the daily market-analysis pipeline."""

from datetime import date

from celery import shared_task

from core.services import logger
from market_analysis.services import market_analysis


@shared_task
def scheduled_analysis_pipeline(reporting_date: str, force: bool = False):
    """Collect news into memory, analyze, and persist daily recap with market data.

    Articles are not stored. Skips when a recap already exists (unless force).
    Queued after successful price ingestion.
    """
    logger.info(
        "Celery market analysis task received for %s (force=%s)",
        reporting_date,
        force,
    )
    try:
        result = market_analysis.run_daily_analysis_pipeline_with_lock(
            date.fromisoformat(reporting_date), force=force
        )
        logger.info(
            "Celery market analysis task finished for %s: %s",
            reporting_date,
            result.get("status") if isinstance(result, dict) else result,
        )
        return result
    except Exception as exc:
        logger.error("Market analysis pipeline failed for %s: %s", reporting_date, exc)
        return {"status": "error", "message": str(exc)}


def schedule_market_analysis_after_ingestion(price_date: date) -> None:
    """Queue analysis immediately after a successful price ingestion."""
    scheduled_analysis_pipeline.delay(
        reporting_date=price_date.isoformat(),
        force=False,
    )
    logger.info(
        "Queued market analysis for %s after price ingestion",
        price_date.isoformat(),
    )
