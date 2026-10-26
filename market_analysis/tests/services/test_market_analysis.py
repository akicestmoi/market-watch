"""Tests for market_analysis (pipeline skip / run)."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from market_analysis.models import DailyRecapModel
from market_analysis.services.market_analysis import (
    run_daily_analysis_pipeline,
    run_daily_analysis_pipeline_with_lock,
)


def _make_recap(day: date) -> DailyRecapModel:
    """Create a DailyRecapModel for the given reporting date."""
    return DailyRecapModel.objects.create(
        reporting_date=day,
        title="t",
        main_summary="main",
        us_summary="us",
        eur_summary="eur",
        jp_summary="jp",
        additional_summary="extra",
        source_urls=[],
        model_name="gpt-6-luna",
        prompt_version="market_analysis.v1",
    )


class RunDailyAnalysisPipelineTests(TestCase):
    """Tests for run_daily_analysis_pipeline skip and lock behavior."""

    @patch(
        "market_analysis.services.market_analysis.article_extraction.extract_all_articles"
    )
    def test_skips_without_extracting_when_recap_exists(self, mock_extract):
        """
        GIVEN a DailyRecap already exists for the reporting date
        WHEN run_daily_analysis_pipeline is called without force
        THEN the pipeline is skipped and extraction is not called
        """
        day = date(2025, 12, 12)
        _make_recap(day)
        result = run_daily_analysis_pipeline(day, force=False)
        assert result["status"] == "skipped"
        assert result.get("reason") == "Daily recap already exists"
        assert result["reporting_date"] == day.isoformat()
        mock_extract.assert_not_called()

    @patch(
        "market_analysis.services.market_analysis.llm_market_recap.generate_daily_recap"
    )
    @patch(
        "market_analysis.services.market_analysis.llm_market_recap.analyze_extracted_articles"
    )
    @patch(
        "market_analysis.services.market_analysis.article_extraction.extract_all_articles"
    )
    def test_force_runs_when_recap_exists(
        self, mock_extract, mock_analyze, mock_generate
    ):
        """
        GIVEN a DailyRecap already exists for the reporting date
        WHEN run_daily_analysis_pipeline is called with force=True
        THEN the pipeline runs and extraction is called
        """
        day = date(2025, 12, 12)
        _make_recap(day)
        mock_extract.return_value = {
            "articles": [],
            "sources": [],
            "reporting_date": day.isoformat(),
        }
        mock_analyze.return_value = {
            "analyses": [],
            "analyzed_count": 0,
            "failed": [],
            "cache_hits": 0,
            "cache_misses": 0,
        }
        mock_generate.return_value = DailyRecapModel.objects.get(reporting_date=day)
        result = run_daily_analysis_pipeline(day, force=True)
        assert result["status"] == "success"
        mock_extract.assert_called_once()

    @patch("market_analysis.services.market_analysis.try_acquire_redis_lock")
    @patch(
        "market_analysis.services.market_analysis.run_daily_analysis_pipeline"
    )
    def test_with_lock_skips_when_lock_held(self, mock_pipeline, mock_lock):
        """
        GIVEN the per-date Redis pipeline lock is already held
        WHEN run_daily_analysis_pipeline_with_lock is called
        THEN the pipeline is not run and status is skipped
        """
        mock_lock.return_value = None
        day = date(2025, 12, 12)
        result = run_daily_analysis_pipeline_with_lock(day, force=True)
        assert result["status"] == "skipped"
        assert "already in progress" in (result.get("reason") or "")
        mock_pipeline.assert_not_called()
