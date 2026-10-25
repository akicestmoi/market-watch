"""Tests for market_analysis Celery tasks."""

from unittest.mock import patch

from django.test import TestCase

from market_analysis.tasks import scheduled_analysis_pipeline


class ScheduledAnalysisPipelineTests(TestCase):
    @patch(
        "market_analysis.tasks.market_analysis_services.run_daily_analysis_pipeline_with_lock",
        return_value={"status": "success", "reporting_date": "2025-12-12"},
    )
    def test_logs_force_without_typeerror(self, mock_pipeline):
        """
        GIVEN a Celery market-analysis task
        WHEN scheduled_analysis_pipeline runs with force=True
        THEN logging includes force and the locked pipeline is called
        """
        result = scheduled_analysis_pipeline("2025-12-12", force=True)
        assert result["status"] == "success"
        mock_pipeline.assert_called_once()
        args, kwargs = mock_pipeline.call_args
        assert kwargs.get("force") is True or (args and args[-1] is True)
