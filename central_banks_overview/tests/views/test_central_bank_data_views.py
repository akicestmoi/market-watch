# from datetime import date

# from django.test import TestCase
# from rest_framework import status
# from rest_framework.test import APIClient

# from central_banks_overview.models import CentralBankChoices, CentralBankDataModel


# class TestCentralBankDataViews(TestCase):
#     """Test cases for Central Bank Data API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/data"
#         self.test_date = date(2024, 1, 15)
#         self.test_date_2 = date(2024, 2, 15)

#         # Create central bank data for FRB
#         self.frb_data_1 = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date,
#             value=5.25,
#             comment="",
#         )
#         self.frb_data_2 = CentralBankDataModel.objects.create(
#             cb_data_id=1,
#             central_bank=CentralBankChoices.FRB,
#             short_name="FRB_FEDFUNDS",
#             full_name="FRB Target Fed Funds Rate",
#             date=self.test_date_2,
#             value=5.50,
#             comment="",
#         )

#         # Create central bank data for ECB
#         self.ecb_data_1 = CentralBankDataModel.objects.create(
#             cb_data_id=2,
#             central_bank=CentralBankChoices.ECB,
#             short_name="ECB_Deposit",
#             full_name="ECB Deposit Facility Rate",
#             date=self.test_date,
#             value=4.0,
#             comment="",
#         )

#     def test_list_central_bank_data_with_date(self):
#         """
#         GIVEN central bank data for a specific date
#         WHEN listing central bank data with date parameter
#         THEN the correct data for that date is returned
#         """
#         response = self.client.get(self.base_url, {"date": self.test_date.isoformat()})

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2
#         short_names = {item["short_name"] for item in data}
#         assert "FRB_FEDFUNDS" in short_names
#         assert "ECB_Deposit" in short_names

#     def test_list_central_bank_data_with_central_banks_filter(self):
#         """
#         GIVEN central bank data for multiple central banks
#         WHEN listing central bank data with central_banks filter
#         THEN only data for specified central banks is returned
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

#     def test_list_central_bank_data_with_multiple_central_banks_filter(self):
#         """
#         GIVEN central bank data for multiple central banks
#         WHEN listing central bank data with comma-separated central_banks
#         THEN data for all specified central banks is returned
#         """
#         response = self.client.get(
#             self.base_url,
#             {
#                 "date": self.test_date.isoformat(),
#                 "central_banks": f"{CentralBankChoices.FRB.value},{CentralBankChoices.ECB.value}",
#             },
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2
#         central_banks = {item["central_bank"] for item in data}
#         assert CentralBankChoices.FRB.value in central_banks
#         assert CentralBankChoices.ECB.value in central_banks

#     def test_list_central_bank_data_with_last_value(self):
#         """
#         GIVEN central bank data for multiple dates
#         WHEN listing central bank data with last_value=True
#         THEN only the latest data for each short_name is returned
#         """
#         response = self.client.get(self.base_url, {"last_value": True})

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2

#         # Find FRB data
#         frb_data = next(
#             item
#             for item in data
#             if item["central_bank"] == CentralBankChoices.FRB.value
#         )
#         assert frb_data["date"] == self.test_date_2.isoformat()
#         assert frb_data["value"] == 5.50

#     def test_list_central_bank_data_no_filters(self):
#         """
#         GIVEN central bank data in the database
#         WHEN listing central bank data without filters
#         THEN all data is returned
#         """
#         response = self.client.get(self.base_url)

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 3

#     def test_list_central_bank_data_empty(self):
#         """
#         GIVEN no central bank data for a date
#         WHEN listing central bank data for that date
#         THEN an empty list is returned
#         """
#         response = self.client.get(
#             self.base_url, {"date": date(2025, 1, 1).isoformat()}
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert data == []
