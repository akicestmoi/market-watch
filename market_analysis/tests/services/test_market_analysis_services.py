"""Tests for market_analysis_services (pipeline skip / run)."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from market_analysis.models import DailyRecapModel
from market_analysis.services.market_analysis_services import (
    run_daily_analysis_pipeline,
    run_daily_analysis_pipeline_with_lock,
)


def _make_recap(day: date) -> DailyRecapModel:
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
    @patch(
        "market_analysis.services.market_analysis_services.article_extraction_services.extract_all_articles"
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
        assert result["reason"] == "Daily recap already exists"
        assert result["reporting_date"] == day.isoformat()
        mock_extract.assert_not_called()

    @patch(
        "market_analysis.services.market_analysis_services.article_extraction_services.extract_all_articles"
    )
    def test_force_runs_when_recap_exists(self, mock_extract):
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
        with (
            patch(
                "market_analysis.services.market_analysis_services.llm_market_recap_services.analyze_extracted_articles"
            ) as mock_analyze,
            patch(
                "market_analysis.services.market_analysis_services.llm_market_recap_services.generate_daily_recap"
            ) as mock_generate,
        ):
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

    @patch(
        "market_analysis.services.market_analysis_services.try_acquire_redis_lock",
        return_value=None,
    )
    @patch(
        "market_analysis.services.market_analysis_services.run_daily_analysis_pipeline"
    )
    def test_with_lock_skips_when_lock_held(self, mock_pipeline, _mock_lock):
        """
        GIVEN the per-date Redis pipeline lock is already held
        WHEN run_daily_analysis_pipeline_with_lock is called
        THEN the pipeline is not run and status is skipped
        """
        day = date(2025, 12, 12)
        result = run_daily_analysis_pipeline_with_lock(day, force=True)
        assert result["status"] == "skipped"
        assert "already in progress" in result["reason"]
        mock_pipeline.assert_not_called()
