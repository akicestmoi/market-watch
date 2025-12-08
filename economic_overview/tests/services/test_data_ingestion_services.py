from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from core.services import convert_query_to_dictionary_list
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.data_ingestion_services import (
    ingest_economic_data,
    ingest_specific_economic_data,
)


def _scraper_side_effect(ticker, period):
    if ticker == "TEST":
        return {"period": date(2024, 1, 15), "data_value": 100.0, "comment": ""}
    return {"period": None, "data_value": None, "comment": "No data"}


def _scraper_multiple_periods_side_effect(ticker, period):
    if period == "2024-01":
        return {"period": date(2024, 1, 15), "data_value": 100.0, "comment": ""}
    return {"period": date(2024, 2, 15), "data_value": 200.0, "comment": ""}


class TestDataIngestionServices(TestCase):
    """Test cases for data_ingestion_services functions."""

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
            ticker="TEST",
        )
        self.target_period = "2024-01"

    @patch(
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_economic_data_success(self, mock_source_scrap_map):
        """
        GIVEN an indicator with a successful scraper
        WHEN ingesting economic data
        THEN the data is successfully ingested
        """
        mock_scraper = Mock(
            return_value={
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        )
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_economic_data([self.indicator])

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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_economic_data_no_value(self, mock_source_scrap_map):
        """
        GIVEN an indicator with a scraper that returns no value
        WHEN ingesting economic data
        THEN the indicator is listed as not updated
        """
        mock_scraper = Mock(
            return_value={"period": None, "data_value": None, "comment": "No data"}
        )
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_economic_data([self.indicator])

        assert result == [self.indicator.name]
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
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
            category=EconomicDataCategoryChoices.GROWTH,
            type="Other test Indicator",
            name="Other test Indicator Name",
            technical_name="other_test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="OTHER_TEST",
        )

        mock_scraper = Mock(side_effect=_scraper_side_effect)
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_economic_data([self.indicator, other_indicator])

        assert result == [other_indicator.name]
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_success(self, mock_source_scrap_map):
        """
        GIVEN an indicator and specific periods
        WHEN ingesting specific economic data
        THEN the data for those periods is ingested
        """
        mock_scraper = Mock(
            return_value={
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        )
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_ingest_specific_economic_data_no_value(self, mock_source_scrap_map):
        """
        GIVEN an indicator and specific periods with no value
        WHEN ingesting specific economic data
        THEN the indicator and period are listed as not updated
        """
        mock_scraper = Mock(
            return_value={"period": None, "data_value": None, "comment": "No data"}
        )
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_specific_economic_data(
            [self.indicator], periods=[[self.target_period]]
        )

        assert result == [
            {
                "indicator": self.indicator.name,
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
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

        mock_scraper = Mock(side_effect=_scraper_multiple_periods_side_effect)
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
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

        mock_scraper = Mock(
            return_value={
                "period": date(2024, 1, 15),
                "data_value": None,
                "comment": "No data",
            }
        )
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        result = ingest_specific_economic_data([self.indicator], periods=[[period]])

        assert result == [{"indicator": self.indicator.name, "period": period}]
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
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
            category=EconomicDataCategoryChoices.GROWTH,
            type="Test Indicator 3",
            name="Test Indicator Name 3",
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
                "indicator": indicator_no_source.name,
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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
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
        mock_scraper = Mock(
            return_value={
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        )
        mock_source_scrap_map[EconomicDataSourceChoices.INSEE] = mock_scraper

        ingest_economic_data([self.indicator])

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
        "economic_overview.services.data_ingestion_services.SOURCE_SCRAP_MAP",
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
        mock_scraper = Mock(
            return_value={
                "period": date(2024, 1, 15),
                "data_value": 100.0,
                "comment": "",
            }
        )
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
