# import csv
# from datetime import date
# from io import StringIO

# from django.core.files.uploadedfile import SimpleUploadedFile
# from django.test import TestCase
# from rest_framework import status
# from rest_framework.test import APIClient

# from central_banks_overview.models import (
#     CentralBankChoices,
#     StirFuturesModel,
#     StirFuturesNameChoices,
#     StirFuturesSourceChoices,
# )


# class TestStirFuturesViews(TestCase):
#     """Test cases for STIR Futures API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/stir-futures"
#         self.test_date = date(2024, 1, 15)
#         self.test_date_2 = date(2024, 2, 15)

#         # Create FRB futures prices
#         self.frb_future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=95.25,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         # Create ECB futures prices
#         self.ecb_future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=96.50,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#     def test_list_stir_futures_prices_with_date(self):
#         """
#         GIVEN futures prices for a specific date
#         WHEN listing STIR futures prices with date parameter
#         THEN the correct futures prices for that date are returned
#         """
#         response = self.client.get(self.base_url, {"date": self.test_date.isoformat()})

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2
#         central_banks = {item["central_bank"] for item in data}
#         assert CentralBankChoices.FRB.value in central_banks
#         assert CentralBankChoices.ECB.value in central_banks

#     def test_list_stir_futures_prices_with_central_banks_filter(self):
#         """
#         GIVEN futures prices for multiple central banks
#         WHEN listing STIR futures prices with central_banks filter
#         THEN only futures prices for specified central banks are returned
#         """
#         response = self.client.get(
#             self.base_url,
#             {
#                 "date": self.test_date.isoformat(),
#                 "central_banks": CentralBankChoices.FRB.value,
#             },
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 1
#         assert data[0]["central_bank"] == CentralBankChoices.FRB.value

#     def test_list_stir_futures_prices_empty(self):
#         """
#         GIVEN no futures prices for a date
#         WHEN listing STIR futures prices for that date
#         THEN an empty list is returned
#         """
#         response = self.client.get(
#             self.base_url, {"date": date(2025, 1, 1).isoformat()}
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert data == []

#     def test_list_stir_futures_prices_with_none_price(self):
#         """
#         GIVEN futures price with None value
#         WHEN listing STIR futures prices
#         THEN the futures with None price is still returned
#         """
#         future_with_none = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="24.04",
#             first_accrual_date=date(2024, 4, 1),
#             last_accrual_date=date(2024, 4, 30),
#             date=self.test_date,
#             price=None,
#             source=StirFuturesSourceChoices.TFX,
#             comment="No price available",
#         )

