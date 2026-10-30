"""Tests for publication schedule API views."""

import json
from datetime import datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.testing import MockResponse, load_json_mock
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from economic_overview.services.scrapers.insee import (
    _get_insee_publication_schedule,
    get_publication_dates_from_insee,
)


class TestUpdatePublicationScheduleView(TestCase):
    """Test cases for UpdatePublicationScheduleView."""

    UPDATE_PUBLICATION_SCHEDULE_URL = "/update"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/economics/schedule"
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Test Indicator",
            name="Test Indicator Name",
            technical_name="Foreign trade results",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.schedule = PublicationScheduleModel.objects.create(
            indicator=self.indicator
        )
        self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS = load_json_mock(
            "economic_overview/tests/mock_web_data/insee/schedule/success.json"
        )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_insee_publication_schedule.cache_clear()
        get_publication_dates_from_insee.cache_clear()

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_update_publication_schedule_success(self, mock_post):
        """
        GIVEN valid indicator names with successful INSEE API response
        WHEN updating publication schedules
        THEN the schedules are successfully updated
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=json.dumps(self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS).encode(),
        )

        payload = {
            "indicator_names": [self.indicator.name],
        }
        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            payload,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Publication schedule successfully updated.",
            "schedule_not_updated": [],
        }
        self.schedule.refresh_from_db()
        assert self.schedule.convert_to_dict() == {
            "indicator_id": self.indicator.id,
            "previous_publication_date": None,
            "current_publication_date": datetime(
                2025, 12, 5, 7, 45, 0, tzinfo=dt_timezone.utc
            ),
            "next_publication_date": datetime(
                2026, 3, 10, 7, 45, 0, tzinfo=dt_timezone.utc
            ),
        }

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_update_publication_schedule_empty_list_updates_all(self, mock_post):
        """
        GIVEN an empty indicator_names list
        WHEN updating publication schedules
        THEN all indicators are updated
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=json.dumps(self.MOCK_INSEE_PUBLICATION_SCHEDULE_SUCCESS).encode(),
        )

        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            {"indicator_names": []},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Publication schedule successfully updated.",
            "schedule_not_updated": [],
        }
        self.schedule.refresh_from_db()
        assert self.schedule.current_publication_date is not None

    def test_update_publication_schedule_indicator_not_found(self):
        """
        GIVEN non-existent indicator names
        WHEN updating publication schedules
        THEN a 404 error is returned
        """
        payload = {
            "indicator_names": ["NonExistent"],
        }
        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            payload,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.json()["message"]
            == "indicators: ['NonExistent'] do not exist in database."
        )

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_update_publication_schedule_http_error(self, mock_post):
        """
        GIVEN an HTTP error from INSEE API
        WHEN updating publication schedules
        THEN the schedule is not updated
        """
        mock_post.return_value = MockResponse(status_code=404, content=b"Not Found")

        payload = {
            "indicator_names": [self.indicator.name],
        }
        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            payload,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Publication schedule successfully updated.",
            "schedule_not_updated": [self.indicator.name],
        }

    @patch("economic_overview.services.scrapers.insee.requests.post")
    def test_update_publication_schedule_empty_documents(self, mock_post):
        """
        GIVEN an INSEE API response with empty documents
        WHEN updating publication schedules
        THEN the schedule is not updated
        """
        mock_data = {"documents": []}
        mock_post.return_value = MockResponse(
            status_code=200, content=json.dumps(mock_data).encode()
        )

        payload = {
            "indicator_names": [self.indicator.name],
        }
        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            payload,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Publication schedule successfully updated.",
            "schedule_not_updated": [self.indicator.name],
        }

    @patch(
        "economic_overview.services.publication.PUBLICATION_SOURCE_MAP",
        {},
    )
    def test_update_publication_schedule_no_publication_function(self):
        """
        GIVEN an indicator with no publication function in PUBLICATION_SOURCE_MAP
        WHEN updating publication schedules
        THEN the request succeeds and the indicator is listed as not updated
        """
        payload = {
            "indicator_names": [self.indicator.name],
        }
        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            payload,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Publication schedule successfully updated.",
            "schedule_not_updated": [self.indicator.name],
        }
