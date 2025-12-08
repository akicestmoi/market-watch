# from datetime import datetime, timezone

# from django.test import TestCase
# from freezegun import freeze_time  # type: ignore[reportMissingImports]

# from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel
# from central_banks_overview.services.cb_meetings_services import (
#     get_central_bank_meeting_dates,
#     get_central_bank_next_meeting_date,
#     ingest_specific_central_bank_meeting_dates,
# )


# class TestCentralBankMeetingsServices(TestCase):
#     """Test cases for cb_meetings_services functions."""

#     def setUp(self):
#         """Set up test fixtures."""
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
#         result = get_central_bank_meeting_dates()
#         assert len(result) == 2

#         # Find FRB and ECB in results
#         frb_result = next(
#             r for r in result if r["central_bank"] == CentralBankChoices.FRB
#         )
#         ecb_result = next(
#             r for r in result if r["central_bank"] == CentralBankChoices.ECB
#         )

#         assert len(frb_result["meeting_dates"]) == 2
#         assert self.test_date_1 in frb_result["meeting_dates"]
#         assert self.test_date_2 in frb_result["meeting_dates"]

#         assert len(ecb_result["meeting_dates"]) == 1
#         assert self.test_date_3 in ecb_result["meeting_dates"]

#     def test_get_central_bank_meeting_dates_filtered(self):
#         """
#         GIVEN central bank meetings for multiple banks
#         WHEN getting meeting dates for specific central banks
#         THEN only meeting dates for those banks are returned
#         """
#         result = get_central_bank_meeting_dates([CentralBankChoices.FRB])
#         assert len(result) == 1
#         assert result[0]["central_bank"] == CentralBankChoices.FRB
#         assert len(result[0]["meeting_dates"]) == 2

#     def test_get_central_bank_next_meeting_date(self):
#         """
#         GIVEN central bank meetings in the database
#         WHEN getting next meeting date for a central bank
#         THEN the earliest meeting date is returned
#         """
#         result = get_central_bank_next_meeting_date(CentralBankChoices.FRB)
#         assert result == self.test_date_1

#     @freeze_time("2024-01-01")
#     def test_ingest_specific_central_bank_meeting_dates(self):
#         """
#         GIVEN a list of meeting dates in the future
#         WHEN ingesting specific central bank meeting dates
#         THEN the meetings are created in the database with correct order
#         """
#         new_date_1 = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
#         new_date_2 = datetime(2024, 7, 15, 13, 0, 0, tzinfo=timezone.utc)
#         new_date_3 = datetime(2024, 8, 15, 13, 0, 0, tzinfo=timezone.utc)

#         meeting_dates = [new_date_1, new_date_2, new_date_3]
#         ingest_specific_central_bank_meeting_dates(
#             CentralBankChoices.BOJ, meeting_dates
#         )

#         boj_meetings = CentralBankMeetingModel.objects.filter(
#             central_bank=CentralBankChoices.BOJ
#         ).order_by("order")

#         assert boj_meetings.count() == 3
#         assert boj_meetings[0].date == new_date_1
#         assert boj_meetings[0].order == 1
#         assert boj_meetings[1].date == new_date_2
#         assert boj_meetings[1].order == 2
#         assert boj_meetings[2].date == new_date_3
#         assert boj_meetings[2].order == 3

#     def test_get_central_bank_meeting_dates_empty(self):
#         """
#         GIVEN no central bank meetings in the database
#         WHEN getting all central bank meeting dates
#         THEN an empty list is returned
#         """
#         CentralBankMeetingModel.objects.all().delete()

#         result = get_central_bank_meeting_dates()
#         assert result == []

#     def test_get_central_bank_meeting_dates_single_bank(self):
#         """
#         GIVEN meetings for only one central bank
#         WHEN getting all meeting dates
#         THEN only meetings for that bank are returned
#         """
#         # Clear existing meetings
#         CentralBankMeetingModel.objects.all().delete()

#         # Create only ECB meetings
#         CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             order=1,
#             date=self.test_date_3,
#         )

