"""Tests for central bank meetings services."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta
from django.test import TestCase
from freezegun import freeze_time

from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankMeetingModel,
    CentralBankMeetingStatusChoices,
)
from central_banks_overview.services.central_banks_meetings import (
    _CentralBankMeetingDates,
    get_central_bank_meeting_dates,
    get_central_bank_next_meeting_date,
    has_past_meeting,
    ingest_all_central_bank_meeting_dates,
    ingest_central_bank_meeting_dates,
    list_past_meetings_pending_rates_ingest,
    mark_meeting_status,
)
from central_banks_overview.services.config import (
    BOJ_MPM_URL,
    ECB_MEETING_URL,
    FOMC_MEETING_URL,
)
from central_banks_overview.services.scrapers.boj_meetings import (
    extract_boj_meeting_dates,
)
from central_banks_overview.services.scrapers.ecb_meetings import (
    extract_ecb_meeting_dates,
)
from central_banks_overview.services.scrapers.fomc_meetings import (
    extract_fomc_meeting_dates,
)
from core.testing import MockResponse, parse_query_for_testing, read_file_content


class TestCentralBankMeetingsServices(TestCase):
    """Test cases for central_banks_meetings functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date_1 = datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc)
        self.test_date_2 = datetime(2024, 5, 1, 13, 0, 0, tzinfo=timezone.utc)
        self.test_date_3 = datetime(2024, 6, 12, 13, 0, 0, tzinfo=timezone.utc)

        # Create FRB meetings
        self.frb_meeting_1 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=self.test_date_1,
        )
        self.frb_meeting_2 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=self.test_date_2,
        )

        # Create ECB meetings
        self.ecb_meeting_1 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            date=self.test_date_3,
        )

    @freeze_time("2024-01-01 12:00:00")
    def test_get_central_bank_meeting_dates_all(self):
        """
        GIVEN central bank meetings in the database
        WHEN getting all central bank meeting dates
        THEN upcoming meeting dates are returned grouped by central bank
        """
        result = get_central_bank_meeting_dates()
        assert result == [
            _CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[self.test_date_3],
            ),
            _CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[self.test_date_1, self.test_date_2],
            ),
        ]

    @freeze_time("2024-01-01 12:00:00")
    def test_get_central_bank_meeting_dates_filtered(self):
        """
        GIVEN central bank meetings for multiple banks
        WHEN getting meeting dates for specific central banks
        THEN only meeting dates for those banks are returned
        """
        result = get_central_bank_meeting_dates([CentralBankChoices.FRB])
        assert result == [
            _CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[self.test_date_1, self.test_date_2],
            ),
        ]

    def test_get_central_bank_meeting_dates_empty(self):
        """
        GIVEN no central bank meetings in the database
        WHEN getting all central bank meeting dates
        THEN an empty list is returned
        """
        CentralBankMeetingModel.objects.all().delete()
        result = get_central_bank_meeting_dates()
        assert result == []

    def test_get_central_bank_next_meeting_date_no_meetings(self):
        """
        GIVEN no meetings for a central bank
        WHEN getting next meeting date
        THEN None is returned
        """
        CentralBankMeetingModel.objects.filter(
            central_bank=CentralBankChoices.BOJ
        ).delete()
        result = get_central_bank_next_meeting_date(CentralBankChoices.BOJ)
        assert result is None

    @freeze_time("2026-10-30 16:00:00")
    def test_get_central_bank_next_meeting_date_includes_today_from_t_minus_one(
        self,
    ):
        """
        GIVEN a meeting on the system calendar day (BoJ decision day)
        WHEN getting next meeting (Market Watch as-of = previous business day)
        THEN that same-day meeting is still the next meeting
        """
        CentralBankMeetingModel.objects.all().delete()
        boj_meeting_today = datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=boj_meeting_today,
        )
        result = get_central_bank_next_meeting_date(CentralBankChoices.BOJ)
        assert result == boj_meeting_today

    @freeze_time("2026-10-30 16:00:00")
    def test_has_past_meeting_true_after_scheduled_time(self):
        """
        GIVEN a same-day BoJ meeting whose scheduled UTC time has passed
        WHEN checking whether the bank has a past meeting
        THEN True is returned
        """
        CentralBankMeetingModel.objects.all().delete()
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc),
        )
        assert has_past_meeting(CentralBankChoices.BOJ) is True

    @freeze_time("2026-10-30 05:00:00")
    def test_has_past_meeting_false_before_scheduled_time(self):
        """
        GIVEN a same-day meeting whose scheduled UTC time is still ahead
        WHEN checking whether the bank has a past meeting
        THEN False is returned
        """
        CentralBankMeetingModel.objects.all().delete()
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc),
        )
        assert has_past_meeting(CentralBankChoices.BOJ) is False

    @freeze_time("2026-10-30 16:00:00")
    def test_list_past_meetings_pending_rates_ingest_same_day_after_scheduled_time(
        self,
    ):
        """
        GIVEN a same-day BoJ meeting whose scheduled UTC time has passed
        WHEN listing past meetings pending a rates ingest
        THEN that meeting is returned even though it is still as-of 'next'
        """
        CentralBankMeetingModel.objects.all().delete()
        boj_meeting_today = datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=boj_meeting_today,
        )
        assert get_central_bank_next_meeting_date(CentralBankChoices.BOJ) == (
            boj_meeting_today
        )
        pending_meetings = list_past_meetings_pending_rates_ingest(
            CentralBankChoices.BOJ
        )
        assert [meeting.date for meeting in pending_meetings] == [boj_meeting_today]

    @freeze_time("2026-11-02 10:00:00")
    def test_list_past_meetings_pending_rates_ingest_lookback_past_not_next(
        self,
    ):
        """
        GIVEN a recent past BoJ meeting retained in lookback (no longer as-of next)
        WHEN listing past meetings pending a rates ingest
        THEN that past meeting is returned while next meeting is None
        """
        CentralBankMeetingModel.objects.all().delete()
        boj_meeting_past = datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=boj_meeting_past,
        )
        assert get_central_bank_next_meeting_date(CentralBankChoices.BOJ) is None
        pending_meetings = list_past_meetings_pending_rates_ingest(
            CentralBankChoices.BOJ
        )
        assert [meeting.date for meeting in pending_meetings] == [boj_meeting_past]

    @freeze_time("2026-10-30 05:00:00")
    def test_list_past_meetings_pending_rates_ingest_before_scheduled_time(
        self,
    ):
        """
        GIVEN a same-day meeting whose scheduled UTC time is still ahead
        WHEN listing past meetings pending a rates ingest
        THEN an empty list is returned
        """
        CentralBankMeetingModel.objects.all().delete()
        boj_meeting_today = datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=boj_meeting_today,
        )
        assert list_past_meetings_pending_rates_ingest(CentralBankChoices.BOJ) == []

    @freeze_time("2026-11-02 10:00:00")
    def test_mark_meeting_status_lifecycle(self):
        """
        GIVEN an UPCOMING meeting
        WHEN marking OCCURRED then RATES_INGESTED
        THEN status moves along the allowed lifecycle
        """
        meeting = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc),
        )
        assert meeting.status == CentralBankMeetingStatusChoices.UPCOMING
        mark_meeting_status(meeting, CentralBankMeetingStatusChoices.OCCURRED)
        meeting.refresh_from_db()
        assert meeting.status == CentralBankMeetingStatusChoices.OCCURRED
        mark_meeting_status(meeting, CentralBankMeetingStatusChoices.RATES_INGESTED)
        meeting.refresh_from_db()
        assert meeting.status == CentralBankMeetingStatusChoices.RATES_INGESTED
        assert list_past_meetings_pending_rates_ingest(CentralBankChoices.BOJ) == []

    @freeze_time("2026-11-02 10:00:00")
    def test_mark_meeting_status_rejects_upcoming_to_rates_ingested(self):
        """
        GIVEN an UPCOMING meeting
        WHEN marking RATES_INGESTED directly
        THEN a ValueError is raised and status stays UPCOMING
        """
        meeting = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.BOJ,
            date=datetime(2026, 10, 30, 6, 30, tzinfo=timezone.utc),
        )
        with pytest.raises(ValueError, match="RATES_INGESTED"):
            mark_meeting_status(meeting, CentralBankMeetingStatusChoices.RATES_INGESTED)
        meeting.refresh_from_db()
        assert meeting.status == CentralBankMeetingStatusChoices.UPCOMING

    @freeze_time("2024-01-01 12:00:00")
    def test_get_central_bank_meeting_dates_ordered_by_date(self):
        """
        GIVEN meetings created in non-chronological date order
        WHEN getting meeting dates
        THEN upcoming meetings are returned ordered by date
        """
        # Clear and create meetings in non-chronological order
        CentralBankMeetingModel.objects.all().delete()

        date_3 = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
        date_1 = datetime(2024, 4, 15, 13, 0, 0, tzinfo=timezone.utc)
        date_2 = datetime(2024, 5, 15, 13, 0, 0, tzinfo=timezone.utc)

        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB, date=date_3
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB, date=date_1
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB, date=date_2
        )

        result = get_central_bank_meeting_dates([CentralBankChoices.FRB])
        assert result == [
            _CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[date_1, date_2, date_3],
            ),
        ]

    @freeze_time("2024-01-01 12:00:00")
    def test_get_central_bank_next_meeting_date(self):
        """
        GIVEN central bank meetings in the database
        WHEN getting next meeting date for a central bank
        THEN the earliest upcoming meeting date is returned
        """
        result = get_central_bank_next_meeting_date(CentralBankChoices.FRB)
        assert result == self.test_date_1


