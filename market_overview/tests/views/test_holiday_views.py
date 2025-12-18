from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]
from rest_framework import status
from rest_framework.test import APIClient

from core.tests import load_json_mock
from market_overview.models import HolidayModel, LocationChoices

HOLIDAY_API_RESPONSE_FR = load_json_mock(
    "market_overview/tests/mock_web_data/holidays/api_response_fr.json"
)
HOLIDAY_API_RESPONSE_US = load_json_mock(
    "market_overview/tests/mock_web_data/holidays/api_response_us.json"
)
HOLIDAY_API_RESPONSE_JP = {}
HOLIDAY_API_RESPONSE_ALL = [
    HOLIDAY_API_RESPONSE_US,
    HOLIDAY_API_RESPONSE_FR,
    HOLIDAY_API_RESPONSE_JP,
]


class TestHolidaysIngestionViews(TestCase):
    """Test cases for Holidays Ingestion Views."""

    INGEST_HOLIDAYS_URL = "/ingest"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/markets/holidays"

    @freeze_time("2025-01-01")
    @patch("market_overview.services.holiday_services._call_holiday_api")
    def test_ingest_holidays_success(self, mock_call_holiday_api):
        """
        GIVEN a holiday API response
        WHEN ingesting holidays
        THEN the holidays should be ingested successfully
        """
        mock_call_holiday_api.side_effect = HOLIDAY_API_RESPONSE_ALL
        response = self.client.post(f"{self.base_url}{self.INGEST_HOLIDAYS_URL}")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"message": "Holidays successfully ingested."}
        assert mock_call_holiday_api.call_count == 3
        assert HolidayModel.objects.all().count() == sum(
            len(response) for response in HOLIDAY_API_RESPONSE_ALL
        )

    @freeze_time("2025-01-01")
    @patch("market_overview.services.holiday_services._call_holiday_api")
    def test_ingest_holidays_with_location(self, mock_call_holiday_api):
        """
        GIVEN a holiday API response
        WHEN ingesting holidays with a specific location
        THEN the holidays should be ingested successfully for the specific location
        """
        mock_call_holiday_api.return_value = HOLIDAY_API_RESPONSE_FR
        payload = {"location": LocationChoices.US.value}
        response = self.client.post(
            f"{self.base_url}{self.INGEST_HOLIDAYS_URL}",
            data=payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"message": "Holidays successfully ingested."}
        assert HolidayModel.objects.filter().count() == len(HOLIDAY_API_RESPONSE_FR)
        other_holidays_nb = HolidayModel.objects.exclude(
            location=LocationChoices.FR.value
        ).count()
        assert other_holidays_nb == 0

    @freeze_time("2025-01-01")
    @patch("market_overview.services.holiday_services._call_holiday_api")
    def test_ingest_holidays_with_date_parameter(self, mock_call_holiday_api):
        """
        GIVEN a holiday API response
        WHEN ingesting holidays with a date parameter
        THEN the holidays should be ingested successfully for the specific date
        """
        mock_call_holiday_api.return_value = HOLIDAY_API_RESPONSE_FR
        test_date = date(2025, 11, 1)
        payload = {"date": test_date.isoformat()}
        response = self.client.post(
            f"{self.base_url}{self.INGEST_HOLIDAYS_URL}",
            data=payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"message": "Holidays successfully ingested."}
        assert HolidayModel.objects.all().count() == len(
            [
                data
                for data in HOLIDAY_API_RESPONSE_FR
                if data["date"] >= test_date.isoformat()
            ]
        )
        assert HolidayModel.objects.filter(date__lt=test_date).count() == 0

    @freeze_time("2025-11-01")
    @patch("market_overview.services.holiday_services._call_holiday_api")
    def test_ingest_holidays_over_year(self, mock_call_holiday_api):
        """
        GIVEN a holiday API response
        WHEN ingesting holidays without a date parameter
        THEN API should be called twice (over the year), starting from the current date
        """
        mock_call_holiday_api.side_effect = [HOLIDAY_API_RESPONSE_FR, {}]
        payload = {"location": LocationChoices.FR.value}
        response = self.client.post(
            f"{self.base_url}{self.INGEST_HOLIDAYS_URL}",
            data=payload,
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"message": "Holidays successfully ingested."}
        assert mock_call_holiday_api.call_count == 2


