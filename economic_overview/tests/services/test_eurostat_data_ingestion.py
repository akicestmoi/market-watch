"""Tests for Eurostat HICP scraping in economic data ingestion."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from pydantic import TypeAdapter

from core.conftest import MockResponse, load_json_mock
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.data_ingestion import (
    EurostatJsonStatPayload,
    ScrapingResult,
    _get_data_from_eurostat,
    _parse_eurostat_jsonstat_values,
)

_EUROSTAT_JSONSTAT_ADAPTER = TypeAdapter(EurostatJsonStatPayload)


class TestEurostatHicpIngestion(TestCase):
    """Tests for Eurostat ``prc_hicp_minr`` scraping helpers."""

    MOCK_EUROSTAT_HICP_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/eurostat/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_data_from_eurostat.cache_clear()

    def test_parse_eurostat_jsonstat_values(self):
        """
        GIVEN a Eurostat JSON-stat HICP fixture
        WHEN parsing values
        THEN periods and index levels are returned newest-first
        """
        payload = _EUROSTAT_JSONSTAT_ADAPTER.validate_python(
            self.MOCK_EUROSTAT_HICP_SUCCESS
        )
        result = _parse_eurostat_jsonstat_values(payload)
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1),
            data_value=104.31,
            comment="",
        )
        assert len(result) == 141
        assert result[-1] == ScrapingResult(
            period=date(2015, 1, 1),
            data_value=76.3,
            comment="",
        )

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_eurostat_success_no_target_period(self, mock_get):
        """
        GIVEN a successful Eurostat JSON-stat response
        WHEN getting data without target period
        THEN all observations are returned with the latest first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_EUROSTAT_HICP_SUCCESS,
        )

        result = _get_data_from_eurostat(
            "prc_hicp_minr",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1),
            data_value=104.31,
            comment="",
        )
        assert len(result) == 141

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_eurostat_filters_target_period(self, mock_get):
        """
        GIVEN Eurostat returns several months
        WHEN requesting a specific YYYY-MM period
        THEN only that period is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_EUROSTAT_HICP_SUCCESS,
        )

        result = _get_data_from_eurostat(
            "prc_hicp_minr",
            "2024-09",
            EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 9, 1),
                data_value=98.33,
                comment="",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_eurostat_http_error(self, mock_get):
        """
        GIVEN an HTTP error from the Eurostat Statistics API
        WHEN getting data
        THEN a single error ScrapingResult is returned
        """
        mock_get.return_value = MockResponse(
            status_code=404,
            content=b"Not Found",
        )

        result = _get_data_from_eurostat("prc_hicp_minr")
        assert result == [
            ScrapingResult(period=None, data_value=None, comment="Not Found")
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_eurostat_unknown_ticker(self, mock_get):
        """
        GIVEN a ticker not in EUROSTAT_DATASET_PARAMS
        WHEN getting data
        THEN an unsupported-ticker ScrapingResult is returned without calling the API
        """
        result = _get_data_from_eurostat("prc_hicp_midx")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported Eurostat ticker: prc_hicp_midx",
            )
        ]
        mock_get.assert_not_called()
