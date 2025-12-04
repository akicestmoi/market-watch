import json
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from django.test import TestCase
from pandas.testing import assert_frame_equal

from core.tests import MockResponse, load_json_mock
from economic_overview.services.publication_services import (
    _get_insee_publication_schedule,
    _get_publication_dates_from_insee,
)


class TestInseePublicationScheduleScraping(TestCase):
    """Test cases for INSEE publication schedule scraping functions."""

    MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/insee/schedule/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_insee_publication_schedule.cache_clear()
        _get_publication_dates_from_insee.cache_clear()

    @patch("economic_overview.services.publication_services.requests.post")
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

    @patch("economic_overview.services.publication_services.requests.post")
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

    @patch("economic_overview.services.publication_services.requests.post")
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

    @patch("economic_overview.services.publication_services.requests.post")
    def test_get_publication_dates_from_insee_success(self, mock_post):
        """
        GIVEN a publication schedule with matching indicator name
        WHEN getting publication dates for that indicator
        THEN the first two publication dates should be returned
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=json.dumps(self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS).encode(),
        )

        result = _get_publication_dates_from_insee("Foreign trade results")
        assert result == [
            datetime(2025, 12, 5, 7, 45),
            datetime(2026, 3, 10, 7, 45),
        ]

    @patch("economic_overview.services.publication_services.requests.post")
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

        result = _get_publication_dates_from_insee("Test Indicator")

        assert result == []

    @patch("economic_overview.services.publication_services.requests.post")
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

        result = _get_publication_dates_from_insee("Test Indicator")

        assert result == []
