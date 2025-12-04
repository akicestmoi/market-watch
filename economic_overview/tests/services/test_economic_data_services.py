from datetime import date, timedelta

from django.test import TestCase

from core.services import convert_query_to_dictionary_list
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from economic_overview.services.economic_data_services import (
    check_economic_indicator_existence,
    delete_economic_data,
    get_economic_data,
    get_economic_indicators_by_names,
    get_economic_indicators_to_update,
    identify_not_existing_indicators,
)


class TestEconomicDataServices(TestCase):
    """Test cases for economic_data_services functions."""

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
            category=EconomicDataCategoryChoices.GROWTH,
            type="Other Indicator",
            name="Other Indicator Name",
            technical_name="other_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        result = get_economic_indicators_by_names([self.indicator.name])
        result_dict = convert_query_to_dictionary_list(result)

        assert result_dict == [
            {
                "location": EconomicDataLocationChoices.FR,
                "category": EconomicDataCategoryChoices.CONFIDENCE,
                "type": "Test Indicator",
                "name": "Test Indicator Name",
                "technical_name": "test_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                "source": EconomicDataSourceChoices.INSEE,
                "ticker": "001565530",
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
            type="Other Indicator",
            name="Other Indicator Name",
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
                "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                "type": "Test Indicator",
                "name": "Test Indicator Name",
                "technical_name": "test_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.INSEE.value,
                "ticker": "001565530",
            },
            {
                "location": EconomicDataLocationChoices.JP.value,
                "category": EconomicDataCategoryChoices.GOVERNMENT.value,
                "type": "Other Indicator",
                "name": "Other Indicator Name",
                "technical_name": "other_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.JP_CABINET_OFFICE.value,
                "ticker": "001565531",
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
            category=EconomicDataCategoryChoices.GROWTH,
            type="Other Indicator",
            name="Other Indicator Name",
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
                "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                "type": "Test Indicator",
                "name": "Test Indicator Name",
                "technical_name": "test_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.INSEE.value,
                "ticker": "001565530",
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
            type="Other Indicator",
            name="Other Indicator Name",
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
                "type": "Other Indicator",
                "name": "Other Indicator Name",
                "technical_name": "other_indicator",
                "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                "source": EconomicDataSourceChoices.JP_CABINET_OFFICE.value,
                "ticker": "001565531",
            }
        ]

    def test_check_economic_indicator_existence_true(self):
        """
        GIVEN an existing indicator name
        WHEN checking if it exists
        THEN True is returned
        """
        result = check_economic_indicator_existence(self.indicator.name)

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
        result = identify_not_existing_indicators([self.indicator.name])

        assert result == []

    def test_identify_not_existing_indicators_some_not_exist(self):
        """
        GIVEN a list with some non-existent indicator names
        WHEN identifying not existing indicators
        THEN only non-existent names are returned
        """
        result = identify_not_existing_indicators(
            [self.indicator.name, "NonExistent1", "NonExistent2"]
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
            type="Other Indicator",
            name="Other Indicator Name",
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
        result = get_economic_data(indicator_names=[self.indicator.name])
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
            category=EconomicDataCategoryChoices.GROWTH,
            type="Other Indicator",
            name="Other Indicator Name",
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
            indicator_names=[self.indicator.name], period=self.period.isoformat()
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
            type="Other Indicator",
            name="Other Indicator Name",
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

    def test_delete_economic_data_with_period(self):
        """
        GIVEN existing economic data
        WHEN deleting economic data for a specific indicator and period
        THEN the data is deleted
        """
        delete_economic_data(self.indicator.name, self.period.isoformat())

        result = get_economic_data(indicator_names=[self.indicator.name])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == []

    def test_delete_economic_data_without_period(self):
        """
        GIVEN existing economic data
        WHEN deleting economic data for a specific indicator without period
        THEN all data for that indicator is deleted
        """
        other_period = date(2024, 2, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=other_period,
            data_value=200.0,
        )

        delete_economic_data(self.indicator.name)

        result = get_economic_data(indicator_names=[self.indicator.name])
        result_dict = convert_query_to_dictionary_list(result)
        assert result_dict == []
