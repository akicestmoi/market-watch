from datetime import datetime, timezone
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

from central_banks_overview.models import CentralBankChoices, CentralBankMeetingModel
from central_banks_overview.services.cb_meetings_services import (
    BOJ_MPM_URL,
    ECB_MEETING_URL,
    FOMC_MEETING_URL,
    CentralBankMeetingDates,
    _extract_boj_meeting_dates,
    _extract_ecb_meeting_dates,
    _extract_fomc_meeting_dates,
    get_central_bank_meeting_dates,
    get_central_bank_next_meeting_date,
    ingest_all_central_bank_meeting_dates,
    ingest_central_bank_meeting_dates,
)
from core.tests import MockResponse, parse_query_for_testing, read_file_content


class TestCentralBankMeetingsServices(TestCase):
    """Test cases for cb_meetings_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date_1 = datetime(2024, 3, 20, 13, 0, 0, tzinfo=timezone.utc)
        self.test_date_2 = datetime(2024, 5, 1, 13, 0, 0, tzinfo=timezone.utc)
        self.test_date_3 = datetime(2024, 6, 12, 13, 0, 0, tzinfo=timezone.utc)

        # Create FRB meetings
        self.frb_meeting_1 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=1,
            date=self.test_date_1,
        )
        self.frb_meeting_2 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            order=2,
            date=self.test_date_2,
        )

        # Create ECB meetings
        self.ecb_meeting_1 = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            order=1,
            date=self.test_date_3,
        )

    def test_get_central_bank_meeting_dates_all(self):
        """
        GIVEN central bank meetings in the database
        WHEN getting all central bank meeting dates
        THEN all meeting dates are returned grouped by central bank
        """
        result = get_central_bank_meeting_dates()
        assert result == [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.ECB,
                meeting_dates=[self.test_date_3],
            ),
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[self.test_date_1, self.test_date_2],
            ),
        ]

    def test_get_central_bank_meeting_dates_filtered(self):
        """
        GIVEN central bank meetings for multiple banks
        WHEN getting meeting dates for specific central banks
        THEN only meeting dates for those banks are returned
        """
        result = get_central_bank_meeting_dates([CentralBankChoices.FRB])
        assert result == [
            CentralBankMeetingDates(
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
        THEN an IndexError is raised
        """
        CentralBankMeetingModel.objects.filter(
            central_bank=CentralBankChoices.BOJ
        ).delete()
        result = get_central_bank_next_meeting_date(CentralBankChoices.BOJ)
        assert result is None

    def test_get_central_bank_meeting_dates_ordered_by_date(self):
        """
        GIVEN meetings with different orders
        WHEN getting meeting dates
        THEN meetings are returned ordered by date
        """
        # Clear and create meetings in non-chronological order
        CentralBankMeetingModel.objects.all().delete()

        date_3 = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
        date_1 = datetime(2024, 4, 15, 13, 0, 0, tzinfo=timezone.utc)
        date_2 = datetime(2024, 5, 15, 13, 0, 0, tzinfo=timezone.utc)

        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB, order=3, date=date_3
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB, order=1, date=date_1
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB, order=2, date=date_2
        )

        result = get_central_bank_meeting_dates([CentralBankChoices.FRB])
        assert result == [
            CentralBankMeetingDates(
                central_bank=CentralBankChoices.FRB,
                meeting_dates=[date_1, date_2, date_3],
            ),
        ]

    def test_get_central_bank_next_meeting_date(self):
        """
        GIVEN central bank meetings in the database
        WHEN getting next meeting date for a central bank
        THEN the earliest meeting date is returned
        """
        result = get_central_bank_next_meeting_date(CentralBankChoices.FRB)
        assert result == self.test_date_1


