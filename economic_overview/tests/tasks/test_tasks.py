import json
from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

import economic_overview.tasks as tasks
from core.tests import MockResponse, parse_query_for_testing, read_file_content
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from economic_overview.services.data_ingestion_services import _get_data_from_insee
from economic_overview.services.publication_services import (
    _get_insee_publication_schedule,
    _get_publication_dates_from_insee,
)


class TestScheduledEconomicDataAndScheduleUpdate(TestCase):
    """Test cases for scheduled_economic_data_and_schedule_update task."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Test Indicator",
            name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        mock_insee_zip = read_file_content(
            "economic_overview/tests/mock_web_data/insee/data/success.zip"
        )
        self.mock_insee_response = MockResponse(
            status_code=200, content=mock_insee_zip, text=""
        )
        publication_data = {
            "documents": [
                {
                    "famille": {
                        "facetteConjoncture": {
                            "libelleEn": "test_indicator",
                        }
                    },
                    "embargo": "2025-12-15T10:00:00Z",
                },
                {
                    "famille": {
                        "facetteConjoncture": {
                            "libelleEn": "test_indicator",
                        }
                    },
                    "embargo": "2026-01-15T10:00:00Z",
                },
            ]
        }
        self.mock_publication_response = MockResponse(
            status_code=200,
            content=json.dumps(publication_data).encode("utf-8"),
            json_data=publication_data,
        )

    def tearDown(self):
        """Tear down test fixtures."""
        # Clear all caches to prevent state leakage between tests
        _get_data_from_insee.cache_clear()
        _get_insee_publication_schedule.cache_clear()
        _get_publication_dates_from_insee.cache_clear()

    @freeze_time("2025-12-15")
    @patch("economic_overview.services.publication_services.requests.post")
    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_scheduled_economic_data_update_success_update_publication_schedule(
        self, mock_requests_get, mock_requests_post
    ):
        """
        GIVEN a single economic indicator to update exists and scraping succeeds
        WHEN scheduled_economic_data_and_schedule_update is called
        THEN the task should successfully ingest data, update schedules, and create logs
        """
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=datetime(
                2025, 11, 14, 10, 0, 0, tzinfo=timezone.utc
            ),
        )

        mock_requests_get.return_value = self.mock_insee_response
        mock_requests_post.return_value = self.mock_publication_response

        assert EconomicDataModel.objects.all().count() == 0

        result = tasks.scheduled_economic_data_and_schedule_update()
        assert result == {
            "status": "success",
            "date": "2025-12-15",
            "message": "Economic data ingested successfully.",
        }
        assert parse_query_for_testing(EconomicDataModel.objects.all()) == [
            {
                "indicator_id": self.indicator.pk,
                "period": date(2025, 11, 1),
                "data_value": 97.6,
                "comment": "",
            }
        ]
        assert parse_query_for_testing(PublicationScheduleModel.objects.all()) == [
            {
                "indicator_id": self.indicator.pk,
                "previous_publication_date": "2025-11-14 10:00:00+0000",
                "current_publication_date": "2025-12-15 09:00:00+0000",
                "next_publication_date": "2026-01-15 09:00:00+0000",
            }
        ]

    @freeze_time("2025-12-15")
    @patch("economic_overview.services.publication_services.requests.post")
    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_scheduled_economic_data_update_creates_publication_schedule(
        self, mock_requests_get, mock_requests_post
    ):
        """
        GIVEN an indicator without a publication schedule
        WHEN scheduled_economic_data_and_schedule_update is called
        THEN the task should create a new publication schedule
        """
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=None,
        )
        assert parse_query_for_testing(PublicationScheduleModel.objects.all()) == [
            {
                "indicator_id": self.indicator.pk,
                "current_publication_date": None,
                "previous_publication_date": None,
                "next_publication_date": None,
            }
        ]

        mock_requests_get.return_value = self.mock_insee_response
        mock_requests_post.return_value = self.mock_publication_response

        result = tasks.scheduled_economic_data_and_schedule_update()

        assert result == {
            "status": "success",
            "date": "2025-12-15",
            "message": "Economic data ingested successfully.",
        }
        assert parse_query_for_testing(PublicationScheduleModel.objects.all()) == [
            {
                "indicator_id": self.indicator.pk,
                "current_publication_date": "2025-12-15 09:00:00+0000",
                "previous_publication_date": None,
                "next_publication_date": "2026-01-15 09:00:00+0000",
            }
        ]
        assert parse_query_for_testing(EconomicDataModel.objects.all()) == [
            {
                "indicator_id": self.indicator.pk,
                "period": date(2025, 11, 1),
                "data_value": 97.6,
                "comment": "",
            }
        ]

    @freeze_time("2025-12-15")
    @patch("economic_overview.services.publication_services.requests.post")
    def test_scheduled_economic_data_update_no_indicators(self, mock_requests_post):
        """
        GIVEN no economic indicators to update exist
        WHEN scheduled_economic_data_and_schedule_update is called
        THEN the task should return success with no update message and no data created
        """
        EconomicIndicatorInformationModel.objects.all().delete()
        PublicationScheduleModel.objects.all().delete()
        mock_requests_post.return_value = self.mock_publication_response

        result = tasks.scheduled_economic_data_and_schedule_update()

        assert result == {
            "status": "success",
            "date": "2025-12-15",
            "message": "No economic indicators to update found.",
        }
        assert mock_requests_post.call_count == 0
        assert EconomicDataModel.objects.all().count() == 0
        assert PublicationScheduleModel.objects.all().count() == 0

    @freeze_time("2025-12-15")
    @patch("economic_overview.services.publication_services.requests.post")
    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_scheduled_economic_data_update_error_during_ingestion(
        self, mock_requests_get, mock_requests_post
    ):
        """
        GIVEN an error occurs during data ingestion
        WHEN scheduled_economic_data_and_schedule_update is called
        THEN the task should return an error status and no data should be saved
        """
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=datetime(
                2025, 11, 14, 10, 0, 0, tzinfo=timezone.utc
            ),
        )
        initial_publication_data = [
            {
                "indicator_id": self.indicator.pk,
                "current_publication_date": "2025-11-14 10:00:00+0000",
                "previous_publication_date": None,
                "next_publication_date": None,
            }
        ]
        assert (
            parse_query_for_testing(PublicationScheduleModel.objects.all())
            == initial_publication_data
        )

        mock_requests_get.side_effect = Exception("Network error")
        mock_requests_post.return_value = self.mock_publication_response

        result = tasks.scheduled_economic_data_and_schedule_update()
        assert result == {
            "status": "error",
            "date": "2025-12-15",
            "message": "Error: Network error",
        }
        assert (
            parse_query_for_testing(PublicationScheduleModel.objects.all())
            == initial_publication_data
        )
        assert EconomicDataModel.objects.all().count() == 0
        assert mock_requests_post.call_count == 0

    @freeze_time("2025-12-15")
    @patch("economic_overview.services.publication_services.requests.post")
    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_scheduled_economic_data_update_error_during_schedule_update(
        self, mock_requests_get, mock_requests_post
    ):
        """
        GIVEN an error occurs during publication schedule update
        WHEN scheduled_economic_data_and_schedule_update is called
        THEN the task should return an error status
        Note: Data ingestion may still succeed before the error
        """
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=datetime(
                2025, 11, 14, 10, 0, 0, tzinfo=timezone.utc
            ),
        )

        mock_requests_get.return_value = self.mock_insee_response
        mock_requests_post.side_effect = Exception("Publication schedule error")
        initial_publication_data = [
            {
                "indicator_id": self.indicator.pk,
                "current_publication_date": "2025-11-14 10:00:00+0000",
                "previous_publication_date": None,
                "next_publication_date": None,
            }
        ]

        assert (
            parse_query_for_testing(PublicationScheduleModel.objects.all())
            == initial_publication_data
        )

        result = tasks.scheduled_economic_data_and_schedule_update()
        assert result == {
            "status": "error",
            "date": "2025-12-15",
            "message": "Error: Publication schedule error",
        }
        assert (
            parse_query_for_testing(PublicationScheduleModel.objects.all())
            == initial_publication_data
        )
        assert parse_query_for_testing(EconomicDataModel.objects.all()) == [
            {
                "indicator_id": self.indicator.pk,
                "period": date(2025, 11, 1),
                "data_value": 97.6,
                "comment": "",
            }
        ]


class TestScheduledEconomicDataUpdateLogsCleanup(TestCase):
    """Test cases for scheduled_economic_data_update_logs_cleanup task."""

    @freeze_time("2025-12-15")
    def test_scheduled_economic_data_update_logs_cleanup_success_not_january(self):
        """
        GIVEN it's not January
        WHEN scheduled_economic_data_update_logs_cleanup is called
        THEN the task should clean up logs from the previous month
        """
        logs_date = date(2025, 11, 1)  # Previous month
        # Create test logs before cutoff date
        indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Test Indicator",
            name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        economic_data = EconomicDataModel.objects.create(
            indicator=indicator,
            period=date(2025, 12, 15),
            data_value=100.0,
        )
        log_before = EconomicDataUpdateLogModel.objects.create(
            economic_data=economic_data,
            logs="Test log before cutoff",
        )
        log_before.date_added = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        log_before.save()

        log_after = EconomicDataUpdateLogModel.objects.create(
            economic_data=economic_data,
            logs="Test log after cutoff",
        )
        log_after.date_added = datetime(2025, 12, 1, 12, 0, 0, tzinfo=timezone.utc)
        log_after.save()

        # Verify logs exist before cleanup
        assert parse_query_for_testing(EconomicDataUpdateLogModel.objects.all()) == [
            {
                "economic_data_id": economic_data.pk,
                "logs": "Test log after cutoff",
            },
            {
                "economic_data_id": economic_data.pk,
                "logs": "Test log before cutoff",
            },
        ]

        result = tasks.scheduled_economic_data_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Economic data update logs deleted successfully for 2025-11-01",
            "status": "success",
        }
        assert parse_query_for_testing(EconomicDataUpdateLogModel.objects.all()) == [
            {
                "economic_data_id": economic_data.pk,
                "logs": "Test log after cutoff",
            }
        ]

    @freeze_time("2025-01-15")
    def test_scheduled_economic_data_update_logs_cleanup_success_january(self):
        """
        GIVEN it's January
        WHEN scheduled_economic_data_update_logs_cleanup is called
        THEN the task should clean up logs from December of the previous year
        """
        logs_date = date(2024, 12, 1)  # December of previous year
        # Create test logs before cutoff date
        indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Test Indicator",
            name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        economic_data = EconomicDataModel.objects.create(
            indicator=indicator,
            period=date(2025, 1, 15),
            data_value=100.0,
        )
        log_before = EconomicDataUpdateLogModel.objects.create(
            economic_data=economic_data,
            logs="Test log before cutoff",
        )
        log_before.date_added = datetime(2024, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        log_before.save()

        log_after = EconomicDataUpdateLogModel.objects.create(
            economic_data=economic_data,
            logs="Test log after cutoff",
        )
        log_after.date_added = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        log_after.save()

        # Verify logs exist before cleanup
        assert parse_query_for_testing(EconomicDataUpdateLogModel.objects.all()) == [
            {
                "economic_data_id": economic_data.pk,
                "logs": "Test log after cutoff",
            },
            {
                "economic_data_id": economic_data.pk,
                "logs": "Test log before cutoff",
            },
        ]

        result = tasks.scheduled_economic_data_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Economic data update logs deleted successfully for 2024-12-01",
            "status": "success",
        }
        assert parse_query_for_testing(EconomicDataUpdateLogModel.objects.all()) == [
            {
                "economic_data_id": economic_data.pk,
                "logs": "Test log after cutoff",
            }
        ]

    @freeze_time("2025-12-15")
    @patch(
        "economic_overview.tasks.economic_data_services.delete_economic_data_update_logs_before_date"
    )
    def test_scheduled_economic_data_update_logs_cleanup_error(self, mock_delete):
        """
        GIVEN an error occurs during log cleanup
        WHEN scheduled_economic_data_update_logs_cleanup is called
        THEN the task should return an error status
        """
        logs_date = date(2025, 11, 1)
        mock_delete.side_effect = Exception("Database error")

        result = tasks.scheduled_economic_data_update_logs_cleanup()
        assert result == {
            "date": logs_date.isoformat(),
            "message": "Error: Database error",
            "status": "error",
        }
