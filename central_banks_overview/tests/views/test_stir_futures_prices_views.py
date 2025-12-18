import csv
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)


class TestStirFuturesViews(TestCase):
    """Test cases for STIR Futures API Views."""

    INGEST_URL = "/ingest"
    INGEST_ESTR_PDF_URL = "/ingest-estr-pdf"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/central-banks/stir-futures"
        self.test_date = date(2024, 1, 15)
        self.test_date_2 = date(2024, 2, 15)

        # Create FRB futures prices
        self.frb_future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.25,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

        # Create ECB futures prices
        self.ecb_future_1 = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 3, 31),
            date=self.test_date,
            price=96.50,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.extract_all_stir_futures_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.ingest_stir_futures_prices"
    )
    def test_ingest_stir_futures_prices_success(self, mock_ingest, mock_extract):
        """
        GIVEN valid date for STIR futures ingestion
        WHEN ingesting STIR futures prices
        THEN the prices are successfully ingested
        """
        mock_extract.return_value = [
            {
                "central_bank": CentralBankChoices.FRB,
                "short_name": StirFuturesNameChoices.FF1M,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1),
                "last_accrual_date": date(2024, 1, 31),
                "date": self.test_date,
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO,
                "comment": "",
            }
        ]
        mock_ingest.return_value = [
            {
                "short_name": StirFuturesNameChoices.FF1M,
                "maturity": "24.01",
            }
        ]

        payload = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.post(
            f"{self.base_url}{self.INGEST_URL}", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "STIR Futures prices successfully ingested",
            "date": self.test_date.isoformat(),
            "stir_futures_updated": [
                f"{StirFuturesNameChoices.FF1M.value}.24.01",
            ],
        }
        mock_extract.assert_called_once_with(self.test_date)
        mock_ingest.assert_called_once()

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.extract_all_stir_futures_prices"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.ingest_stir_futures_prices"
    )
    def test_ingest_stir_futures_prices_empty_result(self, mock_ingest, mock_extract):
        """
        GIVEN date with no STIR futures prices available
        WHEN ingesting STIR futures prices
        THEN an empty list is returned
        """
        mock_extract.return_value = []
        mock_ingest.return_value = []

        payload = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.post(
            f"{self.base_url}{self.INGEST_URL}", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "STIR Futures prices successfully ingested",
            "date": self.test_date.isoformat(),
            "stir_futures_updated": [],
        }

    def test_ingest_stir_futures_prices_missing_date(self):
        """
        GIVEN request without date
        WHEN ingesting STIR futures prices
        THEN a validation error is returned
        """
        response = self.client.post(f"{self.base_url}{self.INGEST_URL}", {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]},
        }

    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.extract_estr_prices_from_pdf"
    )
    @patch(
        "central_banks_overview.services.stir_prices_ingestion_services.ingest_stir_futures_prices"
    )
    def test_ingest_estr_prices_via_pdf_success(self, mock_ingest, mock_extract):
        """
        GIVEN valid PDF file and date
        WHEN ingesting ESTR prices via PDF
        THEN the prices are successfully ingested
        """
        mock_extract.return_value = [
            {
                "central_bank": CentralBankChoices.ECB,
                "short_name": StirFuturesNameChoices.ESTR3M,
                "full_name": "3 Month ESTR Futures",
                "maturity": "24.03",
                "first_accrual_date": date(2024, 3, 1),
                "last_accrual_date": date(2024, 3, 31),
                "date": self.test_date,
                "price": 96.50,
                "source": StirFuturesSourceChoices.PDF,
                "comment": "",
            }
        ]
        mock_ingest.return_value = [
            {
                "short_name": StirFuturesNameChoices.ESTR3M,
                "maturity": "24.03",
            }
        ]

        pdf_file = SimpleUploadedFile(
            "test.pdf", b"fake pdf content", content_type="application/pdf"
        )
        payload = {
            "pdf_file": pdf_file,
            "date": self.test_date.isoformat(),
        }
        response = self.client.post(
            f"{self.base_url}{self.INGEST_ESTR_PDF_URL}",
            data=payload,
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "STIR Futures prices successfully ingested",
            "date": self.test_date.isoformat(),
            "stir_futures_updated": [
                f"{StirFuturesNameChoices.ESTR3M.value}.24.03",
            ],
        }
        mock_extract.assert_called_once()
        mock_ingest.assert_called_once()

    def test_ingest_estr_prices_via_pdf_missing_file(self):
        """
        GIVEN request without PDF file
        WHEN ingesting ESTR prices via PDF
        THEN a validation error is returned
        """
        payload = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.post(
            f"{self.base_url}{self.INGEST_ESTR_PDF_URL}", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"pdf_file": ["No file was submitted."]},
        }

    def test_ingest_estr_prices_via_pdf_missing_date(self):
        """
        GIVEN request without date
        WHEN ingesting ESTR prices via PDF
        THEN a validation error is returned
        """
        pdf_file = SimpleUploadedFile(
            "test.pdf", b"fake pdf content", content_type="application/pdf"
        )
        payload = {
            "pdf_file": pdf_file,
        }
        response = self.client.post(
            f"{self.base_url}{self.INGEST_ESTR_PDF_URL}",
            data=payload,
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]},
        }

    def test_list_stir_futures_prices_with_date(self):
        """
        GIVEN futures prices for a specific date
        WHEN listing STIR futures prices with date parameter
        THEN the correct futures prices for that date are returned
        """
        params = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.ECB.value,
                "full_name": "3 Month ESTR Futures",
                "maturity": "24.03",
                "first_accrual_date": date(2024, 3, 1).isoformat(),
                "last_accrual_date": date(2024, 3, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 96.50,
                "source": StirFuturesSourceChoices.TFX.value,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
        ]

    def test_list_stir_futures_prices_with_central_banks_filter(self):
        """
        GIVEN futures prices for multiple central banks
        WHEN listing STIR futures prices with central_banks filter
        THEN only futures prices for specified central banks are returned
        """
        params = {
            "date": self.test_date.isoformat(),
            "central_banks": CentralBankChoices.FRB.value,
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
        ]

    def test_list_stir_futures_prices_empty(self):
        """
        GIVEN no futures prices for a date
        WHEN listing STIR futures prices for that date
        THEN an empty list is returned
        """
        params = {
            "date": date(2025, 1, 1).isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_stir_futures_prices_with_none_price(self):
        """
        GIVEN futures price with None value
        WHEN listing STIR futures prices
        THEN the futures with None price is still returned
        """
        StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name="3 Month Mutan STIR Futures",
            maturity="24.04",
            first_accrual_date=date(2024, 4, 1),
            last_accrual_date=date(2024, 4, 30),
            date=self.test_date,
            price=None,
            source=StirFuturesSourceChoices.TFX,
            comment="No price available",
        )

        params = {
            "date": self.test_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.BOJ.value,
                "full_name": "3 Month Mutan STIR Futures",
                "maturity": "24.04",
                "first_accrual_date": date(2024, 4, 1).isoformat(),
                "last_accrual_date": date(2024, 4, 30).isoformat(),
                "date": self.test_date.isoformat(),
                "price": None,
                "source": StirFuturesSourceChoices.TFX.value,
                "comment": "No price available",
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "full_name": "3 Month ESTR Futures",
                "maturity": "24.03",
                "first_accrual_date": date(2024, 3, 1).isoformat(),
                "last_accrual_date": date(2024, 3, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 96.50,
                "source": StirFuturesSourceChoices.TFX.value,
                "comment": "",
            },
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.25,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "",
            },
        ]


