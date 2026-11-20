"""Tests for sector-analysis API views."""

from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from market_overview.models.common import EquityIndexChoices
from market_overview.models.sector_analysis import IndexSubsectorDailyMoveModel


class TestGetSectorAnalysisView(TestCase):
    """Test cases for GetSectorAnalysisView."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/markets/sector-analysis"

    def test_get_sector_analysis_empty(self):
        """
        GIVEN no stored subsector moves for the requested date
        WHEN GET /markets/sector-analysis is called
        THEN an empty subsectors list is returned for that region and date
        """
        response = self.client.get(
            self.base_url,
            {"date": "2026-11-19", "location": "US"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "location": "US",
            "date": "2026-11-19",
            "equity_index": "SPX",
            "subsectors": [],
        }

    def test_get_sector_analysis_with_data(self):
        """
        GIVEN stored subsector moves for US on one date
        WHEN GET /markets/sector-analysis is called for that location and date
        THEN the stored subsector day moves are returned
        """
        IndexSubsectorDailyMoveModel.objects.bulk_create(
            [
                IndexSubsectorDailyMoveModel(
                    date=date(2026, 11, 19),
                    equity_index=EquityIndexChoices.SPX.value,
                    sector="Technology",
                    subsector="Software",
                    weight=40.0,
                    daily_return=1.5,
                    contribution=0.6,
                    top_movers=[
                        {
                            "company": "Soft Co",
                            "ticker": "SOFT",
                            "weight": 40.0,
                            "daily_return": 1.5,
                            "contribution": 0.6,
                        }
                    ],
                ),
                IndexSubsectorDailyMoveModel(
                    date=date(2026, 11, 19),
                    equity_index=EquityIndexChoices.SPX.value,
                    sector="Energy",
                    subsector="Oil",
                    weight=10.0,
                    daily_return=-3.0,
                    contribution=-0.3,
                    top_movers=[
                        {
                            "company": "Oil Co",
                            "ticker": "OIL",
                            "weight": 10.0,
                            "daily_return": -3.0,
                            "contribution": -0.3,
                        }
                    ],
                ),
            ]
        )

        response = self.client.get(
            self.base_url,
            {"date": "2026-11-19", "location": "US"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "location": "US",
            "date": "2026-11-19",
            "equity_index": "SPX",
            "subsectors": [
                {
                    "date": "2026-11-19",
                    "equity_index": "SPX",
                    "sector": "Energy",
                    "subsector": "Oil",
                    "weight": 10.0,
                    "daily_return": -3.0,
                    "contribution": -0.3,
                    "top_movers": [
                        {
                            "company": "Oil Co",
                            "ticker": "OIL",
                            "weight": 10.0,
                            "daily_return": -3.0,
                            "contribution": -0.3,
                        }
                    ],
                },
                {
                    "date": "2026-11-19",
                    "equity_index": "SPX",
                    "sector": "Technology",
                    "subsector": "Software",
                    "weight": 40.0,
                    "daily_return": 1.5,
                    "contribution": 0.6,
                    "top_movers": [
                        {
                            "company": "Soft Co",
                            "ticker": "SOFT",
                            "weight": 40.0,
                            "daily_return": 1.5,
                            "contribution": 0.6,
                        }
                    ],
                },
            ],
        }

    def test_get_sector_analysis_missing_params(self):
        """
        GIVEN a request without date or location
        WHEN GET /markets/sector-analysis is called
        THEN a 400 response is returned
        """
        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "date": ["This field is required."],
                "location": ["This field is required."],
            }
        }
