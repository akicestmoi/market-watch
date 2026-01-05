from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankDataModel,
    CentralBankMeetingModel,
)
from central_banks_overview.services.cb_inference_services import (
    CentralBankProbabilityMatrix,
)
from data_visualization.services.central_bank_recap_services import (
    get_central_bank_data_item,
    get_central_bank_formatted_probability_matrix,
    get_formatted_probability_matrix_changes,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)


class TestCentralBankRecapServices(TestCase):
    """Test cases for central_bank_recap_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = date(2024, 1, 15)

        # Create EFFR asset for FRB effective rate
        self.effr_asset = AssetModel.objects.create(
            short_name="EFFR",
            full_name="Effective Fed Funds Rate",
            asset_id=7,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.US,
            ticker="500",
        )

        # Create ESTR asset for ECB effective rate
        self.estr_asset = AssetModel.objects.create(
            short_name="ESTR",
            full_name="Euro Short-Term Rate",
            asset_id=8,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.EU,
            ticker="ESTR",
        )

        # Create MUTAN asset for BOJ effective rate
        self.mutan_asset = AssetModel.objects.create(
            short_name="MUTAN",
            full_name="Uncollateralized Overnight Call Rate",
            asset_id=9,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.JP,
            ticker="MUTAN",
        )

        # Create market prices for effective rates
        self.effr_price = MarketPriceModel.objects.create(
            asset=self.effr_asset,
            date=self.test_date,
            price=5.25,
        )

        # Create central bank data
        self.frb_data = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.test_date,
            value=5.25,
            comment="",
        )

        # Create meeting dates
        self.frb_meeting = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc),
        )

    def test_get_central_bank_data_item_frb_success(self):
        """
        GIVEN central bank data, effective rate, and meeting date for FRB
        WHEN getting central bank data item
        THEN the correct data items are returned with FRB-specific additional data
        """
        result = get_central_bank_data_item(CentralBankChoices.FRB, self.test_date)
        assert result == [
            {"label": "Effective Rate", "value": "5.25 %"},
            {"label": "FRB Target Fed Funds Rate", "value": "5.25 %"},
            {"label": "Next Meeting", "value": "2024-03-20"},
            {"label": "US Inflation Rate", "value": "3.0 %"},
        ]

    def test_get_central_bank_data_item_ecb_success(self):
        """
        GIVEN central bank data, effective rate, and meeting date for ECB
        WHEN getting central bank data item
        THEN the correct data items are returned with ECB-specific additional data
        """
        CentralBankDataModel.objects.create(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=self.test_date,
            value=4.0,
            comment="",
        )
        MarketPriceModel.objects.create(
            asset=self.estr_asset,
            date=self.test_date,
            price=4.0,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=datetime(2024, 4, 15, 13, 15, 0, tzinfo=timezone.utc),
        )

        result = get_central_bank_data_item(CentralBankChoices.ECB, self.test_date)
        assert result == [
            {"label": "Effective Rate", "value": "4.0 %"},
            {"label": "ECB Deposit Facility Rate", "value": "4.0 %"},
            {"label": "Next Meeting", "value": "2024-04-15"},
            {"label": "France Inflation Rate", "value": "0.9 %"},
            {"label": "Eurozone Inflation Rate", "value": "2.1 %"},
        ]

    def test_get_central_bank_data_item_boj_success(self):
        """
        GIVEN central bank data, effective rate, and meeting date for BOJ
        WHEN getting central bank data item
        THEN the correct data items are returned with BOJ-specific additional data
        """
        CentralBankDataModel.objects.create(
            cb_data_id=5,
            central_bank=CentralBankChoices.BOJ,
            short_name="BOJ_MUTAN",
            full_name="BOJ Target Uncollateralized Overnight Rate",
            date=self.test_date,
            value=0.1,
            comment="",
        )
        MarketPriceModel.objects.create(
            asset=self.mutan_asset,
            date=self.test_date,
            price=0.1,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            order=1,
            date=datetime(2024, 5, 1, 4, 0, 0, tzinfo=timezone.utc),
        )

        result = get_central_bank_data_item(CentralBankChoices.BOJ, self.test_date)
        assert result == [
            {"label": "Effective Rate", "value": "0.1 %"},
            {"label": "BOJ Target Uncollateralized Overnight Rate", "value": "0.1 %"},
            {"label": "Next Meeting", "value": "2024-05-01"},
            {"label": "Japan Inflation Rate", "value": "2.9 %"},
        ]

    @patch(
        "data_visualization.services.central_bank_recap_services.cb_meetings_services.get_central_bank_next_meeting_date"
    )
    def test_get_central_bank_data_item_no_next_meeting(self, mock_next_meeting):
        """
        GIVEN central bank data without next meeting date
        WHEN getting central bank data item
        THEN N/A is returned for the next meeting
        """
        mock_next_meeting.return_value = None
        result = get_central_bank_data_item(CentralBankChoices.FRB, self.test_date)
        assert result == [
            {"label": "Effective Rate", "value": "5.25 %"},
            {"label": "FRB Target Fed Funds Rate", "value": "5.25 %"},
            {"label": "Next Meeting", "value": "N/A"},
            {"label": "US Inflation Rate", "value": "3.0 %"},
        ]

    def test_get_central_bank_data_item_no_value(self):
        """
        GIVEN central bank data with None value
        WHEN getting central bank data item
        THEN N/A is returned for that value
        """
        # Create data with None value
        CentralBankDataModel.objects.create(
            cb_data_id=3,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_TEST",
            full_name="FRB Test Rate",
            date=self.test_date,
            value=None,
            comment="No data",
        )

        result = get_central_bank_data_item(CentralBankChoices.FRB, self.test_date)
        assert result == [
            {"label": "Effective Rate", "value": "5.25 %"},
            {"label": "FRB Target Fed Funds Rate", "value": "5.25 %"},
            {"label": "FRB Test Rate", "value": "N/A"},
            {"label": "Next Meeting", "value": "2024-03-20"},
            {"label": "US Inflation Rate", "value": "3.0 %"},
        ]

    @patch(
        "data_visualization.services.central_bank_recap_services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_central_bank_formatted_probability_matrix_success(
        self, mock_get_matrices
    ):
        """
        GIVEN probability matrices from inference service
        WHEN getting formatted probability matrix
        THEN the matrix is sorted by expected_rate_step and returned
        """
        mock_get_matrices.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 25,
                        "probabilities": [0.3, 0.25],
                    },
                    {
                        "expected_rate_step": 0,
                        "probabilities": [0.7, 0.75],
                    },
                    {
                        "expected_rate_step": -25,
                        "probabilities": [0.0, 0.0],
                    },
                ],
            }
        ]

        result = get_central_bank_formatted_probability_matrix(
            CentralBankChoices.FRB, self.test_date
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {"expected_rate_step": -25, "probabilities": [0.0, 0.0]},
                {"expected_rate_step": 0, "probabilities": [0.7, 0.75]},
                {"expected_rate_step": 25, "probabilities": [0.3, 0.25]},
            ],
        }

    @patch(
        "data_visualization.services.central_bank_recap_services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_central_bank_formatted_probability_matrix_not_found(
        self, mock_get_matrices
    ):
        """
        GIVEN no probability matrix for central bank
        WHEN getting formatted probability matrix
        THEN None is returned
        """
        mock_get_matrices.return_value = []
        result = get_central_bank_formatted_probability_matrix(
            CentralBankChoices.FRB, self.test_date
        )
        assert result is None

    @patch(
        "data_visualization.services.central_bank_recap_services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_central_bank_formatted_probability_matrix_all_empty_probabilities(
        self, mock_get_matrices
    ):
        """
        GIVEN probability matrix with all probabilities empty
        WHEN getting formatted probability matrix
        THEN None is returned (empty probabilities are treated as no matrix)
        """
        mock_get_matrices.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [date(2024, 3, 20)],
                "probability_matrix": [
                    {
                        "expected_rate_step": 0,
                        "probabilities": [],
                    },
                    {
                        "expected_rate_step": 25,
                        "probabilities": [],
                    },
                ],
            }
        ]
        result = get_central_bank_formatted_probability_matrix(
            CentralBankChoices.FRB, self.test_date
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [],
        }

    def test_get_formatted_probability_matrix_changes_success(self):
        """
        GIVEN current and previous probability matrices
        WHEN getting formatted probability matrix changes
        THEN the changes are calculated and sorted by expected_rate_step
        """
        previous_matrix: CentralBankProbabilityMatrix = {
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
        current_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.75, 0.80],
                },
                {
                    "expected_rate_step": 25,
                    "probabilities": [0.25, 0.20],
                },
            ],
        }

        result = get_formatted_probability_matrix_changes(
            current_matrix, previous_matrix
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.05, 0.05],
                },
                {
                    "expected_rate_step": 25,
                    "probabilities": [-0.05, -0.05],
                },
            ],
        }

    def test_get_formatted_probability_matrix_changes_none_current(self):
        """
        GIVEN None current probability matrix
        WHEN getting formatted probability matrix changes
        THEN None is returned
        """
        previous_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.7],
                },
            ],
        }

        result = get_formatted_probability_matrix_changes(None, previous_matrix)
        assert result is None

    def test_get_formatted_probability_matrix_changes_none_previous(self):
        """
        GIVEN None previous probability matrix
        WHEN getting formatted probability matrix changes
        THEN None is returned
        """
        current_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.75],
                },
            ],
        }

        result = get_formatted_probability_matrix_changes(current_matrix, None)
        assert result is None

    def test_get_formatted_probability_matrix_changes_empty_current(self):
        """
        GIVEN current probability matrix with empty probability_matrix list
        WHEN getting formatted probability matrix changes
        THEN the empty probability_matrix list is returned
        """
        current_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [],
        }
        previous_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.7],
                },
            ],
        }

        result = get_formatted_probability_matrix_changes(
            current_matrix, previous_matrix
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [],
        }

    def test_get_formatted_probability_matrix_changes_empty_previous(self):
        """
        GIVEN previous probability matrix with empty probability_matrix list
        WHEN getting formatted probability matrix changes
        THEN the empty probability_matrix list is returned
        """
        current_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.75],
                },
            ],
        }
        previous_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [],
        }

        result = get_formatted_probability_matrix_changes(
            current_matrix, previous_matrix
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20)],
            "probability_matrix": [],
        }

    def test_get_formatted_probability_matrix_changes_no_changes(self):
        """
        GIVEN current and previous probability matrices with same probabilities
        WHEN getting formatted probability matrix changes
        THEN the change matrix shows zero differences
        """
        current_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.7, 0.75]},
                {"expected_rate_step": 25, "probabilities": [0.3, 0.25]},
            ],
        }
        previous_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.7, 0.75]},
                {"expected_rate_step": 25, "probabilities": [0.3, 0.25]},
            ],
        }

        result = get_formatted_probability_matrix_changes(
            current_matrix, previous_matrix
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.0, 0.0]},
                {"expected_rate_step": 25, "probabilities": [0.0, 0.0]},
            ],
        }

    @patch(
        "data_visualization.services.central_bank_recap_services.cb_inference_services.get_central_bank_probability_matrices"
    )
    def test_get_formatted_probability_matrix_changes_with_meeting_dates_override(
        self, mock_get_matrices
    ):
        """
        GIVEN current and previous probability matrices with different meeting dates
        WHEN getting formatted probability matrix changes with previous_date
        THEN the previous matrix is recalculated using current meeting dates
        """
        # Current matrix has meeting dates after a meeting occurred
        current_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 5, 1), date(2024, 6, 15)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.75, 0.80]},
                {"expected_rate_step": 25, "probabilities": [0.25, 0.20]},
            ],
        }
        # Previous matrix has old meeting dates (before meeting occurred)
        previous_matrix: CentralBankProbabilityMatrix = {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 3, 20), date(2024, 5, 1)],
            "probability_matrix": [
                {"expected_rate_step": 0, "probabilities": [0.7, 0.75]},
                {"expected_rate_step": 25, "probabilities": [0.3, 0.25]},
            ],
        }

        # Mock the recalculation to return a matrix with current meeting dates
        mock_get_matrices.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "meeting_dates": [date(2024, 5, 1), date(2024, 6, 15)],
                "probability_matrix": [
                    {"expected_rate_step": 0, "probabilities": [0.7, 0.75]},
                    {"expected_rate_step": 25, "probabilities": [0.3, 0.25]},
                ],
            }
        ]

        previous_date = date(2024, 1, 10)
        result = get_formatted_probability_matrix_changes(
            current_matrix, previous_matrix, previous_date=previous_date
        )
        assert result == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2024, 5, 1), date(2024, 6, 15)],
            "probability_matrix": [
                {
                    "expected_rate_step": 0,
                    "probabilities": [0.05, 0.05],
                },
                {
                    "expected_rate_step": 25,
                    "probabilities": [-0.05, -0.05],
                },
            ],
        }
