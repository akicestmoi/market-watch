"""Tests for FRED series scraping in economic data ingestion."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.conftest import MockResponse, load_json_mock
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.fred import get_data_from_fred


class TestFredDataIngestion(TestCase):
    """Tests for FRED ``series/observations`` scraping helpers."""

    MOCK_FRED_OBSERVATIONS_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/fred/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_fred.cache_clear()

    @override_settings(FRED_API_KEY="")
    def test_get_data_from_fred_missing_api_key(self):
        """
        GIVEN FRED_API_KEY is empty
        WHEN getting FRED data
        THEN a configuration-error ScrapingResult is returned
        """
        result = get_data_from_fred("CPIAUCSL")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="FRED_API_KEY is not configured.",
            )
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_success_no_target_period(self, mock_get):
        """
        GIVEN a successful FRED observations response
        WHEN getting data without target period
        THEN observations are returned newest-first and missing values are skipped
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_FRED_OBSERVATIONS_SUCCESS,
        )

        result = get_data_from_fred(
            "CPIAUCSL",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=324.1, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=323.0, comment=""),
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_filters_target_period(self, mock_get):
        """
        GIVEN FRED returns several months
        WHEN requesting a specific YYYY-MM period
        THEN only that period is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_FRED_OBSERVATIONS_SUCCESS,
        )

        result = get_data_from_fred(
            "CPIAUCSL",
            "2026-08",
            EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 8, 1), data_value=323.0, comment="")
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_http_error(self, mock_get):
        """
        GIVEN an HTTP error from the FRED API
        WHEN getting data
        THEN a single error ScrapingResult is returned
        """
        mock_get.return_value = MockResponse(status_code=400, content=b"Bad Request")

        result = get_data_from_fred("CPIAUCSL")
        assert result == [
            ScrapingResult(period=None, data_value=None, comment="Bad Request")
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_annual_deficit_filters_year(self, mock_get):
        """
        GIVEN annual FRED surplus/deficit observations
        WHEN requesting a specific calendar year
        THEN only the matching fiscal-year observation is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={
                "observations": [
                    {"date": "2025-09-30", "value": "-1774684.0"},
                    {"date": "2024-09-30", "value": "-1815377.0"},
                    {"date": "2023-09-30", "value": "."},
                ]
            },
        )

        result = get_data_from_fred(
            "FYFSD",
            "2024",
            EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(period=date(2024, 9, 30), data_value=-1815377.0, comment="")
        ]
