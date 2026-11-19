"""Tests for economic data query, transform, and ingest helpers."""

from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from core.services.orm import convert_query_to_dictionary_list
from core.services.time_series_calculation import (
    ValueChangeType,
    calculate_value_change,
)
from core.testing import parse_query_for_testing
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from economic_overview.services.economic_data import (
    TimedEconomicDataValue,
    _IndicatorValueTriplet,
    change_triplet_values_for_mode,
    check_economic_indicator_existence,
    delete_economic_data,
    delete_economic_data_update_logs_before_date,
    get_economic_data,
    get_economic_indicators_by_names,
    get_economic_indicators_to_update,
    get_lag_for_mode_change_calculation,
    get_lookback_period_for_mode_change,
    identify_not_existing_indicators,
    ingest_historical_economic_data,
    ingest_latest_economic_data,
    ingest_specific_economic_data,
)


class TestEconomicDataServices(TestCase):
    """Test cases for economic_data functions."""

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
        self.period = date(2024, 1, 15)
        self.economic_data = EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.period,
            data_value=100.0,
            comment="Test comment",
        )

    def test_get_economic_indicators_by_names_with_names(self):
        """
        GIVEN existing indicator names
        WHEN getting economic indicators by names
        THEN the correct indicators are returned
        """
        EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        result = get_economic_indicators_by_names([self.indicator.full_name])
        result_dict = convert_query_to_dictionary_list(result)

        assert result_dict == [
            {
                "location": EconomicDataLocationChoices.FR,
                "category": EconomicDataCategoryChoices.BUSINESS,
                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                "series_label": "Test Indicator",
                "full_name": "Test Indicator Name",
                "technical_name": "test_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "source": EconomicDataSourceChoices.INSEE,
                "ticker": "001565530",
                "base_unit": "",
                "base_year": None,
                "base_currency": "",
                "default_mode": "Raw",
                "measure_type": "FLOW",
                "parent_series_label": "",
                "expansion_relation": "",
                "is_hidden": False,
                "publication_schedule_mode": "CALENDAR",
                "description": "",
                "source_url": "",
            }
        ]

    def test_get_economic_indicators_by_names_empty_list(self):
        """
        GIVEN an empty list of indicator names
        WHEN getting economic indicators by names
        THEN all indicators are returned
        """
        EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        result = get_economic_indicators_by_names([])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "location": EconomicDataLocationChoices.FR.value,
                "category": EconomicDataCategoryChoices.BUSINESS.value,
                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                "series_label": "Test Indicator",
                "full_name": "Test Indicator Name",
                "technical_name": "test_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.INSEE.value,
                "ticker": "001565530",
                "base_unit": "",
                "base_year": None,
                "base_currency": "",
                "default_mode": "Raw",
                "measure_type": "FLOW",
                "parent_series_label": "",
                "expansion_relation": "",
                "is_hidden": False,
                "publication_schedule_mode": "CALENDAR",
                "description": "",
                "source_url": "",
            },
            {
                "location": EconomicDataLocationChoices.JP.value,
                "category": EconomicDataCategoryChoices.GOVERNMENT.value,
                "subcategory": EconomicDataSubcategoryChoices.BUDGET,
                "series_label": "Other Indicator",
                "full_name": "Other Indicator Name",
                "technical_name": "other_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.JP_CABINET_OFFICE.value,
                "ticker": "001565531",
                "base_unit": "",
                "base_year": None,
                "base_currency": "",
                "default_mode": "Raw",
                "measure_type": "FLOW",
                "parent_series_label": "",
                "expansion_relation": "",
                "is_hidden": False,
                "publication_schedule_mode": "CALENDAR",
                "description": "",
                "source_url": "",
            },
        ]

    def test_get_economic_indicators_by_names_no_match(self):
        """
        GIVEN non-existent indicator names
        WHEN getting economic indicators by names
        THEN an empty queryset is returned
        """
        result = get_economic_indicators_by_names(["NonExistent"])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == []

    def test_get_economic_indicators_to_update_with_dates(self):
        """
        GIVEN a publication schedule with dates
        WHEN getting indicators to update
        THEN the correct indicators are returned
        """
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=date.today() + timedelta(days=1),
        )
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        PublicationScheduleModel.objects.create(
            indicator=new_indicator,
            current_publication_date=date.today() + timedelta(days=3),
        )

        result = get_economic_indicators_to_update(
            start_date=date.today(), end_date=date.today() + timedelta(days=2)
        )
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "location": EconomicDataLocationChoices.FR.value,
                "category": EconomicDataCategoryChoices.BUSINESS.value,
                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                "series_label": "Test Indicator",
                "full_name": "Test Indicator Name",
                "technical_name": "test_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.INSEE.value,
                "ticker": "001565530",
                "base_unit": "",
                "base_year": None,
                "base_currency": "",
                "default_mode": "Raw",
                "measure_type": "FLOW",
                "parent_series_label": "",
                "expansion_relation": "",
                "is_hidden": False,
                "publication_schedule_mode": "CALENDAR",
                "description": "",
                "source_url": "",
            }
        ]

    def test_get_economic_indicators_to_update_no_publication_date(self):
        """
        GIVEN indicators with no publication date
        WHEN getting indicators to update
        THEN indicators that have no publication date are returned
        """
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        PublicationScheduleModel.objects.create(
            indicator=new_indicator,
            current_publication_date=None,
        )

        result = get_economic_indicators_to_update()
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "location": EconomicDataLocationChoices.JP.value,
                "category": EconomicDataCategoryChoices.GOVERNMENT.value,
                "subcategory": EconomicDataSubcategoryChoices.BUDGET,
                "series_label": "Other Indicator",
                "full_name": "Other Indicator Name",
                "technical_name": "other_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.JP_CABINET_OFFICE.value,
                "ticker": "001565531",
                "base_unit": "",
                "base_year": None,
                "base_currency": "",
                "default_mode": "Raw",
                "measure_type": "FLOW",
                "parent_series_label": "",
                "expansion_relation": "",
                "is_hidden": False,
                "publication_schedule_mode": "CALENDAR",
                "description": "",
                "source_url": "",
            }
        ]

    def test_check_economic_indicator_existence_true(self):
        """
        GIVEN an existing indicator name
        WHEN checking if it exists
        THEN True is returned
        """
        result = check_economic_indicator_existence(self.indicator.full_name)

        assert result is True

    def test_check_economic_indicator_existence_false(self):
        """
        GIVEN a non-existent indicator name
        WHEN checking if it exists
        THEN False is returned
        """
        result = check_economic_indicator_existence("NonExistent")

        assert result is False

    def test_identify_not_existing_indicators_all_exist(self):
        """
        GIVEN a list of existing indicator names
        WHEN identifying not existing indicators
        THEN an empty list is returned
        """
        result = identify_not_existing_indicators([self.indicator.full_name])

        assert result == []

    def test_identify_not_existing_indicators_some_not_exist(self):
        """
        GIVEN a list with some non-existent indicator names
        WHEN identifying not existing indicators
        THEN only non-existent names are returned
        """
        result = identify_not_existing_indicators(
            [self.indicator.full_name, "NonExistent1", "NonExistent2"]
        )

        assert result == ["NonExistent1", "NonExistent2"]

    def test_get_economic_data_with_indicator_names(self):
        """
        GIVEN existing economic data and indicator names
        WHEN getting economic data
        THEN the correct data is returned
        """
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        EconomicDataModel.objects.create(
            indicator=new_indicator,
            period=self.period,
            data_value=200.0,
            comment="Other comment",
        )
        result = get_economic_data(indicator_names=[self.indicator.full_name])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": self.period,
                "data_value": 100.0,
                "comment": "Test comment",
            }
        ]

    def test_get_economic_data_with_period(self):
        """
        GIVEN existing economic data and a period
        WHEN getting economic data
        THEN the correct data for that period is returned
        """
        other_period = date(2024, 2, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=other_period,
            data_value=200.0,
        )

        result = get_economic_data(period=self.period.isoformat())
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": self.period,
                "data_value": 100.0,
                "comment": "Test comment",
            }
        ]

    def test_get_economic_data_with_indicator_names_and_period(self):
        """
        GIVEN existing economic data, indicator names, and a period
        WHEN getting economic data
        THEN the correct filtered data is returned
        """
        other_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        EconomicDataModel.objects.create(
            indicator=other_indicator,
            period=self.period,
            data_value=300.0,
        )

        result = get_economic_data(
            indicator_names=[self.indicator.full_name], period=self.period.isoformat()
        )
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": self.period,
                "data_value": 100.0,
                "comment": "Test comment",
            }
        ]

    def test_get_economic_data_no_filters(self):
        """
        GIVEN existing economic data
        WHEN getting economic data without filters
        THEN all data is returned
        """
        new_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GOVERNMENT,
            subcategory=EconomicDataSubcategoryChoices.BUDGET,
            series_label="Other Indicator",
            full_name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        EconomicDataModel.objects.create(
            indicator=new_indicator,
            period=self.period,
            data_value=200.0,
            comment="Other comment",
        )

        result = get_economic_data()
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": self.period,
                "data_value": 100.0,
                "comment": "Test comment",
            },
            {
                "indicator_id": new_indicator.id,
                "period": self.period,
                "data_value": 200.0,
                "comment": "Other comment",
            },
        ]

    def test_delete_economic_data_by_ids(self):
        """
        GIVEN existing economic data
        WHEN deleting economic data by IDs
        THEN the specified data is deleted
        """
        deleted_count = delete_economic_data([self.economic_data.pk])

        assert deleted_count == 1
        result = get_economic_data(indicator_names=[self.indicator.full_name])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == []

    def test_delete_economic_data_by_ids_multiple(self):
        """
        GIVEN existing economic data for multiple periods
        WHEN deleting economic data by multiple IDs
        THEN all specified data is deleted
        """
        other_period = date(2024, 2, 15)
        other_data = EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=other_period,
            data_value=200.0,
        )

        deleted_count = delete_economic_data([self.economic_data.pk, other_data.pk])

        assert deleted_count == 2
        result = get_economic_data(indicator_names=[self.indicator.full_name])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == []

    def test_delete_economic_data_update_logs_before_date(self):
        """
        GIVEN economic data update logs with different dates
        WHEN delete_economic_data_update_logs_before_date is called with a cutoff date
        THEN logs before the cutoff date should be deleted
        """
        cutoff_date = date(2024, 1, 10)

        # Create logs with different dates
        log_before = EconomicDataUpdateLogModel.objects.create(
            economic_data=self.economic_data,
            logs="Log before cutoff",
        )
        log_before.date_added = datetime(2024, 1, 5, 12, 0, 0)
        log_before.save()

        log_after = EconomicDataUpdateLogModel.objects.create(
            economic_data=self.economic_data,
            logs="Log after cutoff",
        )
        log_after.date_added = datetime(2024, 1, 15, 12, 0, 0)
        log_after.save()

        delete_economic_data_update_logs_before_date(cutoff_date)

        result = EconomicDataUpdateLogModel.objects.all()
        assert parse_query_for_testing(result) == [
            {
                "economic_data_id": self.economic_data.pk,
                "logs": "Log after cutoff",
            }
        ]

    def test_delete_economic_data_update_logs_before_date_no_logs(self):
        """
        GIVEN no economic data update logs exist
        WHEN delete_economic_data_update_logs_before_date is called
        THEN no error should occur
        """
        cutoff_date = date(2024, 1, 10)
        EconomicDataUpdateLogModel.objects.all().delete()

        delete_economic_data_update_logs_before_date(cutoff_date)

        assert EconomicDataUpdateLogModel.objects.count() == 0


