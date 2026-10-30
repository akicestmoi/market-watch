"""Tests for publication schedule scraping helpers."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
from django.test import TestCase, override_settings
from freezegun import freeze_time
from pandas.testing import assert_frame_equal

from core.testing import MockResponse, load_json_mock
from economic_overview.services.scrapers.eurostat import (
    _get_eurostat_publication_schedule,
    get_publication_dates_from_eurostat,
)
from economic_overview.services.scrapers.fred import get_publication_dates_from_fred
from economic_overview.services.scrapers.insee import (
    _get_insee_publication_schedule,
    get_publication_dates_from_insee,
)


class TestInseePublicationScheduleScraping(TestCase):
    """Test cases for INSEE publication schedule scraping functions."""

    MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/insee/schedule/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_insee_publication_schedule.cache_clear()
        get_publication_dates_from_insee.cache_clear()

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_get_insee_publication_schedule_success(self, mock_post):
        """
        GIVEN a successful INSEE publication schedule API response
        WHEN getting the publication schedule
        THEN the schedule DataFrame should be returned
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=json.dumps(self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS).encode(),
        )

        result = _get_insee_publication_schedule()
        expected = pd.DataFrame(
            {
                "name": [
                    "Foreign trade results",
                    "Official International reserves",
                    "Balance of payments",
                    "Foreign trade results",
                ],
                "publication_date": pd.to_datetime(
                    [
                        "2025-12-05T07:45:00.000+00:00",
                        "2025-12-05T07:45:00.000+00:00",
                        "2025-12-05T07:45:00.000+00:00",
                        "2026-03-10T07:45:00.000+00:00",
                    ],
                    utc=True,
                ),
            }
        )
        assert_frame_equal(result, expected)

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_get_insee_publication_schedule_http_error(self, mock_post):
        """
        GIVEN an HTTP error response from INSEE API
        WHEN getting the publication schedule
        THEN an empty DataFrame should be returned
        """
        mock_post.return_value = MockResponse(status_code=404, content=b"Not Found")

        result = _get_insee_publication_schedule()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_get_insee_publication_schedule_empty_documents(self, mock_post):
        """
        GIVEN an INSEE API response with empty documents
        WHEN getting the publication schedule
        THEN an empty DataFrame should be returned
        """
        mock_data = {"documents": []}
        mock_post.return_value = MockResponse(
            status_code=200, content=json.dumps(mock_data).encode()
        )

        result = _get_insee_publication_schedule()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @freeze_time("2025-11-01")
    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_get_publication_dates_from_insee_success(self, mock_post):
        """
        GIVEN a publication schedule with matching indicator name
        WHEN getting publication dates for that indicator
        THEN the first two upcoming publication dates should be returned
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=json.dumps(self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS).encode(),
        )

        result = get_publication_dates_from_insee("Foreign trade results")
        assert result == [
            datetime(2025, 12, 5, 7, 45, tzinfo=timezone.utc),
            datetime(2026, 3, 10, 7, 45, tzinfo=timezone.utc),
        ]

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_get_publication_dates_from_insee_not_found(self, mock_post):
        """
        GIVEN a publication schedule without matching indicator name
        WHEN getting publication dates for that indicator
        THEN an empty list should be returned
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=json.dumps(self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS).encode(),
        )

        result = get_publication_dates_from_insee("Test Indicator")

        assert result == []

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_get_publication_dates_from_insee_empty_schedule(self, mock_post):
        """
        GIVEN an empty publication schedule
        WHEN getting publication dates
        THEN an empty list should be returned
        """
        mock_data = {"documents": []}
        mock_post.return_value = MockResponse(
            status_code=200, content=json.dumps(mock_data).encode()
        )

        result = get_publication_dates_from_insee("Test Indicator")

        assert result == []


