# from datetime import datetime, timezone

# from django.test import TestCase
# from rest_framework import status
# from rest_framework.test import APIClient

# from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel


# class TestCentralBankMeetingsViews(TestCase):
#     """Test cases for Central Bank Meetings API Views."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.client = APIClient()
#         self.base_url = "/central-banks/meeting-dates"
#         self.test_date_1 = datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc)
#         self.test_date_2 = datetime(2024, 5, 1, 13, 0, 0, tzinfo=timezone.utc)
#         self.test_date_3 = datetime(2024, 6, 12, 13, 0, 0, tzinfo=timezone.utc)

#         # Create FRB meetings
#         self.frb_meeting_1 = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             order=1,
#             date=self.test_date_1,
#         )
#         self.frb_meeting_2 = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             order=2,
#             date=self.test_date_2,
#         )

#         # Create ECB meetings
#         self.ecb_meeting_1 = CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             order=1,
#             date=self.test_date_3,
#         )

#     def test_get_central_bank_meeting_dates_all(self):
#         """
#         GIVEN central bank meetings in the database
#         WHEN getting all central bank meeting dates
#         THEN all meeting dates are returned grouped by central bank
#         """
#         response = self.client.get(self.base_url)

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2

#         # Find FRB and ECB in results
#         frb_result = next(
#             item
#             for item in data
#             if item["central_bank"] == CentralBankChoices.FRB.value
#         )
#         ecb_result = next(
#             item
#             for item in data
#             if item["central_bank"] == CentralBankChoices.ECB.value
#         )

#         assert len(frb_result["meeting_dates"]) == 2
#         assert len(ecb_result["meeting_dates"]) == 1

#     def test_get_central_bank_meeting_dates_filtered(self):
#         """
#         GIVEN central bank meetings for multiple banks
#         WHEN getting meeting dates for specific central banks
#         THEN only meeting dates for those banks are returned
#         """
#         response = self.client.get(
#             self.base_url, {"central_banks": CentralBankChoices.FRB.value}
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 1
#         assert data[0]["central_bank"] == CentralBankChoices.FRB.value
#         assert len(data[0]["meeting_dates"]) == 2

#     def test_get_central_bank_meeting_dates_multiple_central_banks(self):
#         """
#         GIVEN central bank meetings for multiple banks
#         WHEN getting meeting dates with comma-separated central_banks
#         THEN meeting dates for all specified banks are returned
#         """
#         response = self.client.get(
#             self.base_url,
#             {
#                 "central_banks": f"{CentralBankChoices.FRB.value},{CentralBankChoices.ECB.value}"
#             },
#         )

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert len(data) == 2
#         central_banks = {item["central_bank"] for item in data}
#         assert CentralBankChoices.FRB.value in central_banks
#         assert CentralBankChoices.ECB.value in central_banks

#     def test_get_central_bank_meeting_dates_empty(self):
#         """
#         GIVEN no central bank meetings in the database
#         WHEN getting all central bank meeting dates
#         THEN an empty list is returned
#         """
#         CentralBankMeetingModel.objects.all().delete()

#         response = self.client.get(self.base_url)

#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()
#         assert data == []