class TestGetLagForModeChangeCalculation(SimpleTestCase):
    """Lag lookup for MoM / QoQ / QoQy / YoY modes."""

    def test_raw_always_zero(self):
        """
        GIVEN any publication frequency
        WHEN lag is requested for Raw mode
        THEN the lag is 0
        """
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.RAW,
            )
            == 0
        )

    def test_month_lag_is_one(self):
        """
        GIVEN any publication frequency
        WHEN lag is requested for MoM mode
        THEN the lag is 1
        """
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.MONTH,
            )
            == 1
        )
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.QUARTERLY,
                IndicatorDisplayModeChoices.MONTH,
            )
            == 1
        )

    def test_quarter_lags_by_frequency(self):
        """
        GIVEN monthly / quarterly / annual frequency
        WHEN lag is requested for QoQ mode
        THEN the lag is 3 / 1 / 1
        """
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.QUARTER,
            )
            == 3
        )
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.QUARTERLY,
                IndicatorDisplayModeChoices.QUARTER,
            )
            == 1
        )
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.ANNUAL,
                IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
            )
            == 1
        )

    def test_annual_lags_by_frequency(self):
        """
        GIVEN monthly / quarterly / annual frequency
        WHEN lag is requested for YoY mode
        THEN the lag is 12 / 4 / 1
        """
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.MONTHLY,
                IndicatorDisplayModeChoices.ANNUAL,
            )
            == 12
        )
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.QUARTERLY,
                IndicatorDisplayModeChoices.ANNUAL,
            )
            == 4
        )
        assert (
            get_lag_for_mode_change_calculation(
                EconomicPublicationFrequencyChoices.ANNUAL,
                IndicatorDisplayModeChoices.ANNUAL,
            )
            == 1
        )