class TestCentralBankMeetingsIngestionServices(TestCase):
    """Test cases for ingestion functions in central_banks_meetings."""

    MOCK_FOMC_MEETING_DATES_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/fomc_meeting_dates/success.html"
    )
    MOCK_ECB_MEETING_DATES_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/ecb_meeting_dates/success.html"
    )
    MOCK_BOJ_MEETING_DATES_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/boj_meeting_dates/success.html"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        extract_fomc_meeting_dates.cache_clear()
        extract_ecb_meeting_dates.cache_clear()
        extract_boj_meeting_dates.cache_clear()

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_frb_success(self, mock_get):
        """
        GIVEN FOMC meeting dates are extracted from HTML
        WHEN ingesting central bank meeting dates for FRB
        THEN future meeting dates are created in the database
        """

        def mock_get_side_effect(url, **kwargs):
            """Return success for FOMC meetings and 404 for other banks."""
            if url == FOMC_MEETING_URL:
                return MockResponse(
                    status_code=200, content=self.MOCK_FOMC_MEETING_DATES_SUCCESS
                )
            elif url == ECB_MEETING_URL:
                return MockResponse(status_code=404, content=b"")
            elif url == BOJ_MPM_URL:
                return MockResponse(status_code=404, content=b"")
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        mock_get.assert_any_call(FOMC_MEETING_URL, timeout=10)
        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-01-31 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-03-20 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-05-01 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-06-12 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-07-31 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-09-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-11-07 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-12-18 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-05-07 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-06-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-07-30 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-09-17 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-10-29 18:00:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_ecb_success(self, mock_get):
        """
        GIVEN ECB meeting dates are extracted from HTML
        WHEN ingesting central bank meeting dates for ECB
        THEN future meeting dates are created in the database
        """

        def mock_get_side_effect(url, **kwargs):
            """Return success for ECB meetings and 404 for other banks."""
            if url == ECB_MEETING_URL:
                return MockResponse(
                    status_code=200, content=self.MOCK_ECB_MEETING_DATES_SUCCESS
                )
            elif url == FOMC_MEETING_URL:
                return MockResponse(status_code=404, content=b"")
            elif url == BOJ_MPM_URL:
                return MockResponse(status_code=404, content=b"")
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        mock_get.assert_any_call(ECB_MEETING_URL, timeout=10)
        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2025-12-18 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-02-05 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-03-19 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-04-30 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-06-11 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-07-23 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-09-10 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-10-29 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-12-17 13:15:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_boj_success(self, mock_get):
        """
        GIVEN BoJ meeting dates are extracted from HTML
        WHEN ingesting central bank meeting dates for BoJ
        THEN future meeting dates are created in the database
        """

        def mock_get_side_effect(url, **kwargs):
            """Return success for BOJ meetings and 404 for other banks."""
            if url == BOJ_MPM_URL:
                return MockResponse(
                    status_code=200, content=self.MOCK_BOJ_MEETING_DATES_SUCCESS
                )
            elif url == FOMC_MEETING_URL:
                return MockResponse(status_code=404, content=b"")
            elif url == ECB_MEETING_URL:
                return MockResponse(status_code=404, content=b"")
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        mock_get.assert_any_call(BOJ_MPM_URL, timeout=10)
        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-01-24 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-03-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-05-01 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-06-17 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-07-31 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-09-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-10-30 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-12-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-01-23 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-03-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-04-28 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-06-16 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-07-31 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-09-18 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-10-30 06:30:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_multiple_central_banks(self, mock_get):
        """
        GIVEN meeting dates for multiple central banks are extracted from HTML
        WHEN ingesting central bank meeting dates
        THEN meeting dates for all central banks are created
        """

        def mock_get_side_effect(url, **kwargs):
            """Return success HTML for FOMC, ECB, and BOJ meeting pages."""
            if url == FOMC_MEETING_URL:
                return MockResponse(
                    status_code=200,
                    content=self.MOCK_FOMC_MEETING_DATES_SUCCESS,
                )
            elif url == ECB_MEETING_URL:
                return MockResponse(
                    status_code=200,
                    content=self.MOCK_ECB_MEETING_DATES_SUCCESS,
                )
            elif url == BOJ_MPM_URL:
                return MockResponse(
                    status_code=200,
                    content=self.MOCK_BOJ_MEETING_DATES_SUCCESS,
                )
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["central_bank", "date"]
        )
        assert result == [
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-01-24 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-03-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-05-01 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-06-17 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-07-31 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-09-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-10-30 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2025-12-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-01-23 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-03-19 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-04-28 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-06-16 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-07-31 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-09-18 06:30:00+0000",
            },
            {
                "central_bank": "BOJ",
                "status": "UPCOMING",
                "date": "2026-10-30 06:30:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2025-12-18 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-02-05 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-03-19 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-04-30 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-06-11 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-07-23 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-09-10 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-10-29 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-12-17 13:15:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-01-31 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-03-20 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-05-01 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-06-12 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-07-31 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-09-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-11-07 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-12-18 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-05-07 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-06-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-07-30 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-09-17 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-10-29 18:00:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_updates_existing(self, mock_get):
        """
        GIVEN existing meeting date in the database
        WHEN ingesting the same meeting date from HTML
        THEN the existing meeting is updated
        """
        existing_date = datetime(2024, 1, 31, 19, 0, 0, tzinfo=timezone.utc)
        existing_meeting = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=existing_date,
        )

        def mock_get_side_effect(url, **kwargs):
            """Return success for FOMC meetings and 404 for other banks."""
            if url == FOMC_MEETING_URL:
                return MockResponse(
                    status_code=200,
                    content=self.MOCK_FOMC_MEETING_DATES_SUCCESS,
                )
            elif url == ECB_MEETING_URL:
                return MockResponse(status_code=404, content=b"")
            elif url == BOJ_MPM_URL:
                return MockResponse(status_code=404, content=b"")
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        existing_meeting.refresh_from_db()
        assert existing_meeting.status == CentralBankMeetingStatusChoices.UPCOMING
        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        # Should have 15 meetings total, with existing meeting kept as UPCOMING
        assert result == [
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-01-31 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-03-20 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-05-01 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-06-12 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-07-31 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-09-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-11-07 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2024-12-18 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-05-07 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-06-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-07-30 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-09-17 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-10-29 18:00:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_empty_result(self, mock_get):
        """
        GIVEN no meeting dates are extracted (empty HTML or None)
        WHEN ingesting central bank meeting dates
        THEN no meeting dates are created
        """
        CentralBankMeetingModel.objects.all().delete()

        def mock_get_side_effect(url, **kwargs):
            """Return 404 for every central bank meeting URL."""
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        result = parse_query_for_testing(CentralBankMeetingModel.objects.all())
        assert result == []

    @patch("core.services.requests.get")
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_filters_past_dates(self, mock_get):
        """
        GIVEN meeting dates include past dates in HTML
        WHEN ingesting central bank meeting dates
        THEN only future dates are ingested
        """
        CentralBankMeetingModel.objects.all().delete()

        def mock_get_side_effect(url, **kwargs):
            """Return success for FOMC meetings and 404 for other banks."""
            if url == FOMC_MEETING_URL:
                return MockResponse(
                    status_code=200,
                    content=self.MOCK_FOMC_MEETING_DATES_SUCCESS,
                )
            elif url == ECB_MEETING_URL:
                return MockResponse(status_code=404, content=b"")
            elif url == BOJ_MPM_URL:
                return MockResponse(status_code=404, content=b"")
            return MockResponse(status_code=404, content=b"")

        mock_get.side_effect = mock_get_side_effect

        ingest_all_central_bank_meeting_dates()

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-05-07 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-06-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-07-30 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-09-17 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-10-29 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-12-10 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-01-28 19:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-03-18 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-04-29 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-06-17 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-07-29 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-09-16 18:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2026-10-28 18:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_deletes_old_meetings(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN existing meetings in database and extracted meeting dates
        WHEN ingesting central bank meeting dates for FRB
        THEN old meetings are deleted and new meetings are created
        and the order of the meetings is updated.
        """
        # Outside lookback — should be deleted
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2024, 10, 1, 13, 0, 0, tzinfo=timezone.utc),
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
        )
        # Create a meeting that should be kept (it's in the new list)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),
        )

        new_meeting_dates = [
            datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 5, 7, 13, 0, 0, tzinfo=timezone.utc),
        ]
        mock_extract_fomc.return_value = new_meeting_dates
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.FRB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-05-07 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_only_deletes_same_central_bank(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN meetings for multiple central banks
        WHEN ingesting meeting dates for one central bank
        THEN only meetings for that central bank are deleted
        """
        # Create FRB meeting that should be deleted
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 2, 1, 13, 0, 0, tzinfo=timezone.utc),
        )

        # Create ECB meeting that should NOT be deleted
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            date=datetime(2025, 2, 1, 13, 15, 0, tzinfo=timezone.utc),
        )

        # New FRB meeting dates
        new_frb_dates = [
            datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),
        ]
        mock_extract_fomc.return_value = new_frb_dates
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.FRB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["central_bank", "date"]
        )
        assert result == [
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2025-02-01 13:15:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_respects_nb_meetings_limit(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN more meeting dates than NB_MEETINGS_TO_INGEST
        WHEN ingesting central bank meeting dates for FRB
        THEN only meetings within the limit are kept, others are deleted
        """
        # Create existing meetings beyond the limit
        for i in range(20):
            CentralBankMeetingModel.objects.create(
                central_bank=CentralBankChoices.FRB,
                date=datetime(2025, 2, i + 1, 13, 0, 0, tzinfo=timezone.utc),
            )

        # New meeting dates list with more than NB_MEETINGS_TO_INGEST (15)
        # Generate 20 valid dates starting from January 29, 2025
        start_date = datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc)
        new_meeting_dates = [start_date + relativedelta(days=i) for i in range(20)]
        mock_extract_fomc.return_value = new_meeting_dates
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.FRB)

        # Verify only NB_MEETINGS_TO_INGEST (15) meetings exist
        all_meetings = CentralBankMeetingModel.objects.filter(central_bank="FRB")
        assert all_meetings.count() == 15

        # Verify the first 15 meeting dates from new_meeting_dates are in DB
        meeting_dates_in_db = {m.date for m in all_meetings}
        expected_dates = {new_meeting_dates[i] for i in range(15)}
        assert meeting_dates_in_db == expected_dates

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_filters_past_dates_before_deletion(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN meeting dates including past dates
        WHEN ingesting central bank meeting dates for FRB
        THEN scraped past dates are not ingested as upcoming meetings
        """
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 2, 1, 13, 0, 0, tzinfo=timezone.utc),
        )

        meeting_dates_with_past = [
            datetime(2024, 12, 15, 13, 0, 0, tzinfo=timezone.utc),  # Past
            datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),  # Future
            datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),  # Future
        ]
        mock_extract_fomc.return_value = meeting_dates_with_past
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.FRB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-20 12:00:00")
    def test_ingest_retains_existing_recent_past_meeting_missing_from_scrape(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN a recent past meeting already in the DB that the scrape no longer lists
        WHEN ingesting meeting dates
        THEN that recent past meeting is retained for day-event display
        """
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            date=datetime(2025, 1, 15, 13, 15, 0, tzinfo=timezone.utc),
        )
        mock_extract_fomc.return_value = []
        mock_extract_ecb.return_value = [
            datetime(2025, 3, 19, 13, 15, 0, tzinfo=timezone.utc),
        ]
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.ECB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.filter(central_bank="ECB"),
            sort_keys=["date"],
        )
        assert result == [
            {
                "central_bank": "ECB",
                "status": "OCCURRED",
                "date": "2025-01-15 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2025-03-19 13:15:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2026-10-30 16:00:00")
    def test_ingest_retains_same_day_meeting_missing_from_scrape(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN today's ECB meeting still in the DB after the scrape dropped it
        WHEN ingesting meeting dates (as_of = previous business day)
        THEN that same-day afternoon meeting is retained for economic releases
        """
        same_day_meeting = datetime(2026, 10, 30, 12, 15, 0, tzinfo=timezone.utc)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            date=same_day_meeting,
        )
        mock_extract_fomc.return_value = []
        mock_extract_ecb.return_value = [
            datetime(2026, 12, 17, 13, 15, 0, tzinfo=timezone.utc),
        ]
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.ECB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.filter(central_bank="ECB"),
            sort_keys=["date"],
        )
        assert result == [
            {
                "central_bank": "ECB",
                "status": "OCCURRED",
                "date": "2026-10-30 12:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "status": "UPCOMING",
                "date": "2026-12-17 13:15:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.central_banks_meetings.extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-20 12:00:00")
    def test_ingest_preserves_rates_ingested_and_marks_past_occurred(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN a RATES_INGESTED past meeting and an UPCOMING past meeting in lookback
        WHEN ingesting meeting dates
        THEN RATES_INGESTED is kept and the other past meeting becomes OCCURRED
        """
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 1, 15, 13, 0, 0, tzinfo=timezone.utc),
            status=CentralBankMeetingStatusChoices.RATES_INGESTED,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 1, 18, 13, 0, 0, tzinfo=timezone.utc),
            status=CentralBankMeetingStatusChoices.UPCOMING,
        )
        mock_extract_fomc.return_value = [
            datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),
        ]
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.FRB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["date"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "status": "RATES_INGESTED",
                "date": "2025-01-15 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "OCCURRED",
                "date": "2025-01-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "status": "UPCOMING",
                "date": "2025-03-19 13:00:00+0000",
            },
        ]