#         response = self.client.get(self.base_url, {"date": self.test_date.isoformat()})

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         boj_data = next(
#             item
#             for item in data
#             if item["central_bank"] == CentralBankChoices.BOJ.value
#         )
#         assert boj_data["price"] is None


# class TestBulkUpdateStirFuturesViews(TestCase):
#     """Test cases for Bulk Update STIR Futures API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/stir-futures/bulk-update"
#         self.test_date = date(2024, 1, 15)

#         # Create futures to update
#         self.frb_future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=95.0,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#     def test_bulk_update_stir_futures_prices_success(self):
#         """
#         GIVEN valid bulk update request
#         WHEN bulk updating STIR futures prices
#         THEN the prices are successfully updated
#         """
#         updates = [
#             {
#                 "date": self.test_date.isoformat(),
#                 "short_name": StirFuturesNameChoices.FF1M,
#                 "maturity": "24.01",
#                 "price": 95.50,
#                 "logs": "Test update",
#             }
#         ]

#         response = self.client.patch(self.base_url, data=updates, format="json")

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 1
#         assert data[0]["price"] == 95.50

#         # Verify database was updated
#         self.frb_future.refresh_from_db()
#         assert self.frb_future.price == 95.50

#     def test_bulk_update_stir_futures_prices_empty_list(self):
#         """
#         GIVEN empty list of updates
#         WHEN bulk updating STIR futures prices
#         THEN an empty list is returned
#         """
#         response = self.client.patch(self.base_url, data=[], format="json")

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert data == []

#     def test_bulk_update_stir_futures_prices_multiple_updates(self):
#         """
#         GIVEN multiple updates
#         WHEN bulk updating STIR futures prices
#         THEN all prices are updated
#         """
#         # Create another future
#         ecb_future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         updates = [
#             {
#                 "date": self.test_date.isoformat(),
#                 "short_name": StirFuturesNameChoices.FF1M,
#                 "maturity": "24.01",
#                 "price": 95.75,
#                 "logs": "Update 1",
#             },
#             {
#                 "date": self.test_date.isoformat(),
#                 "short_name": StirFuturesNameChoices.ESTR3M,
#                 "maturity": "24.03",
#                 "price": 96.25,
#                 "logs": "Update 2",
#             },
#         ]

#         response = self.client.patch(self.base_url, data=updates, format="json")

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2

#         # Verify both were updated
#         self.frb_future.refresh_from_db()
#         ecb_future.refresh_from_db()
#         assert self.frb_future.price == 95.75
#         assert ecb_future.price == 96.25


# class TestCsvBulkUpdateStirFuturesViews(TestCase):
#     """Test cases for CSV Bulk Update STIR Futures API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/stir-futures/bulk-update-from-csv"
#         self.test_date = date(2024, 1, 15)

#         # Create futures to update
#         self.frb_future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=95.0,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#     def _create_csv_file(self, rows):
#         """Helper to create CSV file from rows."""
#         output = StringIO()
#         writer = csv.DictWriter(
#             output, fieldnames=["date", "short_name", "maturity", "price", "logs"]
#         )
#         writer.writeheader()
#         writer.writerows(rows)
#         output.seek(0)
#         csv_content = output.getvalue()
#         return SimpleUploadedFile(
#             "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
#         )

#     def test_bulk_update_from_csv_success(self):
#         """
#         GIVEN valid CSV file with updates
#         WHEN bulk updating STIR futures prices from CSV
#         THEN the prices are successfully updated
#         """
#         csv_file = self._create_csv_file(
#             [
#                 {
#                     "date": self.test_date.isoformat(),
#                     "short_name": StirFuturesNameChoices.FF1M,
#                     "maturity": "24.01",
#                     "price": "95.50",
#                     "logs": "CSV update",
#                 }
#             ]
#         )

#         response = self.client.post(
#             self.base_url, {"csv_file": csv_file}, format="multipart"
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 1
#         assert data[0]["price"] == 95.50

#         # Verify database was updated
#         self.frb_future.refresh_from_db()
#         assert self.frb_future.price == 95.50

#     def test_bulk_update_from_csv_multiple_rows(self):
#         """
#         GIVEN CSV file with multiple rows
#         WHEN bulk updating STIR futures prices from CSV
#         THEN all prices are updated
#         """
#         # Create another future
#         ecb_future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=96.0,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         csv_file = self._create_csv_file(
#             [
#                 {
#                     "date": self.test_date.isoformat(),
#                     "short_name": StirFuturesNameChoices.FF1M,
#                     "maturity": "24.01",
#                     "price": "95.75",
#                     "logs": "Update 1",
#                 },
#                 {
#                     "date": self.test_date.isoformat(),
#                     "short_name": StirFuturesNameChoices.ESTR3M,
#                     "maturity": "24.03",
#                     "price": "96.25",
#                     "logs": "Update 2",
#                 },
#             ]
#         )

#         response = self.client.post(
#             self.base_url, {"csv_file": csv_file}, format="multipart"
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2

#         # Verify both were updated
#         self.frb_future.refresh_from_db()
#         ecb_future.refresh_from_db()
#         assert self.frb_future.price == 95.75
#         assert ecb_future.price == 96.25

#     def test_bulk_update_from_csv_missing_columns(self):
#         """
#         GIVEN CSV file with missing required columns
#         WHEN bulk updating STIR futures prices from CSV
#         THEN an error is returned
#         """
#         # Create CSV with missing columns
#         output = StringIO()
#         writer = csv.DictWriter(output, fieldnames=["date", "short_name"])
#         writer.writeheader()
#         writer.writerow(
#             {
#                 "date": self.test_date.isoformat(),
#                 "short_name": StirFuturesNameChoices.FF1M,
#             }
#         )
#         output.seek(0)
#         csv_content = output.getvalue()
#         csv_file = SimpleUploadedFile(
#             "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
#         )

#         response = self.client.post(
#             self.base_url, {"csv_file": csv_file}, format="multipart"
#         )

#         assert response.status_code == status.HTTP_400_BAD_REQUEST

#     def test_bulk_update_from_csv_missing_file(self):
#         """
#         GIVEN request without CSV file
#         WHEN bulk updating STIR futures prices from CSV
#         THEN a validation error is returned
#         """
#         response = self.client.post(self.base_url, {}, format="multipart")

#         assert response.status_code == status.HTTP_400_BAD_REQUEST
