from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest  # type: ignore[reportMissingImports]
from django.test import TestCase
from django.utils import timezone as django_timezone

from core.services import convert_query_to_dictionary_list
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from economic_overview.services.publication_services import (
    get_publication_schedules_for_dates,
    update_publication_schedules,
)


class TestPublicationServices(TestCase):
    """Test cases for publication_services functions."""

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
        self.schedule = PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=None,
            current_publication_date=None,
            next_publication_date=None,
        )

    @patch(
        "economic_overview.services.publication_services.PUBLICATION_SOURCE_MAP",
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
        mock_publication_function = Mock(return_value=[next_date1, next_date2])
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
        "economic_overview.services.publication_services.PUBLICATION_SOURCE_MAP",
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
        mock_publication_function = Mock(return_value=[next_date1, next_date2])
        mock_publication_source_map[EconomicDataSourceChoices.INSEE] = (
            mock_publication_function
        )

        result = update_publication_schedules([self.indicator])

        assert result == [self.indicator.name]
        self.schedule.refresh_from_db()
        assert self.schedule.convert_to_dict() == {
            "indicator_id": self.indicator.id,
            "previous_publication_date": None,
            "current_publication_date": future_date,
            "next_publication_date": None,
        }

    @patch(
        "economic_overview.services.publication_services.PUBLICATION_SOURCE_MAP",
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
        mock_publication_function = Mock(return_value=[next_date1, next_date2])
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
        "economic_overview.services.publication_services.PUBLICATION_SOURCE_MAP",
        new_callable=dict,
    )
    def test_update_publication_schedules_no_publication_function(
        self, mock_publication_source_map
    ):
        """
        GIVEN an indicator with no publication function
        WHEN updating publication schedules
        THEN a ValueError is raised
        """
        indicator_no_source = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            type="Test Indicator",
            name="Test Indicator Name",
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
        with pytest.raises(ValueError) as exc_info:
            update_publication_schedules([indicator_no_source])

        assert (
            f"Publication function not found for indicator: {indicator_no_source.name}"
            in str(exc_info.value)
        )

    def test_get_publication_schedules_for_dates_with_dates(self):
        """
        GIVEN publication schedules with dates
        WHEN getting schedules for a date range
        THEN the correct schedules are returned
        """
        start_date = date.today()
        end_date = date.today() + timedelta(days=10)
        schedule_date = django_timezone.now() + timedelta(days=5)

        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=None,
            current_publication_date=start_date + timedelta(days=-1),
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

        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=None,
            current_publication_date=start_date + timedelta(days=-1),
            next_publication_date=None,
        )
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            type="Test Indicator",
            name="Test Indicator Name",
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

        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            previous_publication_date=None,
            current_publication_date=end_date + timedelta(days=1),
            next_publication_date=None,
        )
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            type="Test Indicator",
            name="Test Indicator Name",
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
