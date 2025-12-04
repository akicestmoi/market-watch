import json
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.tests import MockResponse, load_json_mock
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from economic_overview.services.publication_services import (
    _get_insee_publication_schedule,
    _get_publication_dates_from_insee,
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
        _get_publication_dates_from_insee.cache_clear()

    @patch("economic_overview.services.publication_services.requests.post")
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
                2025, 12, 5, 6, 45, 0, tzinfo=timezone.now().tzinfo
            ),
            "next_publication_date": datetime(
                2026, 3, 10, 6, 45, 0, tzinfo=timezone.now().tzinfo
            ),
        }

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
        assert response.json() == {
            "error": "indicators: ['NonExistent'] do not exist in database.",
        }

    @patch("economic_overview.services.publication_services.requests.post")
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

    @patch("economic_overview.services.publication_services.requests.post")
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
        "economic_overview.services.publication_services.PUBLICATION_SOURCE_MAP",
        {},
    )
    def test_update_publication_schedule_no_publication_function(self):
        """
        GIVEN an indicator with no publication function in PUBLICATION_SOURCE_MAP
        WHEN updating publication schedules
        THEN a ValueError is raised
        """
        payload = {
            "indicator_names": [self.indicator.name],
        }
        response = self.client.post(
            f"{self.base_url}{self.UPDATE_PUBLICATION_SCHEDULE_URL}",
            payload,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.json()["detail"]["exception"]
            == "Publication function not found for indicator: Test Indicator Name"
        )
