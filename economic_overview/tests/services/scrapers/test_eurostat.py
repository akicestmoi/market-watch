"""Tests for Eurostat HICP scraping in economic data ingestion."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from pydantic import TypeAdapter

from core.conftest import MockResponse, load_json_mock
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.eurostat import (
    EurostatJsonStatPayload,
    _build_eurostat_request_params,
    _parse_eurostat_jsonstat_values,
    _parse_eurostat_period_label,
    get_data_from_eurostat,
)

_EUROSTAT_JSONSTAT_ADAPTER = TypeAdapter(EurostatJsonStatPayload)


class TestEurostatHicpIngestion(TestCase):
    """Tests for Eurostat ``prc_hicp_minr`` scraping helpers."""

    MOCK_EUROSTAT_HICP_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/eurostat/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_eurostat.cache_clear()

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

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
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

        result = get_data_from_eurostat(
            "prc_hicp_minr",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            location="EU",
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1),
            data_value=104.31,
            comment="",
        )
        assert len(result) == 141

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
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

        result = get_data_from_eurostat(
            "prc_hicp_minr",
            "2024-09",
            EconomicPublicationFrequencyChoices.MONTHLY,
            location="EU",
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 9, 1),
                data_value=98.33,
                comment="",
            )
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
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

        result = get_data_from_eurostat("prc_hicp_minr", location="EU")
        assert result == [
            ScrapingResult(period=None, data_value=None, comment="Not Found")
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_unknown_ticker(self, mock_get):
        """
        GIVEN a configured series ID with no Eurostat template
        WHEN getting data
        THEN an unsupported-ticker ScrapingResult is returned without calling the API
        """
        result = get_data_from_eurostat("prc_hicp_midx", location="EU")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported Eurostat ticker: prc_hicp_midx",
            )
        ]
        mock_get.assert_not_called()

    def test_parse_eurostat_period_label_annual(self):
        """
        GIVEN an annual Eurostat time label
        WHEN parsing the period
        THEN January 1 of that year is returned
        """
        assert _parse_eurostat_period_label("2024") == date(2024, 1, 1)
        assert _parse_eurostat_period_label("2024-Q2") == date(2024, 4, 1)
        assert _parse_eurostat_period_label("2024-09") == date(2024, 9, 1)

    def test_eurostat_location_supplies_geo(self):
        """
        GIVEN configured Eurostat series IDs and indicator locations
        WHEN resolving request params
        THEN geo comes from location (EU → EA)
        """
        for location in ("FR", "DE", "ES", "IT"):
            pct = _build_eurostat_request_params("tec00127_pct", location)
            mio = _build_eurostat_request_params("tec00127_mio", location)
            assert pct is not None
            assert mio is not None
            assert pct["dataset"] == "tec00127"
            assert pct["params"].get("geo") == location
            assert pct["params"].get("unit") == "PC_GDP"
            assert pct["params"].get("na_item") == "B9"
            assert mio["dataset"] == "tec00127"
            assert mio["params"].get("geo") == location
            assert mio["params"].get("unit") == "MIO_EUR"
        ea_hicp = _build_eurostat_request_params("prc_hicp_minr", "EU")
        de_hicp = _build_eurostat_request_params("prc_hicp_minr", "DE")
        assert ea_hicp is not None
        assert de_hicp is not None
        assert ea_hicp["params"].get("geo") == "EA"
        assert de_hicp["params"].get("geo") == "DE"
        assert _build_eurostat_request_params("unknown_series", "DE") is None

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_annual_deficit(self, mock_get):
        """
        GIVEN an annual tec00127 JSON-stat payload
        WHEN scraping with ANNUAL frequency
        THEN yearly observations are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={
                "version": "2.0",
                "class": "dataset",
                "label": "General government deficit/surplus",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {"0": -5.4, "1": -5.8, "2": -5.1},
                "id": ["freq", "unit", "sector", "na_item", "geo", "time"],
                "size": [1, 1, 1, 1, 1, 3],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {"index": {"A": 0}, "label": {"A": "Annual"}},
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"PC_GDP": 0},
                            "label": {"PC_GDP": "% GDP"},
                        },
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S13": 0},
                            "label": {"S13": "General government"},
                        },
                    },
                    "na_item": {
                        "label": "NA item",
                        "category": {
                            "index": {"B9": 0},
                            "label": {"B9": "Net lending/borrowing"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"FR": 0},
                            "label": {"FR": "France"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {"2023": 0, "2024": 1, "2025": 2},
                            "label": {"2023": "2023", "2024": "2024", "2025": "2025"},
                        },
                    },
                },
            },
        )
        result = get_data_from_eurostat(
            "tec00127_pct",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="FR",
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 1, 1), data_value=-5.1, comment=""
        )
        assert len(result) == 3