#         result = get_central_bank_meeting_dates()
#         assert len(result) == 1
#         assert result[0]["central_bank"] == CentralBankChoices.ECB
#         assert len(result[0]["meeting_dates"]) == 1

#     def test_get_central_bank_next_meeting_date_no_meetings_error(self):
#         """
#         GIVEN no meetings for a central bank
#         WHEN getting next meeting date
#         THEN an IndexError is raised
#         """
#         CentralBankMeetingModel.objects.filter(
#             central_bank=CentralBankChoices.BOJ
#         ).delete()

#         try:
#             get_central_bank_next_meeting_date(CentralBankChoices.BOJ)
#             assert False, "Expected IndexError"
#         except (IndexError, KeyError):
#             # The function accesses [0] which will raise IndexError if empty
#             pass

#     @freeze_time("2024-01-01")
#     def test_ingest_specific_central_bank_meeting_dates_filters_past_dates(self):
#         """
#         GIVEN meeting dates including past dates
#         WHEN ingesting specific central bank meeting dates
#         THEN only future dates are ingested
#         """
#         past_date = datetime(2023, 12, 15, 13, 0, 0, tzinfo=timezone.utc)
#         future_date_1 = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
#         future_date_2 = datetime(2024, 7, 15, 13, 0, 0, tzinfo=timezone.utc)

#         meeting_dates = [past_date, future_date_1, future_date_2]
#         ingest_specific_central_bank_meeting_dates(
#             CentralBankChoices.BOJ, meeting_dates
#         )

#         boj_meetings = CentralBankMeetingModel.objects.filter(
#             central_bank=CentralBankChoices.BOJ
#         ).order_by("order")

#         assert boj_meetings.count() == 2
#         assert past_date not in [m.date for m in boj_meetings]
#         assert future_date_1 in [m.date for m in boj_meetings]
#         assert future_date_2 in [m.date for m in boj_meetings]

#     @freeze_time("2024-01-01")
#     def test_ingest_specific_central_bank_meeting_dates_limits_to_nb_meetings(self):
#         """
#         GIVEN more than NB_MEETINGS_TO_INGEST meeting dates
#         WHEN ingesting specific central bank meeting dates
#         THEN only the first NB_MEETINGS_TO_INGEST meetings are ingested
#         """
#         # Create 20 meeting dates (more than NB_MEETINGS_TO_INGEST which is 15)
#         # Use dates from 2024-01-15 to 2024-12-15 (12 months) and continue into 2025
#         meeting_dates = []
#         for i in range(20):
#             year = 2024 + (i // 12)
#             month = (i % 12) + 1
#             meeting_dates.append(
#                 datetime(year, month, 15, 13, 0, 0, tzinfo=timezone.utc)
#             )

#         ingest_specific_central_bank_meeting_dates(
#             CentralBankChoices.BOJ, meeting_dates
#         )

#         boj_meetings = CentralBankMeetingModel.objects.filter(
#             central_bank=CentralBankChoices.BOJ
#         ).order_by("order")

#         assert boj_meetings.count() == 15  # NB_MEETINGS_TO_INGEST

#     def test_get_central_bank_meeting_dates_ordered_by_date(self):
#         """
#         GIVEN meetings with different orders
#         WHEN getting meeting dates
#         THEN meetings are returned ordered by date
#         """
#         # Clear and create meetings in non-chronological order
#         CentralBankMeetingModel.objects.all().delete()

#         date_3 = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
#         date_1 = datetime(2024, 4, 15, 13, 0, 0, tzinfo=timezone.utc)
#         date_2 = datetime(2024, 5, 15, 13, 0, 0, tzinfo=timezone.utc)

#         CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB, order=3, date=date_3
#         )
#         CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB, order=1, date=date_1
#         )
#         CentralBankMeetingModel.objects.create(
#             central_bank=CentralBankChoices.FRB, order=2, date=date_2
#         )

#         result = get_central_bank_meeting_dates([CentralBankChoices.FRB])
#         assert len(result) == 1
#         meeting_dates = result[0]["meeting_dates"]
#         assert meeting_dates == [date_1, date_2, date_3]  # Should be ordered by date
