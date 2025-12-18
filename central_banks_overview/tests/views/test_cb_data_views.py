from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from central_banks_overview.models import CentralBankChoices, CentralBankDataModel


class TestCentralBankDataViews(TestCase):
    """Test cases for Central Bank Data API Views."""

    DATA_INGESTION_URL = "/ingest"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/central-banks/data"
        self.test_date = date(2024, 1, 15)
        self.test_date_2 = date(2024, 2, 15)

        # Create central bank data for FRB
        self.frb_data_1 = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        )
        self.frb_data_2 = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date_2,
            value=5.50,
            comment="",
        )

        # Create central bank data for ECB
        self.ecb_data_1 = CentralBankDataModel.objects.create(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=self.test_date,
            value=4.0,
            comment="",
        )

    @patch(
        "central_banks_overview.services.cb_data_services.ingest_requested_central_bank_data"
    )
    def test_ingest_central_bank_data_success(self, mock_ingest):
        """
        GIVEN valid central bank data ingestion request
        WHEN ingesting central bank data
        THEN the data is successfully ingested
        """
        mock_ingest.return_value = [
            {
                "data_name": "FRB Target Fed Funds Rate",
                "date": self.test_date,
            }
        ]

        payload = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "date": self.test_date.isoformat(),
            }
        ]
        response = self.client.post(
            f"{self.base_url}{self.DATA_INGESTION_URL}",
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Central Bank Data successfully ingested",
            "updates": [
                {
                    "data_name": "FRB Target Fed Funds Rate",
                    "date": self.test_date.isoformat(),
                }
            ],
        }
        mock_ingest.assert_called_once()

    @patch(
        "central_banks_overview.services.cb_data_services.ingest_requested_central_bank_data"
    )
    def test_ingest_central_bank_data_multiple_central_banks(self, mock_ingest):
        """
        GIVEN request with multiple central banks
        WHEN ingesting central bank data
        THEN data for all central banks is ingested
        """
        mock_ingest.return_value = []

        payload = [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "date": self.test_date.isoformat(),
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "date": self.test_date.isoformat(),
            },
        ]
        response = self.client.post(
            f"{self.base_url}{self.DATA_INGESTION_URL}",
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Central Bank Data successfully ingested",
            "updates": [],
        }
        mock_ingest.assert_called_once()

    def test_ingest_central_bank_data_invalid_central_bank(self):
        """
        GIVEN request with invalid central bank value
        WHEN ingesting central bank data
        THEN a validation error is returned
        """
        payload = [
            {
                "central_bank": "INVALID",
                "date": self.test_date.isoformat(),
            },
        ]
        response = self.client.post(
            f"{self.base_url}{self.DATA_INGESTION_URL}",
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ingest_central_bank_data_missing_date(self):
        """
        GIVEN request without date
        WHEN ingesting central bank data
        THEN a validation error is returned
        """
        payload = [
            {
                "central_bank": CentralBankChoices.FRB.value,
            },
        ]
        response = self.client.post(
            f"{self.base_url}{self.DATA_INGESTION_URL}",
            payload,
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_central_bank_data_with_date(self):
        """
        GIVEN central bank data for a specific date
        WHEN listing central bank data with date parameter
        THEN the correct data for that date is returned
        """
        params = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.get(f"{self.base_url}", params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date.isoformat(),
                "value": 5.25,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "short_name": "ECB_Deposit",
                "full_name": "ECB Deposit Facility Rate",
                "date": self.test_date.isoformat(),
                "value": 4.0,
                "comment": "",
            },
        ]

    def test_list_central_bank_data_with_central_banks_filter(self):
        """
        GIVEN central bank data for multiple central banks
        WHEN listing central bank data with central_banks filter
        THEN only data for specified central banks is returned
        """
        params = {
            "date": self.test_date.isoformat(),
            "central_banks": CentralBankChoices.FRB.value,
        }
        response = self.client.get(f"{self.base_url}", params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date.isoformat(),
                "value": 5.25,
                "comment": "",
            },
        ]

    def test_list_central_bank_data_with_multiple_central_banks_filter(self):
        """
        GIVEN central bank data for multiple central banks
        WHEN listing central bank data with comma-separated central_banks
        THEN data for all specified central banks is returned
        """
        params = {
            "date": self.test_date.isoformat(),
            "central_banks": f"{CentralBankChoices.FRB.value},{CentralBankChoices.ECB.value}",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date.isoformat(),
                "value": 5.25,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "short_name": "ECB_Deposit",
                "full_name": "ECB Deposit Facility Rate",
                "date": self.test_date.isoformat(),
                "value": 4.0,
                "comment": "",
            },
        ]

    def test_list_central_bank_data_with_last_value(self):
        """
        GIVEN central bank data for multiple dates
        WHEN listing central bank data with last_value=True
        THEN only the latest data for each short_name is returned
        """
        params = {
            "last_value": True,
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "short_name": "ECB_Deposit",
                "full_name": "ECB Deposit Facility Rate",
                "date": self.test_date.isoformat(),
                "value": 4.0,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date_2.isoformat(),
                "value": 5.50,
                "comment": "",
            },
        ]

    def test_list_central_bank_data_no_filters(self):
        """
        GIVEN central bank data in the database
        WHEN listing central bank data without filters
        THEN all data is returned
        """
        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date.isoformat(),
                "value": 5.25,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "short_name": "FRB_FEDFUNDS",
                "full_name": "FRB Target Fed Funds Rate",
                "date": self.test_date_2.isoformat(),
                "value": 5.50,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "short_name": "ECB_Deposit",
                "full_name": "ECB Deposit Facility Rate",
                "date": self.test_date.isoformat(),
                "value": 4.0,
                "comment": "",
            },
        ]

    def test_list_central_bank_data_empty(self):
        """
        GIVEN no central bank data for a date
        WHEN listing central bank data for that date
        THEN an empty list is returned
        """
        params = {
            "date": date(2025, 1, 1).isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
