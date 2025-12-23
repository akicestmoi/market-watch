import json
from datetime import date, datetime, timezone

from django.test import Client, TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankDataModel,
    CentralBankMeetingModel,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)


@freeze_time("2025-12-16")
class TestCentralBanksRecapView(TestCase):
    """Test cases for central_banks_recap_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/central-banks-recap/"
        self.reference_date = date(2025, 12, 15)
        self.previous_date = date(2025, 12, 12)

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
        MarketPriceModel.objects.create(
            asset=self.effr_asset,
            date=self.reference_date,
            price=5.25,
        )

        MarketPriceModel.objects.create(
            asset=self.estr_asset,
            date=self.reference_date,
            price=4.0,
        )

        MarketPriceModel.objects.create(
            asset=self.mutan_asset,
            date=self.reference_date,
            price=0.1,
        )

        # Create central bank data
        self.frb_data = CentralBankDataModel.objects.create(
            cb_data_id=1,
            central_bank=CentralBankChoices.FRB,
            short_name="FRB_FEDFUNDS",
            full_name="FRB Target Fed Funds Rate",
            date=self.reference_date,
            value=5.25,
            comment="",
        )

        # Create meeting dates
        self.frb_meeting = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=datetime(2026, 3, 20, 13, 0, 0, tzinfo=timezone.utc),
        )

        # Create STIR futures prices for probability matrix generation
        # FRB futures - need multiple maturities for probability calculation
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.reference_date,
            price=95.25,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.reference_date,
            price=95.30,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.reference_date,
            price=95.35,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        # Add future after meeting date (required for validation)
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.04",
            first_accrual_date=date(2026, 4, 1),
            last_accrual_date=date(2026, 4, 30),
            date=self.reference_date,
            price=95.40,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        # Also create for previous_date to enable probability_change_matrix
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.01",
            first_accrual_date=date(2026, 1, 1),
            last_accrual_date=date(2026, 1, 31),
            date=self.previous_date,
            price=95.20,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.02",
            first_accrual_date=date(2026, 2, 1),
            last_accrual_date=date(2026, 2, 28),
            date=self.previous_date,
            price=95.25,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.03",
            first_accrual_date=date(2026, 3, 1),
            last_accrual_date=date(2026, 3, 31),
            date=self.previous_date,
            price=95.30,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="26.04",
            first_accrual_date=date(2026, 4, 1),
            last_accrual_date=date(2026, 4, 30),
            date=self.previous_date,
            price=95.35,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

    def test_central_banks_recap_view_success(self):
        """
        GIVEN central bank data, effective rates, and meeting dates
        WHEN accessing central banks recap view
        THEN the view renders successfully with central bank data
        """
        response = self.client.get(
            self.base_url,
            {
                "reference_date": self.reference_date.isoformat(),
                "previous_date": self.previous_date.isoformat(),
            },
        )

        assert response.status_code == 200
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()

        central_banks_data = response.context.get("central_banks_data")
        assert central_banks_data == {
            CentralBankChoices.BOJ: {
                "data": [
                    {"label": "Effective Rate", "value": "0.1 %"},
                    {"label": "Next Meeting", "value": "N/A"},
                    {"label": "Japan Inflation Rate", "value": "2.9 %"},
                ],
                "display_name": "Bank of Japan (BOJ)",
                "probability_change_matrix": None,
                "probability_matrix": None,
            },
            CentralBankChoices.ECB: {
                "data": [
                    {"label": "Effective Rate", "value": "4.0 %"},
                    {"label": "Next Meeting", "value": "N/A"},
                    {"label": "France Inflation Rate", "value": "0.9 %"},
                    {"label": "Eurozone Inflation Rate", "value": "2.1 %"},
                ],
                "display_name": "European Central Bank (ECB)",
                "probability_change_matrix": None,
                "probability_matrix": None,
            },
            CentralBankChoices.FRB: {
                "data": [
                    {"label": "Effective Rate", "value": "5.25 %"},
                    {"label": "FRB Target Fed Funds Rate", "value": "5.25 %"},
                    {"label": "Next Meeting", "value": "2026-03-20"},
                    {"label": "US Inflation Rate", "value": "3.0 %"},
                ],
                "display_name": "Federal Reserve (FRB)",
                "probability_change_matrix": None,
                "probability_matrix": {
                    "central_bank": CentralBankChoices.FRB,
                    "meeting_dates": [date(2026, 3, 20)],
                    "probability_matrix": [
                        {"expected_rate_step": -25, "probabilities": [31.0]},
                        {"expected_rate_step": 0, "probabilities": [69.0]},
                    ],
                },
            },
        }

    def test_central_banks_recap_view_with_probability_matrix(self):
        """
        GIVEN STIR futures prices and meeting dates
        WHEN accessing central banks recap view
        THEN probability matrix is populated with data
        """
        response = self.client.get(
            self.base_url,
            {
                "reference_date": self.reference_date.isoformat(),
                "previous_date": self.previous_date.isoformat(),
            },
        )

        assert response.status_code == 200
        central_banks_data = response.context.get("central_banks_data")
        assert central_banks_data is not None
        frb_probability_matrix = central_banks_data[CentralBankChoices.FRB][
            "probability_matrix"
        ]
        assert frb_probability_matrix == {
            "central_bank": CentralBankChoices.FRB,
            "meeting_dates": [date(2026, 3, 20)],
            "probability_matrix": [
                {"expected_rate_step": -25, "probabilities": [31.0]},
                {"expected_rate_step": 0, "probabilities": [69.0]},
            ],
        }

    def test_central_banks_recap_view_default_dates(self):
        """
        GIVEN no date parameters
        WHEN accessing central banks recap view
        THEN default dates are used
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        assert response.context.get("reference_date") == "2025-12-15"
        assert response.context.get("previous_date") == "2025-12-12"

    def test_central_banks_recap_view_future_reference_date_error(self):
        """
        GIVEN reference date in the future
        WHEN accessing central banks recap view
        THEN an error message is added to context
        """
        future_date = date(2025, 12, 17)
        response = self.client.get(
            self.base_url,
            {
                "reference_date": future_date.isoformat(),
                "previous_date": self.previous_date.isoformat(),
            },
        )

        assert response.status_code == 200
        error_messages = response.context.get("error_messages")
        assert error_messages == json.dumps(
            {
                "reference_date": "Reference date: 2025-12-17 must be before today: 2025-12-16.",
                "FRB_data_item": "Error getting central bank data item for Federal Reserve (FRB): MarketPriceModel matching query does not exist.",
                "FRB_probability_matrix": "Error getting probability matrix for Federal Reserve (FRB): MarketPriceModel matching query does not exist.",
                "FRB_probability_change_matrix": "Error getting probability change matrix for Federal Reserve (FRB): MarketPriceModel matching query does not exist.",
                "ECB_data_item": "Error getting central bank data item for European Central Bank (ECB): MarketPriceModel matching query does not exist.",
                "ECB_probability_matrix": "Error getting probability matrix for European Central Bank (ECB): MarketPriceModel matching query does not exist.",
                "ECB_probability_change_matrix": "Error getting probability change matrix for European Central Bank (ECB): MarketPriceModel matching query does not exist.",
                "BOJ_data_item": "Error getting central bank data item for Bank of Japan (BOJ): MarketPriceModel matching query does not exist.",
                "BOJ_probability_matrix": "Error getting probability matrix for Bank of Japan (BOJ): MarketPriceModel matching query does not exist.",
                "BOJ_probability_change_matrix": "Error getting probability change matrix for Bank of Japan (BOJ): MarketPriceModel matching query does not exist.",
            }
        )

    def test_central_banks_recap_view_all_central_banks(self):
        """
        GIVEN data for all central banks
        WHEN accessing central banks recap view
        THEN data for all central banks is returned
        """
        CentralBankDataModel.objects.create(
            cb_data_id=2,
            central_bank=CentralBankChoices.ECB,
            short_name="ECB_Deposit",
            full_name="ECB Deposit Facility Rate",
            date=self.reference_date,
            value=4.0,
            comment="",
        )
        CentralBankDataModel.objects.create(
            cb_data_id=5,
            central_bank=CentralBankChoices.BOJ,
            short_name="BOJ_MUTAN",
            full_name="BOJ Target Uncollateralized Overnight Rate",
            date=self.reference_date,
            value=0.1,
            comment="",
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=datetime(2026, 4, 15, 13, 15, 0, tzinfo=timezone.utc),
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            order=1,
            date=datetime(2026, 5, 1, 4, 0, 0, tzinfo=timezone.utc),
        )

        response = self.client.get(
            self.base_url,
            {
                "reference_date": self.reference_date.isoformat(),
                "previous_date": self.previous_date.isoformat(),
            },
        )

        assert response.status_code == 200
        central_banks_data = response.context.get("central_banks_data")
        assert central_banks_data == {
            CentralBankChoices.BOJ: {
                "data": [
                    {"label": "Effective Rate", "value": "0.1 %"},
                    {
                        "label": "BOJ Target Uncollateralized Overnight Rate",
                        "value": "0.1 %",
                    },
                    {"label": "Next Meeting", "value": "2026-05-01"},
                    {"label": "Japan Inflation Rate", "value": "2.9 %"},
                ],
                "display_name": "Bank of Japan (BOJ)",
                "probability_change_matrix": None,
                "probability_matrix": {
                    "central_bank": CentralBankChoices.BOJ,
                    "meeting_dates": [],
                    "probability_matrix": [],
                },
            },
            CentralBankChoices.ECB: {
                "data": [
                    {"label": "Effective Rate", "value": "4.0 %"},
                    {"label": "ECB Deposit Facility Rate", "value": "4.0 %"},
                    {"label": "Next Meeting", "value": "2026-04-15"},
                    {"label": "France Inflation Rate", "value": "0.9 %"},
                    {"label": "Eurozone Inflation Rate", "value": "2.1 %"},
                ],
                "display_name": "European Central Bank (ECB)",
                "probability_change_matrix": None,
                "probability_matrix": {
                    "central_bank": CentralBankChoices.ECB,
                    "meeting_dates": [],
                    "probability_matrix": [],
                },
            },
            CentralBankChoices.FRB: {
                "data": [
                    {"label": "Effective Rate", "value": "5.25 %"},
                    {"label": "FRB Target Fed Funds Rate", "value": "5.25 %"},
                    {"label": "Next Meeting", "value": "2026-03-20"},
                    {"label": "US Inflation Rate", "value": "3.0 %"},
                ],
                "display_name": "Federal Reserve (FRB)",
                "probability_change_matrix": None,
                "probability_matrix": {
                    "central_bank": CentralBankChoices.FRB,
                    "meeting_dates": [date(2026, 3, 20)],
                    "probability_matrix": [
                        {"expected_rate_step": -25, "probabilities": [31.0]},
                        {"expected_rate_step": 0, "probabilities": [69.0]},
                    ],
                },
            },
        }