class TestHolidaysViews(TestCase):
    """Test cases for Holidays Views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_date = date(2025, 11, 1)
        self.base_url = "/markets/holidays"
        HolidayModel.objects.create(
            date=self.base_date,
            name="Test US Holiday",
            location=LocationChoices.US.value,
        )
        HolidayModel.objects.create(
            date=date(2025, 1, 1),
            name="Test FR Holiday",
            location=LocationChoices.FR.value,
        )
        HolidayModel.objects.create(
            date=date(2026, 5, 1),
            name="Test JP Holiday",
            location=LocationChoices.JP.value,
        )
        HolidayModel.objects.create(
            date=self.base_date,
            name="Other Test JP Holiday",
            location=LocationChoices.JP.value,
        )

    def test_list_holidays_success(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays
        THEN all holidays should be listed successfully
        """
        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": self.base_date.isoformat(),
                "location": "US",
                "name": "Test US Holiday",
            },
            {
                "date": "2025-01-01",
                "location": "FR",
                "name": "Test FR Holiday",
            },
            {
                "date": "2026-05-01",
                "location": "JP",
                "name": "Test JP Holiday",
            },
            {
                "date": self.base_date.isoformat(),
                "location": "JP",
                "name": "Other Test JP Holiday",
            },
        ]

    def test_list_holidays_with_filters_success(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays with filters
        THEN the holidays should be listed successfully for the specific filters
        """
        params = {
            "location": LocationChoices.JP.value,
            "year": 2026,
            "months": 5,
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": "2026-05-01",
                "location": "JP",
                "name": "Test JP Holiday",
            }
        ]

    def test_list_holidays_with_location_only(self):
        """Test GET with location filter only."""
        params = {
            "location": LocationChoices.JP.value,
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": "2026-05-01",
                "location": "JP",
                "name": "Test JP Holiday",
            },
            {
                "date": self.base_date.isoformat(),
                "location": "JP",
                "name": "Other Test JP Holiday",
            },
        ]

    def test_list_holidays_with_year_only(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays with year filter only
        THEN the holidays should be listed successfully for the specific year
        """
        params = {
            "year": 2025,
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": self.base_date.isoformat(),
                "location": "US",
                "name": "Test US Holiday",
            },
            {
                "date": "2025-01-01",
                "location": "FR",
                "name": "Test FR Holiday",
            },
            {
                "date": self.base_date.isoformat(),
                "location": "JP",
                "name": "Other Test JP Holiday",
            },
        ]

    def test_list_holidays_with_months_only(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays with months filter only
        THEN the holidays should be listed successfully for the specific months
        """
        params = {
            "months": "1,2,3,4,5",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": "2025-01-01",
                "location": "FR",
                "name": "Test FR Holiday",
            },
            {
                "date": "2026-05-01",
                "location": "JP",
                "name": "Test JP Holiday",
            },
        ]

    def test_list_holidays_with_filters_empty(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays with filters
        THEN the holidays should be listed successfully for the specific filters
        """
        params = {
            "location": LocationChoices.US.value,
            "year": 2025,
            "months": "1,2,3",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_holidays_with_invalid_months_format(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays with invalid months format
        THEN a 400 Bad Request should be returned
        """
        params = {
            "months": "invalid,format",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"error_message": {"months": ["Invalid month."]}}

    def test_list_holidays_with_invalid_location(self):
        """
        GIVEN holidays in the database
        WHEN listing holidays with invalid location
        THEN a 400 Bad Request should be returned
        """
        params = {
            "location": "INVALID",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"location": ['"INVALID" is not a valid choice.']}
        }

    def test_delete_holidays_success(self):
        """
        GIVEN holidays in the database
        WHEN deleting holidays for a given dates
        THEN all holidays before the given date should be deleted successfully
        """
        assert HolidayModel.objects.all().count() == 4
        query_params = f"date={(self.base_date + timedelta(days=1)).isoformat()}"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Holidays successfully deleted."}
        assert HolidayModel.objects.all().count() == 1

    def test_delete_holidays_missing_date(self):
        """
        GIVEN holidays in the database
        WHEN deleting holidays with missing date parameter
        THEN a 400 Bad Request should be returned
        """
        response = self.client.delete(self.base_url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]}
        }

    def test_delete_holidays_invalid_date_format(self):
        """
        GIVEN holidays in the database
        WHEN deleting holidays with invalid date format
        THEN a 400 Bad Request should be returned
        """
        response = self.client.delete(f"{self.base_url}?date=invalid-date")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "date": [
                    "Date has wrong format. Use one of these formats instead: YYYY-MM-DD."
                ]
            }
        }