class TestBulkUpdateStirFuturesViews(TestCase):
    """Test cases for Bulk Update STIR Futures API Views."""

    BULK_UPDATE_URL = "/bulk-update"
    CSV_BULK_UPDATE_URL = "/bulk-update-from-csv"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/central-banks/stir-futures"
        self.test_date = date(2024, 1, 15)

        # Create futures to update
        self.frb_future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name="1 Month Fed Funds STIR Futures",
            maturity="24.01",
            first_accrual_date=date(2024, 1, 1),
            last_accrual_date=date(2024, 1, 31),
            date=self.test_date,
            price=95.0,
            source=StirFuturesSourceChoices.YAHOO,
            comment="",
        )

    def _create_csv_file(self, rows):
        """Helper to create CSV file from rows."""
        output = StringIO()
        writer = csv.DictWriter(
            output, fieldnames=["date", "short_name", "maturity", "price", "logs"]
        )
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)
        csv_content = output.getvalue()
        return SimpleUploadedFile(
            "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

    def test_bulk_update_stir_futures_prices_success(self):
        """
        GIVEN valid bulk update request
        WHEN bulk updating STIR futures prices
        THEN the prices are successfully updated
        """
        payload = [
            {
                "date": self.test_date.isoformat(),
                "short_name": StirFuturesNameChoices.FF1M.value,
                "maturity": "24.01",
                "price": 95.50,
                "logs": "Test update",
            },
        ]
        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_URL}", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.50,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Test update",
            },
        ]
        self.frb_future.refresh_from_db()
        assert self.frb_future.convert_to_dict() == {
            "central_bank": CentralBankChoices.FRB.value,
            "short_name": StirFuturesNameChoices.FF1M.value,
            "full_name": "1 Month Fed Funds STIR Futures",
            "maturity": "24.01",
            "first_accrual_date": date(2024, 1, 1),
            "last_accrual_date": date(2024, 1, 31),
            "date": self.test_date,
            "price": 95.50,
            "source": StirFuturesSourceChoices.YAHOO.value,
            "comment": "Test update",
        }

    def test_bulk_update_stir_futures_prices_empty_list(self):
        """
        GIVEN empty list of updates
        WHEN bulk updating STIR futures prices
        THEN an empty list is returned
        """
        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_URL}", data=[], format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_bulk_update_stir_futures_prices_multiple_updates(self):
        """
        GIVEN multiple updates
        WHEN bulk updating STIR futures prices
        THEN all prices are updated
        """
        # Create another future
        ecb_future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 3, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        payload = [
            {
                "date": self.test_date.isoformat(),
                "short_name": StirFuturesNameChoices.FF1M.value,
                "maturity": "24.01",
                "price": 95.75,
                "logs": "Update 1",
            },
            {
                "date": self.test_date.isoformat(),
                "short_name": StirFuturesNameChoices.ESTR3M.value,
                "maturity": "24.03",
                "price": 96.25,
                "logs": "Update 2",
            },
        ]
        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_URL}", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.75,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Update 1",
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "full_name": "3 Month ESTR Futures",
                "maturity": "24.03",
                "first_accrual_date": date(2024, 3, 1).isoformat(),
                "last_accrual_date": date(2024, 3, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 96.25,
                "source": StirFuturesSourceChoices.TFX.value,
                "comment": "Update 2",
            },
        ]
        self.frb_future.refresh_from_db()
        ecb_future.refresh_from_db()
        assert self.frb_future.convert_to_dict() == {
            "central_bank": CentralBankChoices.FRB.value,
            "short_name": StirFuturesNameChoices.FF1M.value,
            "full_name": "1 Month Fed Funds STIR Futures",
            "maturity": "24.01",
            "first_accrual_date": date(2024, 1, 1),
            "last_accrual_date": date(2024, 1, 31),
            "date": self.test_date,
            "price": 95.75,
            "source": StirFuturesSourceChoices.YAHOO.value,
            "comment": "Update 1",
        }
        assert ecb_future.convert_to_dict() == {
            "central_bank": CentralBankChoices.ECB.value,
            "short_name": StirFuturesNameChoices.ESTR3M.value,
            "full_name": "3 Month ESTR Futures",
            "maturity": "24.03",
            "first_accrual_date": date(2024, 3, 1),
            "last_accrual_date": date(2024, 3, 31),
            "date": self.test_date,
            "price": 96.25,
            "source": StirFuturesSourceChoices.TFX.value,
            "comment": "Update 2",
        }

    def test_bulk_update_from_csv_success(self):
        """
        GIVEN valid CSV file with updates
        WHEN bulk updating STIR futures prices from CSV
        THEN the prices are successfully updated
        """
        csv_file = self._create_csv_file(
            [
                {
                    "date": self.test_date.isoformat(),
                    "short_name": StirFuturesNameChoices.FF1M.value,
                    "maturity": "24.01",
                    "price": "95.50",
                    "logs": "CSV update",
                }
            ]
        )
        response = self.client.post(
            f"{self.base_url}{self.CSV_BULK_UPDATE_URL}",
            {"csv_file": csv_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.50,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "CSV update",
            },
        ]
        self.frb_future.refresh_from_db()
        assert self.frb_future.convert_to_dict() == {
            "central_bank": CentralBankChoices.FRB.value,
            "short_name": StirFuturesNameChoices.FF1M.value,
            "full_name": "1 Month Fed Funds STIR Futures",
            "maturity": "24.01",
            "first_accrual_date": date(2024, 1, 1),
            "last_accrual_date": date(2024, 1, 31),
            "date": self.test_date,
            "price": 95.50,
            "source": StirFuturesSourceChoices.YAHOO.value,
            "comment": "CSV update",
        }

    def test_bulk_update_from_csv_multiple_rows(self):
        """
        GIVEN CSV file with multiple rows
        WHEN bulk updating STIR futures prices from CSV
        THEN all prices are updated
        """
        # Create another future
        ecb_future = StirFuturesModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            short_name=StirFuturesNameChoices.ESTR3M,
            full_name="3 Month ESTR Futures",
            maturity="24.03",
            first_accrual_date=date(2024, 3, 1),
            last_accrual_date=date(2024, 3, 31),
            date=self.test_date,
            price=96.0,
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )

        csv_file = self._create_csv_file(
            [
                {
                    "date": self.test_date.isoformat(),
                    "short_name": StirFuturesNameChoices.FF1M.value,
                    "maturity": "24.01",
                    "price": "95.75",
                    "logs": "Update 1",
                },
                {
                    "date": self.test_date.isoformat(),
                    "short_name": StirFuturesNameChoices.ESTR3M.value,
                    "maturity": "24.03",
                    "price": "96.25",
                    "logs": "Update 2",
                },
            ]
        )

        response = self.client.post(
            f"{self.base_url}{self.CSV_BULK_UPDATE_URL}",
            {"csv_file": csv_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "central_bank": CentralBankChoices.FRB.value,
                "full_name": "1 Month Fed Funds STIR Futures",
                "maturity": "24.01",
                "first_accrual_date": date(2024, 1, 1).isoformat(),
                "last_accrual_date": date(2024, 1, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 95.75,
                "source": StirFuturesSourceChoices.YAHOO.value,
                "comment": "Update 1",
            },
            {
                "central_bank": CentralBankChoices.ECB.value,
                "full_name": "3 Month ESTR Futures",
                "maturity": "24.03",
                "first_accrual_date": date(2024, 3, 1).isoformat(),
                "last_accrual_date": date(2024, 3, 31).isoformat(),
                "date": self.test_date.isoformat(),
                "price": 96.25,
                "source": StirFuturesSourceChoices.TFX.value,
                "comment": "Update 2",
            },
        ]
        self.frb_future.refresh_from_db()
        ecb_future.refresh_from_db()
        assert self.frb_future.convert_to_dict() == {
            "central_bank": CentralBankChoices.FRB.value,
            "short_name": StirFuturesNameChoices.FF1M.value,
            "full_name": "1 Month Fed Funds STIR Futures",
            "maturity": "24.01",
            "first_accrual_date": date(2024, 1, 1),
            "last_accrual_date": date(2024, 1, 31),
            "date": self.test_date,
            "price": 95.75,
            "source": StirFuturesSourceChoices.YAHOO.value,
            "comment": "Update 1",
        }
        assert ecb_future.convert_to_dict() == {
            "central_bank": CentralBankChoices.ECB.value,
            "short_name": StirFuturesNameChoices.ESTR3M.value,
            "full_name": "3 Month ESTR Futures",
            "maturity": "24.03",
            "first_accrual_date": date(2024, 3, 1),
            "last_accrual_date": date(2024, 3, 31),
            "date": self.test_date,
            "price": 96.25,
            "source": StirFuturesSourceChoices.TFX.value,
            "comment": "Update 2",
        }

    def test_bulk_update_from_csv_missing_columns(self):
        """
        GIVEN CSV file with missing required columns
        WHEN bulk updating STIR futures prices from CSV
        THEN an error is returned
        """
        # Create CSV with missing columns
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=["date", "short_name"])
        writer.writeheader()
        writer.writerow(
            {
                "date": self.test_date.isoformat(),
                "short_name": StirFuturesNameChoices.FF1M,
            }
        )
        output.seek(0)
        csv_content = output.getvalue()
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        response = self.client.post(
            f"{self.base_url}{self.CSV_BULK_UPDATE_URL}",
            {"csv_file": csv_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error": "Value",
            "message": "Invalid request data. Please check your input.",
            "status_code": 400,
            "detail": {
                "exception": "CSV file must have the following columns: logs, maturity, price.",
            },
        }

    def test_bulk_update_from_csv_missing_file(self):
        """
        GIVEN request without CSV file
        WHEN bulk updating STIR futures prices from CSV
        THEN a validation error is returned
        """
        response = self.client.post(
            f"{self.base_url}{self.CSV_BULK_UPDATE_URL}", {}, format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"csv_file": ["No file was submitted."]},
        }
