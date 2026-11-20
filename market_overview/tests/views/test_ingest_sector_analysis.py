"""Tests for sector-analysis ingestion API views."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from market_overview.models.common import EquityIndexChoices


class TestIngestSectorAnalysisView(TestCase):
    """Test cases for IngestSectorAnalysisView."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/markets/sector-analysis/ingest"

    @patch("market_overview.views.sector_analysis.release_redis_lock")
    @patch("market_overview.views.sector_analysis.try_acquire_redis_lock")
    @patch(
        "market_overview.services.sector_analysis."
        "ingest_all_equity_index_subsector_daily_moves_for_date_range"
    )
    def test_ingest_sector_analysis_all_indexes(
        self,
        mock_ingest_all_range,
        mock_try_acquire,
        mock_release,
    ):
        """
        GIVEN a start_date and end_date window with no equity_index
        WHEN POST /markets/sector-analysis/ingest is called
        THEN every equity index is ingested across the window
        """
        mock_try_acquire.return_value = object()
        mock_ingest_all_range.return_value = [
            {
                "date": "2026-11-18",
                "equity_index": "SPX",
                "subsectors_upserted": 2,
                "names_missing_weight": [],
                "names_missing_return": [],
            }
        ]

        response = self.client.post(
            self.base_url,
            {"start_date": "2026-11-17", "end_date": "2026-11-18"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": (
                "Sector analysis ingested successfully for 2026-11-17 .. 2026-11-18."
            ),
            "results": [
                {
                    "date": "2026-11-18",
                    "equity_index": "SPX",
                    "subsectors_upserted": 2,
                    "names_missing_weight": [],
                    "names_missing_return": [],
                }
            ],
        }
        mock_ingest_all_range.assert_called_once_with(
            date(2026, 11, 17),
            date(2026, 11, 18),
        )
        mock_release.assert_called_once()

    @patch("market_overview.views.sector_analysis.release_redis_lock")
    @patch("market_overview.views.sector_analysis.try_acquire_redis_lock")
    @patch(
        "market_overview.services.sector_analysis."
        "ingest_equity_index_subsector_daily_moves_for_date_range"
    )
    def test_ingest_sector_analysis_one_index(
        self,
        mock_ingest_index_range,
        mock_try_acquire,
        mock_release,
    ):
        """
        GIVEN a date window and equity_index
        WHEN POST /markets/sector-analysis/ingest is called
        THEN only that equity index is ingested across the window
        """
        mock_try_acquire.return_value = object()
        mock_ingest_index_range.return_value = [
            {
                "date": "2026-11-18",
                "equity_index": "CAC40",
                "subsectors_upserted": 1,
                "names_missing_weight": [],
                "names_missing_return": [],
            }
        ]

        response = self.client.post(
            self.base_url,
            {
                "start_date": "2026-11-18",
                "end_date": "2026-11-18",
                "equity_index": "CAC40",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": (
                "Sector analysis ingested successfully for 2026-11-18 .. 2026-11-18."
            ),
            "results": [
                {
                    "date": "2026-11-18",
                    "equity_index": "CAC40",
                    "subsectors_upserted": 1,
                    "names_missing_weight": [],
                    "names_missing_return": [],
                }
            ],
        }
        mock_ingest_index_range.assert_called_once_with(
            EquityIndexChoices.CAC40,
            date(2026, 11, 18),
            date(2026, 11, 18),
        )
        mock_release.assert_called_once()

    def test_ingest_sector_analysis_invalid_window(self):
        """
        GIVEN an end_date before start_date
        WHEN POST /markets/sector-analysis/ingest is called
        THEN a 400 response is returned
        """
        response = self.client.post(
            self.base_url,
            {"start_date": "2026-11-19", "end_date": "2026-11-18"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "non_field_errors": [
                    "end_date must be greater than or equal to start_date.",
                ],
            },
        }