class TestEurostatPublicationScheduleScraping(TestCase):
    """Test cases for Eurostat publication schedule scraping functions."""

    MOCK_EUROSTAT_PUBLICATION_SCHEDULE_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/eurostat/schedule/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_eurostat_publication_schedule.cache_clear()
        get_publication_dates_from_eurostat.cache_clear()

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_eurostat_publication_schedule_success(self, mock_get):
        """
        GIVEN a successful Eurostat eventsJson response
        WHEN getting the publication schedule
        THEN the schedule DataFrame should be returned sorted by date
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=json.dumps(
                self.MOCK_EUROSTAT_PUBLICATION_SCHEDULE_SUCCESS
            ).encode(),
        )

        result = _get_eurostat_publication_schedule()
        expected = pd.DataFrame(
            {
                "name": [
                    "Flash estimate inflation euro area",
                    "Unemployment",
                    "Inflation (HICP)",
                    "Inflation (HICP)",
                ],
                "publication_date": pd.to_datetime(
                    [
                        "2026-10-30T11:00:00+00:00",
                        "2026-11-03T11:00:00+00:00",
                        "2026-11-17T11:00:00+00:00",
                        "2026-12-17T11:00:00+00:00",
                    ],
                    utc=True,
                ),
            }
        )
        assert_frame_equal(result, expected)

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_eurostat_publication_schedule_http_error(self, mock_get):
        """
        GIVEN an HTTP error response from Eurostat eventsJson
        WHEN getting the publication schedule
        THEN an empty DataFrame should be returned
        """
        mock_get.return_value = MockResponse(status_code=404, content=b"Not Found")

        result = _get_eurostat_publication_schedule()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_eurostat_publication_schedule_invalid_json(self, mock_get):
        """
        GIVEN a non-list Eurostat eventsJson payload
        WHEN getting the publication schedule
        THEN an empty DataFrame should be returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=json.dumps({"events": []}).encode(),
        )

        result = _get_eurostat_publication_schedule()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_publication_dates_from_eurostat_success(self, mock_get):
        """
        GIVEN a publication schedule with matching calendar title
        WHEN getting publication dates for that indicator
        THEN the first two Inflation (HICP) dates should be returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=json.dumps(
                self.MOCK_EUROSTAT_PUBLICATION_SCHEDULE_SUCCESS
            ).encode(),
        )

        result = get_publication_dates_from_eurostat("Inflation (HICP)")
        assert result == [
            datetime(2026, 11, 17, 11, 0, tzinfo=timezone.utc),
            datetime(2026, 12, 17, 11, 0, tzinfo=timezone.utc),
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_publication_dates_from_eurostat_not_found(self, mock_get):
        """
        GIVEN a publication schedule without matching calendar title
        WHEN getting publication dates for that indicator
        THEN an empty list should be returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=json.dumps(
                self.MOCK_EUROSTAT_PUBLICATION_SCHEDULE_SUCCESS
            ).encode(),
        )

        result = get_publication_dates_from_eurostat("Unknown release")

        assert result == []


class TestFredPublicationScheduleScraping(TestCase):
    """Test cases for FRED publication schedule scraping functions."""

    MOCK_FRED_RELEASE_DATES_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/fred/schedule/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_publication_dates_from_fred.cache_clear()

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_publication_dates_from_fred_success(self, mock_get):
        """
        GIVEN FRED release dates including past and future CPI releases
        WHEN getting publication dates for Consumer Price Index
        THEN the next two future dates are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_FRED_RELEASE_DATES_SUCCESS,
        )

        result = get_publication_dates_from_fred("Consumer Price Index")
        assert result == [
            datetime(2026, 11, 13, tzinfo=timezone.utc),
            datetime(2026, 12, 10, tzinfo=timezone.utc),
        ]
        request_params = mock_get.call_args.kwargs["params"]
        assert request_params["release_id"] == 10
        assert "realtime_start" in request_params

    @override_settings(FRED_API_KEY="test-fred-key")
    def test_get_publication_dates_from_fred_unknown_technical_name(self):
        """
        GIVEN a technical_name with no FRED release_id mapping
        WHEN getting publication dates
        THEN an empty list is returned
        """
        result = get_publication_dates_from_fred("Unknown FRED release")
        assert result == []
