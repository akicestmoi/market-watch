"""Tests for publication schedule and monthly calendar-less update services."""

from datetime import date, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from freezegun import freeze_time

from core.services.orm import convert_query_to_dictionary_list
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from economic_overview.services.publication_update import (
    MonthlyUpdateIndicatorStatus,
    MonthlyUpdateRunStatus,
    get_publication_schedules_for_dates,
    run_monthly_publication_update,
    update_publication_schedules,
)


class TestPublicationServices(TestCase):
    """Test cases for publication functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
            series_label="Test Indicator",
            full_name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.schedule = PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=None,
            current_publication_date=None,
            next_publication_date=None,
        )

    @patch(
        "economic_overview.services.publication_update.PUBLICATION_SOURCE_MAP",
        new_callable=dict,
    )
    def test_update_publication_schedules_success(self, mock_publication_source_map):
        """
        GIVEN an indicator with a publication function
        WHEN updating publication schedules
        THEN the schedule is updated
        """
        next_date1 = django_timezone.now() + timedelta(days=1)
        next_date2 = django_timezone.now() + timedelta(days=2)
        mock_publication_function = Mock()
        mock_publication_function.return_value = [next_date1, next_date2]
        mock_publication_source_map[EconomicDataSourceChoices.INSEE] = (
            mock_publication_function
        )

        result = update_publication_schedules([self.indicator])

        assert result == []
        self.schedule.refresh_from_db()
        assert self.schedule.convert_to_dict() == {
            "indicator_id": self.indicator.id,
            "previous_publication_date": None,
            "current_publication_date": next_date1,
            "next_publication_date": next_date2,
        }

    @patch(
        "economic_overview.services.publication_update.PUBLICATION_SOURCE_MAP",
        new_callable=dict,
    )
    def test_update_publication_schedules_future_date_not_reached(
        self, mock_publication_source_map
    ):
        """
        GIVEN an indicator with a current publication date in the future
        WHEN updating publication schedules
        THEN the schedule is not updated
        """
        future_date = django_timezone.now() + timedelta(days=5)
        self.schedule.current_publication_date = future_date
        self.schedule.save()

        next_date1 = django_timezone.now() + timedelta(days=1)
        next_date2 = django_timezone.now() + timedelta(days=2)
        mock_publication_function = Mock()
        mock_publication_function.return_value = [next_date1, next_date2]
        mock_publication_source_map[EconomicDataSourceChoices.INSEE] = (
            mock_publication_function
        )

        result = update_publication_schedules([self.indicator])

        assert result == [self.indicator.full_name]
        self.schedule.refresh_from_db()
        assert self.schedule.convert_to_dict() == {
            "indicator_id": self.indicator.id,
            "previous_publication_date": None,
            "current_publication_date": future_date,
            "next_publication_date": None,
        }

    @patch(
        "economic_overview.services.publication_update.PUBLICATION_SOURCE_MAP",
        new_callable=dict,
    )
    def test_update_publication_schedules_past_date(self, mock_publication_source_map):
        """
        GIVEN an indicator with a current publication date in the past
        WHEN updating publication schedules
        THEN the schedule is updated
        """
        past_date = django_timezone.now() - timedelta(days=5)
        self.schedule.current_publication_date = past_date
        self.schedule.save()

        next_date1 = django_timezone.now() + timedelta(days=1)
        next_date2 = django_timezone.now() + timedelta(days=2)
        mock_publication_function = Mock()
        mock_publication_function.return_value = [next_date1, next_date2]
        mock_publication_source_map[EconomicDataSourceChoices.INSEE] = (
            mock_publication_function
        )

        result = update_publication_schedules([self.indicator])

        assert result == []
        self.schedule.refresh_from_db()
        assert self.schedule.convert_to_dict() == {
            "indicator_id": self.indicator.id,
            "previous_publication_date": past_date,
            "current_publication_date": next_date1,
            "next_publication_date": next_date2,
        }

    @patch(
        "economic_overview.services.publication_update.PUBLICATION_SOURCE_MAP",
        new_callable=dict,
    )
    def test_update_publication_schedules_no_publication_function(
        self, mock_publication_source_map
    ):
        """
        GIVEN an indicator with no publication function
        WHEN updating publication schedules
        THEN the indicator is reported as not updated (batch continues)
        """
        indicator_no_source = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Test Indicator",
            full_name="JP Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        PublicationScheduleModel.objects.create(
            indicator=indicator_no_source,
            previous_publication_date=None,
            current_publication_date=None,
            next_publication_date=None,
        )
        result = update_publication_schedules([indicator_no_source])

        assert result == [indicator_no_source.full_name]

    @patch(
        "economic_overview.services.publication_update.PUBLICATION_SOURCE_MAP",
        new_callable=dict,
    )
    def test_update_publication_schedules_single_upcoming_date(
        self, mock_publication_source_map
    ):
        """
        GIVEN INSEE returns only one upcoming embargo (e.g. ILO unemployment)
        WHEN updating publication schedules
        THEN current is set and next is null (no IndexError)
        """
        next_date = django_timezone.now() + timedelta(days=1)
        mock_publication_function = Mock()
        mock_publication_function.return_value = [next_date]
        mock_publication_source_map[EconomicDataSourceChoices.INSEE] = (
            mock_publication_function
        )

        result = update_publication_schedules([self.indicator])

        assert result == []
        self.schedule.refresh_from_db()
        assert self.schedule.convert_to_dict() == {
            "indicator_id": self.indicator.id,
            "previous_publication_date": None,
            "current_publication_date": next_date,
            "next_publication_date": None,
        }

    def test_get_publication_schedules_for_dates_with_dates(self):
        """
        GIVEN publication schedules with dates
        WHEN getting schedules for a date range
        THEN the correct schedules are returned
        """
        start_date = date.today()
        end_date = date.today() + timedelta(days=10)
        schedule_date = django_timezone.now() + timedelta(days=5)
        out_of_range_indicator = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Out Of Range",
            full_name="Out Of Range Indicator",
            technical_name="out_of_range",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="OOR",
        )
        PublicationScheduleModel.objects.create(
            indicator=out_of_range_indicator,
            previous_publication_date=None,
            current_publication_date=django_timezone.now() + timedelta(days=-1),
            next_publication_date=None,
        )

        self.schedule.current_publication_date = schedule_date
        self.schedule.save()

        result = get_publication_schedules_for_dates(
            start_date=start_date, end_date=end_date
        )
        result_dict = convert_query_to_dictionary_list(
            queryset=result, remove_specific_fields=["date_added", "last_modified"]
        )
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "previous_publication_date": None,
                "current_publication_date": schedule_date,
                "next_publication_date": None,
            }
        ]

    def test_get_publication_schedules_for_dates_start_date_only(self):
        """
        GIVEN publication schedules with dates
        WHEN getting schedules with only start date
        THEN schedules on or after start date are returned
        """
        start_date = date.today()
        schedule_date = django_timezone.now() + timedelta(days=5)
        before_start_indicator = EconomicIndicatorInformationModel.objects.create(
            id=4,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Before Start",
            full_name="Before Start Indicator",
            technical_name="before_start",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="BEFORE",
        )
        PublicationScheduleModel.objects.create(
            indicator=before_start_indicator,
            previous_publication_date=None,
            current_publication_date=django_timezone.now() + timedelta(days=-1),
            next_publication_date=None,
        )
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Test Indicator",
            full_name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        new_date = django_timezone.now() + timedelta(days=50)
        PublicationScheduleModel.objects.create(
            indicator=new_indicator,
            previous_publication_date=None,
            current_publication_date=new_date,
            next_publication_date=None,
        )

        self.schedule.current_publication_date = schedule_date
        self.schedule.save()

        result = get_publication_schedules_for_dates(start_date=start_date)
        result_dict = convert_query_to_dictionary_list(
            queryset=result, remove_specific_fields=["date_added", "last_modified"]
        )
        assert result_dict == [
            {
                "indicator_id": new_indicator.id,
                "previous_publication_date": None,
                "current_publication_date": new_date,
                "next_publication_date": None,
            },
            {
                "indicator_id": self.indicator.id,
                "previous_publication_date": None,
                "current_publication_date": schedule_date,
                "next_publication_date": None,
            },
        ]

    def test_get_publication_schedules_for_dates_end_date_only(self):
        """
        GIVEN publication schedules with dates
        WHEN getting schedules with only end date
        THEN schedules before end date are returned
        """
        end_date = date.today() + timedelta(days=10)
        schedule_date = django_timezone.now() + timedelta(days=5)
        after_end_indicator = EconomicIndicatorInformationModel.objects.create(
            id=5,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="After End",
            full_name="After End Indicator",
            technical_name="after_end",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.FRED,
            ticker="AFTER",
        )
        PublicationScheduleModel.objects.create(
            indicator=after_end_indicator,
            previous_publication_date=None,
            current_publication_date=django_timezone.now() + timedelta(days=11),
            next_publication_date=None,
        )
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Test Indicator",
            full_name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        new_date = django_timezone.now() + timedelta(days=-50)
        PublicationScheduleModel.objects.create(
            indicator=new_indicator,
            previous_publication_date=None,
            current_publication_date=new_date,
            next_publication_date=None,
        )

        self.schedule.current_publication_date = schedule_date
        self.schedule.save()

        result = get_publication_schedules_for_dates(end_date=end_date)
        result_dict = convert_query_to_dictionary_list(
            queryset=result, remove_specific_fields=["date_added", "last_modified"]
        )

        assert result_dict == [
            {
                "indicator_id": new_indicator.id,
                "previous_publication_date": None,
                "current_publication_date": new_date,
                "next_publication_date": None,
            },
            {
                "indicator_id": self.indicator.id,
                "previous_publication_date": None,
                "current_publication_date": schedule_date,
                "next_publication_date": None,
            },
        ]

    def test_get_publication_schedules_for_dates_no_filters(self):
        """
        GIVEN publication schedules
        WHEN getting schedules without date filters
        THEN all schedules are returned
        """
        schedule_date = django_timezone.now() + timedelta(days=5)
        self.schedule.current_publication_date = schedule_date
        self.schedule.save()
        result = get_publication_schedules_for_dates()
        result_dict = convert_query_to_dictionary_list(
            queryset=result, remove_specific_fields=["date_added", "last_modified"]
        )
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "previous_publication_date": None,
                "current_publication_date": schedule_date,
                "next_publication_date": None,
            },
        ]

    def test_get_publication_schedules_for_dates_out_of_range(self):
        """
        GIVEN publication schedules with dates
        WHEN getting schedules for a date range that doesn't include them
        THEN no schedules are returned
        """
        start_date = date.today() + timedelta(days=20)
        end_date = date.today() + timedelta(days=30)
        schedule_date = django_timezone.now() + timedelta(days=5)

        self.schedule.current_publication_date = schedule_date
        self.schedule.save()

        result = get_publication_schedules_for_dates(
            start_date=start_date, end_date=end_date
        )
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == []


class TestRunMonthlyPublicationUpdate(TestCase):
    """Test cases for 'run_monthly_publication_update'."""

    def setUp(self):
        """Create one monthly-update indicator."""
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=9001,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
            series_label="Update Indicator",
            full_name="France Update Indicator",
            technical_name="update_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.BANQUE_DE_FRANCE,
            ticker="update_ticker",
            publication_schedule_mode=PublicationScheduleModeChoices.MONTHLY_UPDATE,
        )

    @freeze_time("2026-11-11")
    def test_run_monthly_publication_update_skips_when_not_first_of_month(self):
        """
        GIVEN a mid-month day
        WHEN run_monthly_publication_update is called without force
        THEN the run is skipped with an empty report
        """
        assert run_monthly_publication_update() == {
            "as_of": "2026-11-11",
            "status": MonthlyUpdateRunStatus.SKIPPED_NOT_FIRST_OF_MONTH.value,
            "message": (
                "Skipped: 2026-11-11 is not the first calendar day of the month."
            ),
            "checked": 0,
            "updated": [],
            "failed": [],
            "results": [],
        }

    @freeze_time("2026-11-01")
    @patch("economic_overview.services.publication_update.ingest_latest_economic_data")
    def test_run_monthly_publication_update_ingests_on_first_of_month(
        self, mock_ingest_latest
    ):
        """
        GIVEN the first calendar day of the month
        WHEN run_monthly_publication_update is called
        THEN the indicator is ingested and reported as updated
        """
        mock_ingest_latest.return_value = []

        assert run_monthly_publication_update() == {
            "as_of": "2026-11-01",
            "status": MonthlyUpdateRunStatus.SUCCESS.value,
            "message": "Checked 1 indicator(s): 1 updated, 0 failed.",
            "checked": 1,
            "updated": ["France Update Indicator"],
            "failed": [],
            "results": [
                {
                    "name": "France Update Indicator",
                    "status": MonthlyUpdateIndicatorStatus.SUCCESS.value,
                }
            ],
        }
        mock_ingest_latest.assert_called_once_with([self.indicator])

    @freeze_time("2026-11-11")
    @patch("economic_overview.services.publication_update.ingest_latest_economic_data")
    def test_run_monthly_publication_update_force_reports_failed(
        self, mock_ingest_latest
    ):
        """
        GIVEN force=True mid-month and ingest fails for the indicator
        WHEN run_monthly_publication_update is called
        THEN the indicator is reported as failed
        """
        mock_ingest_latest.return_value = ["France Update Indicator"]

        assert run_monthly_publication_update(force=True) == {
            "as_of": "2026-11-11",
            "status": MonthlyUpdateRunStatus.SUCCESS.value,
            "message": "Checked 1 indicator(s): 0 updated, 1 failed.",
            "checked": 1,
            "updated": [],
            "failed": ["France Update Indicator"],
            "results": [
                {
                    "name": "France Update Indicator",
                    "status": MonthlyUpdateIndicatorStatus.FAILED.value,
                }
            ],
        }
