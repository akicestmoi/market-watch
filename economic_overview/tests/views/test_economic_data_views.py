"""Tests for economic data API views."""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

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
        economic_data = list(EconomicDataModel.objects.all().order_by("pk"))
        assert len(economic_data) == 3
        assert response.json() == [
            {
                "id": economic_data[0].pk,
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
                "id": economic_data[1].pk,
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
                "id": economic_data[2].pk,
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
        economic_data = list(
            EconomicDataModel.objects.filter(indicator=self.indicator).order_by(
                "period"
            )
        )
        assert response.json() == [
            {
                "id": economic_data[0].pk,
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
                "id": economic_data[1].pk,
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
        economic_data = list(
            EconomicDataModel.objects.filter(period=self.period).order_by("pk")
        )
        assert response.json() == [
            {
                "id": economic_data[0].pk,
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
                "id": economic_data[1].pk,
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
        economic_data = EconomicDataModel.objects.get(
            indicator=self.indicator, period=self.period
        )
        assert response.json() == [
            {
                "id": economic_data.pk,
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

    def test_delete_economic_data_no_ids(self):
        """
        GIVEN no ids provided
        WHEN deleting economic data
        THEN a 400 error is returned (ids required)
        """
        response = self.client.delete(self.base_url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_economic_data_by_ids(self):
        """
        GIVEN existing economic data
        WHEN deleting by IDs
        THEN the specified data is deleted
        """
        to_delete = list(EconomicDataModel.objects.filter(indicator=self.indicator)[:2])
        ids_str = ",".join(str(d.pk) for d in to_delete)

        response = self.client.delete(f"{self.base_url}?ids={ids_str}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Economic data successfully deleted",
            "deleted_count": 2,
        }
        for d in to_delete:
            assert not EconomicDataModel.objects.filter(pk=d.pk).exists()
        assert EconomicDataModel.objects.count() == 1

    def test_delete_economic_data_ids_with_other_parameters(self):
        """
        GIVEN IDs and other parameters
        WHEN deleting economic data
        THEN data matching ids is deleted (other params ignored)
        """
        to_delete = list(EconomicDataModel.objects.filter(indicator=self.indicator)[:2])
        ids_str = ",".join(str(d.pk) for d in to_delete)

        response = self.client.delete(
            f"{self.base_url}?ids={ids_str}&start_date=2024-01-01"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Economic data successfully deleted",
            "deleted_count": 2,
        }
        for d in to_delete:
            assert not EconomicDataModel.objects.filter(pk=d.pk).exists()


class TestIngestLatestEconomicDataView(TestCase):
    """Test cases for IngestLatestEconomicDataView."""

    INGEST_LATEST_ECONOMIC_DATA_URL = "/ingest"
    INGEST_HISTORICAL_ECONOMIC_DATA_URL = "/ingest-historical"
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
    @patch(
        "economic_overview.services.data_ingestion_services.ingest_latest_economic_data"
    )
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_by_names"
    )
    def test_ingest_latest_economic_data_success(
        self, mock_get_indicators, mock_ingest, mock_update_schedules
    ):
        """
        GIVEN seeded indicators
        WHEN ingesting latest economic data
        THEN the latest observation is ingested for each indicator
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []
        mock_update_schedules.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_LATEST_ECONOMIC_DATA_URL}",
            {},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Latest economic data successfully ingested",
            "updated_indicators": [self.indicator.name],
            "indicator_not_updated": [],
            "schedule_not_updated": [],
        }
        mock_get_indicators.assert_called_once_with()

    @patch(
        "economic_overview.services.data_ingestion_services.ingest_latest_economic_data"
    )
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_by_names"
    )
    def test_ingest_latest_economic_data_without_update_schedule(
        self, mock_get_indicators, mock_ingest
    ):
        """
        GIVEN update_schedule=False
        WHEN ingesting latest economic data
        THEN schedules are not updated
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_LATEST_ECONOMIC_DATA_URL}",
            {"update_schedule": False},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Latest economic data successfully ingested",
            "updated_indicators": [self.indicator.name],
            "indicator_not_updated": [],
            "schedule_not_updated": [],
        }

    @patch(
        "economic_overview.services.data_ingestion_services.ingest_historical_economic_data"
    )
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_by_names"
    )
    def test_ingest_historical_economic_data_success(
        self, mock_get_indicators, mock_ingest
    ):
        """
        GIVEN a date window
        WHEN ingesting historical economic data
        THEN observations in the window are ingested
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)

        response = self.client.post(
            f"{self.base_url}{self.INGEST_HISTORICAL_ECONOMIC_DATA_URL}",
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "indicators": [self.indicator.name],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Historical economic data successfully ingested",
            "updated_indicators": [self.indicator.name],
            "indicator_not_updated": [],
        }
        mock_get_indicators.assert_called_once_with(
            indicator_names=[self.indicator.name]
        )
        mock_ingest.assert_called_once_with(
            [self.indicator], start_date=start_date, end_date=end_date
        )

    @patch(
        "economic_overview.services.data_ingestion_services.ingest_historical_economic_data"
    )
    @patch(
        "economic_overview.services.economic_data_services.get_economic_indicators_by_names"
    )
    def test_ingest_historical_economic_data_all_indicators(
        self, mock_get_indicators, mock_ingest
    ):
        """
        GIVEN an empty indicators list
        WHEN ingesting historical economic data
        THEN all indicators are selected
        """
        mock_get_indicators.return_value = [self.indicator]
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_HISTORICAL_ECONOMIC_DATA_URL}",
            {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        mock_get_indicators.assert_called_once_with(indicator_names=[])

    def test_ingest_historical_economic_data_indicator_not_found(self):
        """
        GIVEN a non-existent indicator name
        WHEN ingesting historical economic data
        THEN a 404 error is returned
        """
        response = self.client.post(
            f"{self.base_url}{self.INGEST_HISTORICAL_ECONOMIC_DATA_URL}",
            {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "indicators": ["NonExistent"],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "NonExistent" in response.json()["error"]

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
