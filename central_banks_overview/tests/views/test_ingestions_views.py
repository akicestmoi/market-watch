# from datetime import date
# from unittest.mock import patch

# from django.core.files.uploadedfile import SimpleUploadedFile
# from django.test import TestCase
# from rest_framework import status
# from rest_framework.test import APIClient

# from central_banks_overview.models import (
#     CentralBankChoices,
#     StirFuturesNameChoices,
#     StirFuturesSourceChoices,
# )


# class TestStirFuturesIngestionViews(TestCase):
#     """Test cases for STIR Futures Ingestion API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/stir-futures/ingest"
#         self.test_date = date(2024, 1, 15)

#     @patch(
#         "central_banks_overview.services.stir_prices_ingestion_services.extract_all_stir_futures_prices"
#     )
#     @patch(
#         "central_banks_overview.services.stir_prices_ingestion_services.ingest_stir_futures_prices"
#     )
#     def test_ingest_stir_futures_prices_success(self, mock_ingest, mock_extract):
#         """
#         GIVEN valid date for STIR futures ingestion
#         WHEN ingesting STIR futures prices
#         THEN the prices are successfully ingested
#         """
#         mock_extract.return_value = [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "short_name": StirFuturesNameChoices.FF1M,
#                 "full_name": "1 Month Fed Funds STIR Futures",
#                 "maturity": "24.01",
#                 "first_accrual_date": date(2024, 1, 1),
#                 "last_accrual_date": date(2024, 1, 31),
#                 "date": self.test_date,
#                 "price": 95.25,
#                 "source": StirFuturesSourceChoices.YAHOO,
#                 "comment": "",
#             }
#         ]
#         mock_ingest.return_value = [
#             {
#                 "short_name": StirFuturesNameChoices.FF1M,
#                 "maturity": "24.01",
#             }
#         ]

#         response = self.client.post(self.base_url, {"date": self.test_date.isoformat()})

#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["message"] == "STIR Futures prices successfully ingested"
#         assert data["date"] == self.test_date.isoformat()
#         assert len(data["stir_futures_updated"]) > 0
#         mock_extract.assert_called_once_with(self.test_date)
#         mock_ingest.assert_called_once()

#     @patch(
#         "central_banks_overview.services.stir_prices_ingestion_services.extract_all_stir_futures_prices"
#     )
#     @patch(
#         "central_banks_overview.services.stir_prices_ingestion_services.ingest_stir_futures_prices"
#     )
#     def test_ingest_stir_futures_prices_empty_result(self, mock_ingest, mock_extract):
#         """
#         GIVEN date with no STIR futures prices available
#         WHEN ingesting STIR futures prices
#         THEN an empty list is returned
#         """
#         mock_extract.return_value = []
#         mock_ingest.return_value = []

#         response = self.client.post(self.base_url, {"date": self.test_date.isoformat()})

#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["message"] == "STIR Futures prices successfully ingested"
#         assert data["stir_futures_updated"] == []

#     def test_ingest_stir_futures_prices_missing_date(self):
#         """
#         GIVEN request without date
#         WHEN ingesting STIR futures prices
#         THEN a validation error is returned
#         """
#         response = self.client.post(self.base_url, {})

#         assert response.status_code == status.HTTP_400_BAD_REQUEST


# class TestEstrPriceIngestionViaPdfViews(TestCase):
#     """Test cases for ESTR Price Ingestion via PDF API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/stir-futures/ingest-estr-pdf"
#         self.test_date = date(2024, 1, 15)

#     @patch(
#         "central_banks_overview.services.stir_prices_ingestion_services.extract_estr_prices_from_pdf"
#     )
#     @patch(
#         "central_banks_overview.services.stir_prices_ingestion_services.ingest_stir_futures_prices"
#     )
#     def test_ingest_estr_prices_via_pdf_success(self, mock_ingest, mock_extract):
#         """
#         GIVEN valid PDF file and date
#         WHEN ingesting ESTR prices via PDF
#         THEN the prices are successfully ingested
#         """
#         mock_extract.return_value = [
#             {
#                 "central_bank": CentralBankChoices.ECB,
#                 "short_name": StirFuturesNameChoices.ESTR3M,
#                 "full_name": "3 Month ESTR Futures",
#                 "maturity": "24.03",
#                 "first_accrual_date": date(2024, 3, 1),
#                 "last_accrual_date": date(2024, 3, 31),
#                 "date": self.test_date,
#                 "price": 96.50,
#                 "source": StirFuturesSourceChoices.PDF,
#                 "comment": "",
#             }
#         ]
#         mock_ingest.return_value = [
#             {
#                 "short_name": StirFuturesNameChoices.ESTR3M,
#                 "maturity": "24.03",
#             }
#         ]

#         pdf_file = SimpleUploadedFile(
#             "test.pdf", b"fake pdf content", content_type="application/pdf"
#         )

#         response = self.client.post(
#             self.base_url,
#             {"pdf_file": pdf_file, "date": self.test_date.isoformat()},
#             format="multipart",
#         )

#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["message"] == "STIR Futures prices successfully ingested"
#         assert data["date"] == self.test_date.isoformat()
#         mock_extract.assert_called_once()
#         mock_ingest.assert_called_once()

