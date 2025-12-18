from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

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


class TestGenerateBaseEconomicIndicatorInformationView(TestCase):
    """Test cases for GenerateBaseEconomicIndicatorInformationView."""

    GENERATE_INDICATOR_URL = "/generate-base-information"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/economics/indicator"
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
        self.indicator_next = EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GROWTH,
            type="Second test indicator",
            name="Second test indicator name",
            technical_name="second_test_indicator_name",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565531",
        )
        self.period = date(2024, 1, 15)
        self.next_period = date(2024, 2, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.period,
            data_value=100.0,
            comment="Test comment",
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_next,
            period=self.period,
            data_value=50.0,
            comment="Second Indicator test comment",
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator,
            period=self.next_period,
            data_value=101.0,
            comment="Next period test comment",
        )

    @patch("economic_overview.views.economic_data_views.json.load")
    @patch("builtins.open")
    def test_generate_base_economic_indicator_information_success(
        self, mock_open, mock_json_load
    ):
        """
        GIVEN a valid economic_data.json file
        WHEN generating base economic indicator information
        THEN the indicators are successfully created
        """
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_json_load.return_value = [
            {
                "id": 2,
                "location": "FR",
                "category": "CONFIDENCE",
                "type": "New Test Indicator",
                "name": "New Test Indicator Name",
                "technical_name": "new_test_indicator",
                "frequency": "MONTHLY",
                "source": "INSEE",
                "ticker": "001565530",
            }
        ]

        response = self.client.post(f"{self.base_url}{self.GENERATE_INDICATOR_URL}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Economic indicator information successfully generated."
        }
        assert EconomicIndicatorInformationModel.objects.filter(
            id=2,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="New Test Indicator",
            name="New Test Indicator Name",
            technical_name="new_test_indicator",
        ).exists()
        assert PublicationScheduleModel.objects.filter(
            indicator=EconomicIndicatorInformationModel.objects.get(id=2),
            previous_publication_date=None,
            current_publication_date=None,
            next_publication_date=None,
        ).exists()

    def test_get_economic_data_detailed_no_filters(self):
        """
        GIVEN existing economic data
        WHEN getting economic data detailed without filters
        THEN all data is returned
        """
        response = self.client.get(self.base_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "indicator": {
                    "name": "Test Indicator Name",
                    "location": EconomicDataLocationChoices.FR.value,
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "type": "Test Indicator",
                    "technical_name": "test_indicator",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                    "source": EconomicDataSourceChoices.INSEE.value,
                    "ticker": "001565530",
                },
                "period": self.period.isoformat(),
                "data_value": 100.0,
                "comment": "Test comment",
            },
            {
                "indicator": {
                    "name": "Second test indicator name",
                    "location": EconomicDataLocationChoices.JP.value,
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "type": "Second test indicator",
                    "technical_name": "second_test_indicator_name",
                    "frequency": EconomicPublicationFrequencyChoices.QUARTERLY.value,
                    "source": EconomicDataSourceChoices.JP_CABINET_OFFICE.value,
                    "ticker": "001565531",
                },
                "period": self.period.isoformat(),
                "data_value": 50.0,
                "comment": "Second Indicator test comment",
            },
            {
                "indicator": {
                    "name": "Test Indicator Name",
                    "location": EconomicDataLocationChoices.FR.value,
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "type": "Test Indicator",
                    "technical_name": "test_indicator",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                    "source": EconomicDataSourceChoices.INSEE.value,
                    "ticker": "001565530",
                },
                "period": self.next_period.isoformat(),
                "data_value": 101.0,
                "comment": "Next period test comment",
            },
        ]

    def test_get_economic_data_detailed_with_indicator_names(self):
        """
        GIVEN existing economic data and indicator names
        WHEN getting economic data
        THEN the correct data is returned
        """
        params = {
            "indicator_names": self.indicator.name,
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "indicator": {
                    "name": "Test Indicator Name",
                    "location": EconomicDataLocationChoices.FR.value,
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "type": "Test Indicator",
                    "technical_name": "test_indicator",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                    "source": EconomicDataSourceChoices.INSEE.value,
                    "ticker": "001565530",
                },
                "period": self.period.isoformat(),
                "data_value": 100.0,
                "comment": "Test comment",
            },
            {
                "indicator": {
                    "name": "Test Indicator Name",
                    "location": EconomicDataLocationChoices.FR.value,
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "type": "Test Indicator",
                    "technical_name": "test_indicator",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                    "source": EconomicDataSourceChoices.INSEE.value,
                    "ticker": "001565530",
                },
                "period": self.next_period.isoformat(),
                "data_value": 101.0,
                "comment": "Next period test comment",
            },
        ]

    def test_get_economic_data_detailed_with_period(self):
        """
        GIVEN existing economic data and a period
        WHEN getting economic data detailed
        THEN the correct data for that period is returned
        """
        params = {
            "period": self.period.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "indicator": {
                    "name": "Test Indicator Name",
                    "location": EconomicDataLocationChoices.FR.value,
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "type": "Test Indicator",
                    "technical_name": "test_indicator",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                    "source": EconomicDataSourceChoices.INSEE.value,
                    "ticker": "001565530",
                },
                "period": self.period.isoformat(),
                "data_value": 100.0,
                "comment": "Test comment",
            },
            {
                "indicator": {
                    "name": "Second test indicator name",
                    "location": EconomicDataLocationChoices.JP.value,
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "type": "Second test indicator",
                    "technical_name": "second_test_indicator_name",
                    "frequency": EconomicPublicationFrequencyChoices.QUARTERLY.value,
                    "source": EconomicDataSourceChoices.JP_CABINET_OFFICE.value,
                    "ticker": "001565531",
                },
                "period": self.period.isoformat(),
                "data_value": 50.0,
                "comment": "Second Indicator test comment",
            },
        ]

    def test_get_economic_data_detailed_with_indicator_names_and_period(self):
        """
        GIVEN existing economic data, indicator names, and a period
        WHEN getting economic data detailed
        THEN the correct filtered data is returned
        """
        params = {
            "indicator_names": self.indicator.name,
            "period": self.period.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "indicator": {
                    "name": "Test Indicator Name",
                    "location": EconomicDataLocationChoices.FR.value,
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "type": "Test Indicator",
                    "technical_name": "test_indicator",
                    "frequency": EconomicPublicationFrequencyChoices.MONTHLY.value,
                    "source": EconomicDataSourceChoices.INSEE.value,
                    "ticker": "001565530",
                },
                "period": self.period.isoformat(),
                "data_value": 100.0,
                "comment": "Test comment",
            }
        ]

    def test_get_economic_data_detailed_indicator_not_found(self):
        """
        GIVEN non-existent indicator names
        WHEN getting economic data detailed
        THEN a 404 error is returned
        """
        params = {
            "indicator_names": "NonExistent",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_economic_data_success(self):
        """
        GIVEN existing economic data
        WHEN deleting economic data
        THEN the data is successfully deleted
        """
        response = self.client.delete(
            f"{self.base_url}?indicator_name={self.indicator.name}&period={self.period.isoformat()}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Economic data successfully deleted"}

        economic_data = EconomicDataModel.objects.filter(
            indicator=self.indicator, period=self.period
        )
        result_dict = convert_query_to_dictionary_list(economic_data)
        assert result_dict == []

    def test_delete_economic_data_indicator_not_found(self):
        """
        GIVEN non-existent indicator name
        WHEN deleting economic data
        THEN a 404 error is returned
        """
        query_params = f"indicator_name=NonExistent&period={self.period.isoformat()}"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestIngestEconomicDataView(TestCase):
    """Test cases for IngestEconomicDataView."""

    INGEST_ECONOMIC_DATA_URL = "/ingest"
    INGEST_SPECIFIC_ECONOMIC_DATA_URL = "/ingest-specific"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/economics/indicator"
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

    @patch(
        "economic_overview.services.publication_services.update_publication_schedules"
    )
    @patch("economic_overview.services.data_ingestion_services.ingest_economic_data")
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_to_update"
    )
    def test_ingest_economic_data_success(
        self, mock_get_indicators, mock_ingest, mock_update_schedules
    ):
        """
        GIVEN valid date range
        WHEN ingesting economic data
        THEN the data is successfully ingested
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []
        mock_update_schedules.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_ECONOMIC_DATA_URL}",
            {
                "start_date": (date.today() - timedelta(days=30)).isoformat(),
                "end_date": date.today().isoformat(),
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Economic data successfully ingested",
            "updated_indicators": [self.indicator.name],
            "indicator_not_updated": [],
            "schedule_not_updated": [],
        }

    @patch("economic_overview.services.data_ingestion_services.ingest_economic_data")
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_to_update"
    )
    def test_ingest_economic_data_without_update_schedule(
        self, mock_get_indicators, mock_ingest
    ):
        """
        GIVEN valid date range and update_schedule=False
        WHEN ingesting economic data
        THEN the data is ingested without updating schedules
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_ECONOMIC_DATA_URL}",
            {
                "start_date": (date.today() - timedelta(days=30)).isoformat(),
                "end_date": date.today().isoformat(),
                "update_schedule": False,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Economic data successfully ingested",
            "updated_indicators": [self.indicator.name],
            "indicator_not_updated": [],
            "schedule_not_updated": [],
        }

    @patch(
        "economic_overview.services.data_ingestion_services.ingest_specific_economic_data"
    )
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_by_names"
    )
    def test_ingest_specific_economic_data_success(
        self, mock_get_indicators, mock_ingest
    ):
        """
        GIVEN valid indicator names and periods
        WHEN ingesting specific economic data
        THEN the data is successfully ingested
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ECONOMIC_DATA_URL}",
            [
                {
                    "indicator_name": self.indicator.name,
                    "periods": ["2024-01"],
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Economic data successfully ingested",
            "indicator_not_updated": [],
        }

    def test_ingest_specific_economic_data_indicator_not_found(self):
        """
        GIVEN non-existent indicator names
        WHEN ingesting specific economic data
        THEN a 404 error is returned
        """
        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ECONOMIC_DATA_URL}",
            [
                {
                    "indicator_name": "NonExistent",
                    "periods": ["2024-01"],
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
