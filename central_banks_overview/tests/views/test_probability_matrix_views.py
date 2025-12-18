from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from central_banks_overview.models import CentralBankChoices


class TestGetCentralBankProbabilityMatrixViews(TestCase):
    """Test cases for Get Central Bank Probability Matrix API Views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/central-banks/probability-matrix"
        self.test_date = date(2024, 1, 15)

    @patch(
        "central_banks_overview.services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_probability_matrix_success(self, mock_get_matrices):
        """
        GIVEN valid date
        WHEN getting central bank probability matrices
        THEN the probability matrices are returned
        """
        mock_get_matrices.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.7, 0.75],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [0.3, 0.25],
                    },
                ],
            }
        ]

        params = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "meeting_dates": [
                    date(2024, 3, 20).isoformat(),
                    date(2024, 5, 1).isoformat(),
                ],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.7, 0.75],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [0.3, 0.25],
                    },
                ],
            },
        ]
        mock_get_matrices.assert_called_once_with(self.test_date, [])

    @patch(
        "central_banks_overview.services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_probability_matrix_with_central_banks_filter(self, mock_get_matrices):
        """
        GIVEN valid date and central banks filter
        WHEN getting central bank probability matrices
        THEN probability matrices for specified banks are returned
        """
        mock_get_matrices.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [date(2024, 3, 20)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.8],
                    },
                ],
            }
        ]

        params = {
            "date": self.test_date.isoformat(),
            "central_banks": CentralBankChoices.FRB.value,
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "meeting_dates": [date(2024, 3, 20).isoformat()],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.8],
                    },
                ],
            },
        ]
        mock_get_matrices.assert_called_once_with(
            self.test_date, [CentralBankChoices.FRB]
        )

    @patch(
        "central_banks_overview.services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_probability_matrix_multiple_central_banks(self, mock_get_matrices):
        """
        GIVEN valid date and multiple central banks
        WHEN getting central bank probability matrices
        THEN probability matrices for all specified banks are returned
        """
        mock_get_matrices.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [date(2024, 3, 20)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.8],
                    },
                ],
            },
            {
                "central_bank": CentralBankChoices.ECB,
                "meeting_dates": [date(2024, 4, 15)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.7],
                    },
                ],
            },
        ]

        params = {
            "date": self.test_date.isoformat(),
            "central_banks": f"{CentralBankChoices.FRB.value},{CentralBankChoices.ECB.value}",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "meeting_dates": [date(2024, 3, 20).isoformat()],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.8],
                    },
                ],
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "meeting_dates": [date(2024, 4, 15).isoformat()],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.7],
                    },
                ],
            },
        ]
        mock_get_matrices.assert_called_once_with(
            self.test_date, [CentralBankChoices.FRB, CentralBankChoices.ECB]
        )

    def test_get_probability_matrix_missing_date(self):
        """
        GIVEN request without date
        WHEN getting central bank probability matrices
        THEN a validation error is returned
        """
        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]},
        }