#     def test_ingest_estr_prices_via_pdf_missing_file(self):
#         """
#         GIVEN request without PDF file
#         WHEN ingesting ESTR prices via PDF
#         THEN a validation error is returned
#         """
#         response = self.client.post(self.base_url, {"date": self.test_date.isoformat()})

#         assert response.status_code == status.HTTP_400_BAD_REQUEST

#     def test_ingest_estr_prices_via_pdf_missing_date(self):
#         """
#         GIVEN request without date
#         WHEN ingesting ESTR prices via PDF
#         THEN a validation error is returned
#         """
#         pdf_file = SimpleUploadedFile(
#             "test.pdf", b"fake pdf content", content_type="application/pdf"
#         )

#         response = self.client.post(
#             self.base_url, {"pdf_file": pdf_file}, format="multipart"
#         )

#         assert response.status_code == status.HTTP_400_BAD_REQUEST


# class TestCentralBankMeetingDatesIngestionViews(TestCase):
#     """Test cases for Central Bank Meeting Dates Ingestion API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/meeting-dates/ingest"

#     @patch(
#         "central_banks_overview.services.cb_meetings_services.ingest_central_bank_meeting_dates"
#     )
#     def test_ingest_meeting_dates_success(self, mock_ingest):
#         """
#         GIVEN a request to ingest meeting dates
#         WHEN ingesting central bank meeting dates
#         THEN the meeting dates are successfully ingested
#         """
#         mock_ingest.return_value = None

#         response = self.client.post(self.base_url)

#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["message"] == "Central Bank Meeting Dates successfully ingested"
#         mock_ingest.assert_called_once()


# class TestCentralBankDataIngestionViews(TestCase):
#     """Test cases for Central Bank Data Ingestion API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/data/ingest"
#         self.test_date = date(2024, 1, 15)

#     @patch(
#         "central_banks_overview.services.cb_data_services.get_specific_central_bank_data"
#     )
#     @patch(
#         "central_banks_overview.services.cb_data_services.get_all_central_bank_data_dates"
#     )
#     def test_ingest_central_bank_data_success(
#         self, mock_get_dates, mock_get_specific_data
#     ):
#         """
#         GIVEN valid central bank data ingestion request
#         WHEN ingesting central bank data
#         THEN the data is successfully ingested
#         """
#         mock_get_dates.return_value = [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "date": self.test_date,
#             }
#         ]
#         mock_get_specific_data.return_value = {
#             "cb_data_id": 1,
#             "central_bank": CentralBankChoices.FRB,
#             "short_name": "FRB_FEDFUNDS",
#             "full_name": "FRB Target Fed Funds Rate",
#             "date": self.test_date,
#             "value": 5.25,
#             "comment": "",
#         }

#         response = self.client.post(
#             self.base_url,
#             [
#                 {
#                     "central_bank": CentralBankChoices.FRB.value,
#                     "date": self.test_date.isoformat(),
#                 }
#             ],
#             format="json",
#         )

#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["message"] == "Central Bank Data successfully ingested"
#         assert len(data["updates"]) > 0
#         mock_get_dates.assert_called_once()
#         mock_get_specific_data.assert_called()

#     @patch(
#         "central_banks_overview.services.cb_data_services.get_all_central_bank_data_dates"
#     )
#     def test_ingest_central_bank_data_multiple_central_banks(self, mock_get_dates):
#         """
#         GIVEN request with multiple central banks
#         WHEN ingesting central bank data
#         THEN data for all central banks is ingested
#         """
#         mock_get_dates.return_value = [
#             {
#                 "central_bank": CentralBankChoices.FRB,
#                 "date": self.test_date,
#             },
#             {
#                 "central_bank": CentralBankChoices.ECB,
#                 "date": self.test_date,
#             },
#         ]

#         response = self.client.post(
#             self.base_url,
#             [
#                 {
#                     "central_bank": CentralBankChoices.FRB.value,
#                     "date": self.test_date.isoformat(),
#                 },
#                 {
#                     "central_bank": CentralBankChoices.ECB.value,
#                     "date": self.test_date.isoformat(),
#                 },
#             ],
#             format="json",
#         )

#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["message"] == "Central Bank Data successfully ingested"
#         mock_get_dates.assert_called_once()

#     def test_ingest_central_bank_data_invalid_central_bank(self):
#         """
#         GIVEN request with invalid central bank value
#         WHEN ingesting central bank data
#         THEN a validation error is returned
#         """
#         response = self.client.post(
#             self.base_url,
#             [{"central_bank": "INVALID", "date": self.test_date.isoformat()}],
#             format="json",
#         )

#         assert response.status_code == status.HTTP_400_BAD_REQUEST

#     def test_ingest_central_bank_data_missing_date(self):
#         """
#         GIVEN request without date
#         WHEN ingesting central bank data
#         THEN a validation error is returned
#         """
#         response = self.client.post(
#             self.base_url,
#             [{"central_bank": CentralBankChoices.FRB.value}],
#             format="json",
#         )

#         assert response.status_code == status.HTTP_400_BAD_REQUEST