class TestCentralBankMeetingsIngestionServices(TestCase):
    """Test cases for ingestion functions in cb_meetings_services."""

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
        _extract_fomc_meeting_dates.cache_clear()
        _extract_ecb_meeting_dates.cache_clear()
        _extract_boj_meeting_dates.cache_clear()

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_frb_success(self, mock_get):
        """
        GIVEN FOMC meeting dates are extracted from HTML
        WHEN ingesting central bank meeting dates for FRB
        THEN future meeting dates are created in the database with correct order
        """

        def mock_get_side_effect(url, **kwargs):
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
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2024-01-31 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2024-03-20 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 3,
                "date": "2024-05-01 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 4,
                "date": "2024-06-12 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 5,
                "date": "2024-07-31 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 6,
                "date": "2024-09-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 7,
                "date": "2024-11-07 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 8,
                "date": "2024-12-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 9,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 10,
                "date": "2025-03-19 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 11,
                "date": "2025-05-07 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 12,
                "date": "2025-06-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 13,
                "date": "2025-07-30 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 14,
                "date": "2025-09-17 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 15,
                "date": "2025-10-29 13:00:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_ecb_success(self, mock_get):
        """
        GIVEN ECB meeting dates are extracted from HTML
        WHEN ingesting central bank meeting dates for ECB
        THEN future meeting dates are created in the database with correct order
        """

        def mock_get_side_effect(url, **kwargs):
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
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "ECB",
                "order": 1,
                "date": "2025-12-18 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 2,
                "date": "2026-02-05 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 3,
                "date": "2026-03-19 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 4,
                "date": "2026-04-30 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 5,
                "date": "2026-06-11 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 6,
                "date": "2026-07-23 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 7,
                "date": "2026-09-10 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 8,
                "date": "2026-10-29 13:15:00+0000",
            },
            {
                "central_bank": "ECB",
                "order": 9,
                "date": "2026-12-17 13:15:00+0000",
            },
        ]

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_boj_success(self, mock_get):
        """
        GIVEN BoJ meeting dates are extracted from HTML
        WHEN ingesting central bank meeting dates for BoJ
        THEN future meeting dates are created in the database with correct order
        """

        def mock_get_side_effect(url, **kwargs):
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
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "BOJ",
                "order": 1,
                "date": "2025-01-24 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 2,
                "date": "2025-03-19 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 3,
                "date": "2025-05-01 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 4,
                "date": "2025-06-17 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 5,
                "date": "2025-07-31 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 6,
                "date": "2025-09-19 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 7,
                "date": "2025-10-30 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 8,
                "date": "2025-12-19 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 9,
                "date": "2026-01-23 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 10,
                "date": "2026-03-19 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 11,
                "date": "2026-04-28 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 12,
                "date": "2026-06-16 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 13,
                "date": "2026-07-31 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 14,
                "date": "2026-09-18 04:00:00+0000",
            },
            {
                "central_bank": "BOJ",
                "order": 15,
                "date": "2026-10-30 04:00:00+0000",
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
            CentralBankMeetingModel.objects.all(), sort_keys=["central_bank", "order"]
        )
        # Check that we have meetings for all three banks
        boj_meetings = [m for m in result if m["central_bank"] == "BOJ"]
        ecb_meetings = [m for m in result if m["central_bank"] == "ECB"]
        frb_meetings = [m for m in result if m["central_bank"] == "FRB"]
        assert len(boj_meetings) > 0
        assert len(ecb_meetings) > 0
        assert len(frb_meetings) > 0
        assert boj_meetings[0]["order"] == 1
        assert ecb_meetings[0]["order"] == 1
        assert frb_meetings[0]["order"] == 1

    @patch("core.services.requests.get")
    @freeze_time("2024-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_updates_existing(self, mock_get):
        """
        GIVEN existing meeting date in the database
        WHEN ingesting the same meeting date from HTML
        THEN the existing record is updated (order may change)
        """
        existing_date = datetime(2024, 1, 31, 13, 0, 0, tzinfo=timezone.utc)
        existing_meeting = CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=existing_date,
            order=5,  # Old order
        )

        def mock_get_side_effect(url, **kwargs):
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
        assert existing_meeting.order == 1
        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        # Should have 15 meetings total, with existing meeting updated to order 1
        assert result == [
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2024-01-31 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2024-03-20 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 3,
                "date": "2024-05-01 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 4,
                "date": "2024-06-12 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 5,
                "date": "2024-07-31 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 6,
                "date": "2024-09-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 7,
                "date": "2024-11-07 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 8,
                "date": "2024-12-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 9,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 10,
                "date": "2025-03-19 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 11,
                "date": "2025-05-07 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 12,
                "date": "2025-06-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 13,
                "date": "2025-07-30 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 14,
                "date": "2025-09-17 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 15,
                "date": "2025-10-29 13:00:00+0000",
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
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2025-03-19 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 3,
                "date": "2025-05-07 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 4,
                "date": "2025-06-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 5,
                "date": "2025-07-30 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 6,
                "date": "2025-09-17 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 7,
                "date": "2025-10-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 8,
                "date": "2025-12-10 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 9,
                "date": "2026-01-28 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 10,
                "date": "2026-03-18 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 11,
                "date": "2026-04-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 12,
                "date": "2026-06-17 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 13,
                "date": "2026-07-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 14,
                "date": "2026-09-16 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 15,
                "date": "2026-10-28 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
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
        # Create existing meetings that should be deleted
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2024, 12, 10, 13, 0, 0, tzinfo=timezone.utc),
            order=1,
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
            order=2,
        )
        # Create a meeting that should be kept (it's in the new list)
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),
            order=3,
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
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2025-03-19 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 3,
                "date": "2025-05-07 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
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
            order=1,
        )

        # Create ECB meeting that should NOT be deleted
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.ECB,
            date=datetime(2025, 2, 1, 13, 15, 0, tzinfo=timezone.utc),
            order=1,
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
            CentralBankMeetingModel.objects.all(), sort_keys=["central_bank", "order"]
        )
        assert result == [
            {
                "central_bank": "ECB",
                "order": 1,
                "date": "2025-02-01 13:15:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2025-03-19 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
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
                order=i + 1,
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
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_filters_past_dates_before_deletion(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN meeting dates including past dates
        WHEN ingesting central bank meeting dates for FRB
        THEN past dates are filtered out and old meetings are deleted correctly
        """
        # Create existing future meeting
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 2, 1, 13, 0, 0, tzinfo=timezone.utc),
            order=1,
        )

        # Meeting dates list includes past dates (should be filtered out)
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
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2025-03-19 13:00:00+0000",
            },
        ]

    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_fomc_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_ecb_meeting_dates"
    )
    @patch(
        "central_banks_overview.services.cb_meetings_services._extract_boj_meeting_dates"
    )
    @freeze_time("2025-01-01 12:00:00")
    def test_ingest_central_bank_meeting_dates_updates_order_existing_meetings(
        self, mock_extract_boj, mock_extract_ecb, mock_extract_fomc
    ):
        """
        GIVEN existing meetings with incorrect order
        WHEN ingesting central bank meeting dates for FRB
        THEN existing meetings are updated with correct order using bulk_update
        """
        # Create existing meetings with wrong order
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),
            order=99,  # Wrong order
        )
        CentralBankMeetingModel.objects.create(
            central_bank=CentralBankChoices.FRB,
            date=datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
            order=88,  # Wrong order
        )

        # New meeting dates in specific order
        new_meeting_dates = [
            datetime(2025, 1, 29, 13, 0, 0, tzinfo=timezone.utc),  # Should be order 1
            datetime(2025, 3, 19, 13, 0, 0, tzinfo=timezone.utc),  # Should be order 2
        ]
        mock_extract_fomc.return_value = new_meeting_dates
        mock_extract_ecb.return_value = []
        mock_extract_boj.return_value = []

        ingest_central_bank_meeting_dates(CentralBankChoices.FRB)

        result = parse_query_for_testing(
            CentralBankMeetingModel.objects.all(), sort_keys=["order"]
        )
        assert result == [
            {
                "central_bank": "FRB",
                "order": 1,
                "date": "2025-01-29 13:00:00+0000",
            },
            {
                "central_bank": "FRB",
                "order": 2,
                "date": "2025-03-19 13:00:00+0000",
            },
        ]
