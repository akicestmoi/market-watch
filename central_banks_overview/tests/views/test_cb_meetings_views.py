from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel


class TestCentralBankMeetingsViews(TestCase):
    """Test cases for Central Bank Meetings API Views."""

    INGEST_MEETING_DATES_URL = "/ingest"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/central-banks/meeting-dates"
        self.test_date_1 = datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc)
        self.test_date_2 = datetime(2024, 5, 1, 13, 0, 0, tzinfo=timezone.utc)
        self.test_date_3 = datetime(2024, 6, 12, 13, 0, 0, tzinfo=timezone.utc)

        # Create FRB meetings
        self.frb_meeting_1 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=self.test_date_1,
        )
        self.frb_meeting_2 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=2,
            date=self.test_date_2,
        )

        # Create ECB meetings
        self.ecb_meeting_1 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=self.test_date_3,
        )

    @patch(
        "central_banks_overview.services.cb_meetings_services.ingest_all_central_bank_meeting_dates"
    )
    def test_ingest_meeting_dates_success(self, mock_ingest):
        """
        GIVEN a request to ingest meeting dates
        WHEN ingesting central bank meeting dates
        THEN the meeting dates are successfully ingested
        """
        mock_ingest.return_value = None

        response = self.client.post(f"{self.base_url}{self.INGEST_MEETING_DATES_URL}")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Central Bank Meeting Dates successfully ingested"
        }
        mock_ingest.assert_called_once()

    def test_get_central_bank_meeting_dates_all(self):
        """
        GIVEN central bank meetings in the database
        WHEN getting all central bank meeting dates
        THEN all meeting dates are returned grouped by central bank
        """
        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "meeting_dates": ["2024-06-12T15:00:00+02:00"],
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "meeting_dates": [
                    "2024-03-20T14:00:00+01:00",
                    "2024-05-01T15:00:00+02:00",
                ],
            },
        ]

    def test_get_central_bank_meeting_dates_filtered(self):
        """
        GIVEN central bank meetings for multiple banks
        WHEN getting meeting dates for specific central banks
        THEN only meeting dates for those banks are returned
        """
        params = {
            "central_banks": CentralBankChoices.FRB.value,
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "meeting_dates": [
                    "2024-03-20T14:00:00+01:00",
                    "2024-05-01T15:00:00+02:00",
                ],
            },
        ]

    def test_get_central_bank_meeting_dates_multiple_central_banks(self):
        """
        GIVEN central bank meetings for multiple banks
        WHEN getting meeting dates with comma-separated central_banks
        THEN meeting dates for all specified banks are returned
        """
        params = {
            "central_banks": f"{CentralBankChoices.FRB.value},{CentralBankChoices.ECB.value}",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "meeting_dates": ["2024-06-12T15:00:00+02:00"],
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "meeting_dates": [
                    "2024-03-20T14:00:00+01:00",
                    "2024-05-01T15:00:00+02:00",
                ],
            },
        ]

    def test_get_central_bank_meeting_dates_empty(self):
        """
        GIVEN no central bank meetings in the database
        WHEN getting all central bank meeting dates
        THEN an empty list is returned
        """
        CentralBankMeetingModel.objects.all().delete()

        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