class TestGetLookbackPeriodForModeChange(SimpleTestCase):
    """Calendar lookback periods for growth modes."""

    def test_monthly_annual_lookback_is_same_month_prior_year(self):
        """
        GIVEN a monthly period and Annual mode
        WHEN resolving the lookback period
        THEN the same calendar month one year earlier is returned
        """
        assert get_lookback_period_for_mode_change(
            date(2026, 9, 1),
            EconomicPublicationFrequencyChoices.MONTHLY,
            IndicatorDisplayModeChoices.ANNUAL,
        ) == date(2025, 9, 1)


class TestChangeIndicatorValuesMode(SimpleTestCase):
    """Newest-first dated raw series → current / previous / change triplet."""

    def test_empty_series(self):
        """
        GIVEN an empty time series
        WHEN changing mode
        THEN all triplet fields are None
        """
        assert change_triplet_values_for_mode(
            [],
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            mode=IndicatorDisplayModeChoices.RAW,
        ) == _IndicatorValueTriplet(current=None, previous=None, change=None)

    def test_raw_absolute_change(self):
        """
        GIVEN a newest-first raw series
        WHEN changing to Raw mode
        THEN current / previous are consecutive levels and change is absolute
        """
        assert change_triplet_values_for_mode(
            [
                TimedEconomicDataValue(date(2024, 7, 1), 110.0),
                TimedEconomicDataValue(date(2024, 4, 1), 100.0),
                TimedEconomicDataValue(date(2024, 1, 1), 90.0),
            ],
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            mode=IndicatorDisplayModeChoices.RAW,
        ) == _IndicatorValueTriplet(current=110.0, previous=100.0, change=10.0)

    def test_quarter_percent_growth(self):
        """
        GIVEN a quarterly series with enough history
        WHEN changing to Quarter mode
        THEN current / previous are QoQ percent growths and change is their delta
        """
        # Newest-first: 110, 100, 80 → QoQ at 0 = 10%, QoQ at 1 = 25%
        assert change_triplet_values_for_mode(
            [
                TimedEconomicDataValue(date(2024, 7, 1), 110.0),
                TimedEconomicDataValue(date(2024, 4, 1), 100.0),
                TimedEconomicDataValue(date(2024, 1, 1), 80.0),
            ],
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            mode=IndicatorDisplayModeChoices.QUARTER,
        ) == _IndicatorValueTriplet(current=10.0, previous=25.0, change=-15.0)

    def test_monthly_yoy_uses_calendar_month_not_observation_count(self):
        """
        GIVEN monthly CPI with Sep 2025 missing and Aug 2025 present
        WHEN changing to Annual (YoY) mode
        THEN Sep YoY is None; Aug YoY still uses Aug 2025
        """
        previous_yoy = calculate_value_change(334.131, 323.291, ValueChangeType.PERCENT)
        assert change_triplet_values_for_mode(
            [
                TimedEconomicDataValue(date(2026, 9, 1), 336.298),
                TimedEconomicDataValue(date(2026, 8, 1), 334.131),
                TimedEconomicDataValue(date(2025, 8, 1), 323.291),
            ],
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            mode=IndicatorDisplayModeChoices.ANNUAL,
        ) == _IndicatorValueTriplet(current=None, previous=previous_yoy, change=None)

    def test_monthly_yoy_matches_same_calendar_month(self):
        """
        GIVEN monthly CPI with Sep 2026 and Sep 2025
        WHEN changing to Annual (YoY) mode
        THEN YoY uses the same calendar month one year earlier
        """
        current_yoy = calculate_value_change(336.298, 324.245, ValueChangeType.PERCENT)
        previous_yoy = calculate_value_change(334.131, 323.291, ValueChangeType.PERCENT)
        assert change_triplet_values_for_mode(
            [
                TimedEconomicDataValue(date(2026, 9, 1), 336.298),
                TimedEconomicDataValue(date(2026, 8, 1), 334.131),
                TimedEconomicDataValue(date(2025, 9, 1), 324.245),
                TimedEconomicDataValue(date(2025, 8, 1), 323.291),
            ],
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            mode=IndicatorDisplayModeChoices.ANNUAL,
        ) == _IndicatorValueTriplet(
            current=current_yoy,
            previous=previous_yoy,
            change=(
                current_yoy - previous_yoy
                if current_yoy is not None and previous_yoy is not None
                else None
            ),
        )


def _scraper_side_effect(ticker, period, frequency=None, location=None):
    if ticker == "TEST":
        return [{"period": date(2024, 1, 15), "data_value": 100.0, "comment": ""}]
    return [{"period": None, "data_value": None, "comment": "No data"}]


def _scraper_multiple_periods_side_effect(
    ticker, period, frequency=None, location=None
):
    if period == "2024-01":
        return [{"period": date(2024, 1, 15), "data_value": 100.0, "comment": ""}]
    return [{"period": date(2024, 2, 15), "data_value": 200.0, "comment": ""}]


class TestEconomicDataIngest(TestCase):
    """Test cases for economic data ingest functions."""

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
            ticker="TEST",
        )
        self.target_period = "2024-01"

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_economic_data_success(self, mock_source_scrap_map):
        """
        GIVEN an indicator with a successful scraper
        WHEN ingesting economic data
        THEN the data is successfully ingested
        """
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_latest_economic_data([self.indicator])

        assert result == []
        economic_data = EconomicDataModel.objects.filter(indicator=self.indicator)
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_economic_data_no_value(self, mock_source_scrap_map):
        """
        GIVEN an indicator with a scraper that returns no value
        WHEN ingesting economic data
        THEN the indicator is listed as not updated
        """
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {"period": None, "data_value": None, "comment": "No data"}
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_latest_economic_data([self.indicator])

        assert result == [self.indicator.full_name]
        economic_data = EconomicDataModel.objects.filter(indicator=self.indicator)
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": None,
                "data_value": None,
                "comment": "No data",
            }
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_economic_data_multiple_indicators(self, mock_source_scrap_map):
        """
        GIVEN multiple indicators
        WHEN ingesting economic data
        THEN all indicators are processed
        """
        other_indicator = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Other test Indicator",
            full_name="Other test Indicator Name",
            technical_name="other_test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="OTHER_TEST",
        )

        mock_scraper = Mock()
        mock_scraper.side_effect = _scraper_side_effect
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_latest_economic_data([self.indicator, other_indicator])

        assert result == [other_indicator.full_name]
        economic_data = EconomicDataModel.objects.all()
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            },
            {
                "indicator_id": other_indicator.id,
                "period": None,
                "data_value": None,
                "comment": "No data",
            },
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_success(self, mock_source_scrap_map):
        """
        GIVEN an indicator and specific periods
        WHEN ingesting specific economic data
        THEN the data for those periods is ingested
        """
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_specific_economic_data(
            [self.indicator], periods=[[self.target_period]]
        )

        assert result == []
        economic_data = EconomicDataModel.objects.filter(indicator=self.indicator)
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_no_value(self, mock_source_scrap_map):
        """
        GIVEN an indicator and specific periods with no value
        WHEN ingesting specific economic data
        THEN the indicator and period are listed as not updated
        """
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {"period": None, "data_value": None, "comment": "No data"}
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_specific_economic_data(
            [self.indicator], periods=[[self.target_period]]
        )

        assert result == [
            {
                "indicator": self.indicator.full_name,
                "period": self.target_period,
            }
        ]
        economic_data = EconomicDataModel.objects.all()
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": None,
                "data_value": None,
                "comment": "No data",
            }
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_multiple_periods(
        self, mock_source_scrap_map
    ):
        """
        GIVEN an indicator and multiple periods
        WHEN ingesting specific economic data
        THEN all periods are processed
        """
        period1 = "2024-01"
        period2 = "2024-02"

        mock_scraper = Mock()
        mock_scraper.side_effect = _scraper_multiple_periods_side_effect
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_specific_economic_data(
            [self.indicator], periods=[[period1, period2]]
        )

        assert result == []
        economic_data = EconomicDataModel.objects.all()
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            },
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 2, 15),
                "data_value": 200.0,
                "comment": "",
            },
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_update_to_none_skip(
        self, mock_source_scrap_map
    ):
        """
        GIVEN an existing data value for an indicator and a period
        WHEN updating the data value to None
        THEN the data for the period is not updated
        """
        period = "2024-01"
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=date(2024, 1, 15),
            data_value=100.0,
            comment="",
        )
        economic_data = EconomicDataModel.objects.all()
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]

        mock_scraper = Mock()
        mock_scraper.return_value = [
            {
                "period": date(2024, 1, 15),
                "data_value": None,
                "comment": "No data",
            }
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_specific_economic_data([self.indicator], periods=[[period]])

        assert result == [{"indicator": self.indicator.full_name, "period": period}]
        economic_data = EconomicDataModel.objects.all()
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            },
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_no_scraper(self, mock_source_scrap_map):
        """
        GIVEN an indicator with no scraper function
        WHEN ingesting specific economic data
        THEN the indicator and period are listed as not updated
        """
        indicator_no_source = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Test Indicator 3",
            full_name="Test Indicator Name 3",
            technical_name="test_indicator_3",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565532",
        )

        result = ingest_specific_economic_data(
            [indicator_no_source], periods=[[self.target_period]]
        )
        assert result == [
            {
                "indicator": indicator_no_source.full_name,
                "period": self.target_period,
            }
        ]
        economic_data = EconomicDataModel.objects.all()
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": indicator_no_source.id,
                "period": None,
                "data_value": None,
                "comment": "No scraping function found.",
            }
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_economic_data_creates_data_update_log(self, mock_source_scrap_map):
        """
        GIVEN an existing economic data
        WHEN ingesting economic data to update it
        THEN an economic data update log is created
        """
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=date(2024, 1, 15),
            data_value=90.0,
            comment="",
        )
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        ingest_latest_economic_data([self.indicator])

        economic_data = EconomicDataModel.objects.get(
            indicator=self.indicator, period=date(2024, 1, 15)
        )
        queryset = EconomicDataUpdateLogModel.objects.filter(
            economic_data=economic_data
        )
        logs = convert_query_to_dictionary_list(queryset, remove_foreign_key=True)
        assert logs == [
            {
                "logs": "Automated data update on TEST. Updated data_value from 90.0 to 100.0.",
            },
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_creates_data_update_log(
        self, mock_source_scrap_map
    ):
        """
        GIVEN an existing economic data
        WHEN ingesting specific economic data to update it
        THEN an economic data update log is created
        """
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=date(2024, 1, 15),
            data_value=90.0,
            comment="",
        )
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        ingest_specific_economic_data([self.indicator], periods=[[self.target_period]])

        economic_data = EconomicDataModel.objects.get(
            indicator=self.indicator, period=date(2024, 1, 15)
        )
        queryset = EconomicDataUpdateLogModel.objects.filter(
            economic_data=economic_data
        )
        logs = convert_query_to_dictionary_list(queryset, remove_foreign_key=True)
        assert logs == [
            {
                "logs": "Automated data update on TEST. Updated data_value from 90.0 to 100.0.",
            },
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_historical_economic_data_success(self, mock_source_scrap_map):
        """
        GIVEN a scraper returning multiple values
        WHEN ingesting historical economic data for a date window
        THEN only values within the date range are stored
        """
        mock_scraper = Mock()
        mock_scraper.return_value = [
            {"period": date(2023, 12, 1), "data_value": 99.0, "comment": ""},
            {"period": date(2024, 1, 1), "data_value": 100.0, "comment": ""},
            {"period": date(2024, 2, 1), "data_value": 101.5, "comment": ""},
            {"period": date(2025, 1, 1), "data_value": 110.0, "comment": ""},
        ]
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_historical_economic_data(
            [self.indicator],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert result == []
        mock_scraper.assert_called_once_with(
            self.indicator.ticker,
            None,
            self.indicator.frequency,
            self.indicator.location,
        )
        economic_data = EconomicDataModel.objects.filter(
            indicator=self.indicator
        ).order_by("period")
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == [
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 1, 1),
                "data_value": 100.0,
                "comment": "",
            },
            {
                "indicator_id": self.indicator.id,
                "period": date(2024, 2, 1),
                "data_value": 101.5,
                "comment": "",
            },
        ]

    @patch(
        "economic_overview.services.economic_data.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_historical_economic_data_no_values(self, mock_source_scrap_map):
        """
        GIVEN a historical scraper that returns no usable values
        WHEN ingesting historical economic data
        THEN the indicator is listed as not updated
        """
        mock_scraper = Mock()
        mock_scraper.return_value = []
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_historical_economic_data(
            [self.indicator],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert result == [
            {
                "indicator": self.indicator.full_name,
                "period": "2024-01-01/2024-12-31",
            }
        ]
