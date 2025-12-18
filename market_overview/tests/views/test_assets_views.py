from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)


class TestAssetsViews(TestCase):
    """Test cases for Assets Views."""

    GENERATE_BASE_ASSETS_URL = "/generate-base-assets-data"
    GET_ASSET_NAMES_URL = "/get-asset-names"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/markets/asset"
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

    @patch("json.load")
    @patch("builtins.open")
    def test_generate_base_assets_data_success(self, mock_open, mock_json_load):
        """
        GIVEN a valid JSON file
        WHEN the generate base assets data view is called
        THEN new data should be added without deleting the existing data
        """
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_json_load.return_value = [
            {
                "id": 2,
                "short_name": "NEW_TEST",
                "full_name": "Test Asset",
                "asset_class": "STOCKS",
                "asset_type": "EQUITY",
            }
        ]

        response = self.client.post(f"{self.base_url}{self.GENERATE_BASE_ASSETS_URL}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Asset data successfully generated."}
        assert AssetModel.objects.filter(short_name="NEW_TEST").exists()
        assert AssetModel.objects.filter(short_name="TEST").exists()

    @patch("builtins.open")
    @patch("json.load")
    def test_generate_base_assets_data_update_existing_asset(
        self, mock_json_load, mock_open
    ):
        """
        GIVEN an existing in database
        WHEN asset generation is called for an asset with the same short_name
        THEN the existing asset should be updated regardless of other fields
        """
        mock_json_load.return_value = [
            {
                "id": 2,
                "short_name": "TEST",
                "full_name": "Updated Asset",
                "asset_class": "STOCKS",
                "asset_type": "EQUITY",
            }
        ]
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        response = self.client.post(f"{self.base_url}{self.GENERATE_BASE_ASSETS_URL}")

        assert response.status_code == status.HTTP_200_OK
        assert AssetModel.objects.count() == 1
        asset = AssetModel.objects.get(short_name="TEST")
        assert asset.asset_id == 2
        assert asset.full_name == "Updated Asset"

    @patch("builtins.open")
    @patch("json.load")
    def test_generate_base_assets_data_empty_array(self, mock_json_load, mock_open):
        """
        GIVEN an empty JSON array
        WHEN the generate base assets data view is called
        THEN the base assets data should be empty
        """
        self.asset.delete()
        mock_json_load.return_value = []
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        response = self.client.post(f"{self.base_url}{self.GENERATE_BASE_ASSETS_URL}")

        assert response.status_code == status.HTTP_200_OK
        assert AssetModel.objects.count() == 0

    @patch("builtins.open")
    @patch("json.load")
    def test_generate_base_assets_data_cannot_duplicate_asset_short_name(
        self, mock_json_load, mock_open
    ):
        """
        GIVEN an existing asset in database
        WHEN asset generation is called for an asset with the same short_name
        THEN an error should be raised
        """
        mock_json_load.return_value = [
            {
                "id": 1,
                "short_name": "TEST",
                "full_name": "Updated Asset",
                "asset_class": "STOCKS",
                "asset_type": "EQUITY",
            },
            {
                "id": 2,
                "short_name": "TEST",
                "full_name": "Duplicated Asset",
                "asset_class": "STOCKS",
                "asset_type": "EQUITY",
            },
        ]
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        response = self.client.post(f"{self.base_url}{self.GENERATE_BASE_ASSETS_URL}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": "Duplicate asset short_name found: ['TEST']"
        }

    @patch("builtins.open")
    @patch("json.load")
    def test_generate_base_assets_data_missing_required_fields(
        self, mock_json_load, mock_open
    ):
        """
        GIVEN a JSON file with missing required fields (short_name)
        WHEN the generate base assets data view is called
        THEN an error should be raised
        """
        mock_json_load.return_value = [
            {
                "id": 1,
            }
        ]
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        response = self.client.post(f"{self.base_url}{self.GENERATE_BASE_ASSETS_URL}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"error_message": "short_name is required"}

    def test_get_asset_names_success(self):
        """
        GIVEN existing assets in database
        WHEN the get asset names view is called
        THEN the asset names should be returned
        """
        response = self.client.get(f"{self.base_url}{self.GET_ASSET_NAMES_URL}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "full_name": "Test Asset",
                "short_name": "TEST",
            }
        ]

    def test_get_asset_names_with_filters(self):
        """
        GIVEN existing assets in database
        WHEN the get asset names view is called with filters
        THEN only filtered asset names should be returned
        """
        AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=LocationChoices.US,
        )
        response = self.client.get(
            f"{self.base_url}{self.GET_ASSET_NAMES_URL}",
            {
                "asset_class": AssetClassChoices.RATES,
                "asset_type": AssetTypeChoices.GOVERNMENT_BOND_RATE,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "full_name": "Test Asset 2",
                "short_name": "TEST2",
            }
        ]

    def test_get_asset_names_with_non_existent_filter(self):
        """
        GIVEN non-existent filter values
        WHEN the get asset names view is called
        THEN an empty result should be returned
        """
        response = self.client.get(
            f"{self.base_url}{self.GET_ASSET_NAMES_URL}",
            {"asset_class": AssetClassChoices.CRYPTO},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_asset_names_ordering(self):
        """
        GIVEN existing assets in database
        WHEN the get asset names view is called
        THEN the asset names should be ordered by asset_id
        """
        AssetModel.objects.create(
            short_name="TEST3",
            full_name="Test Asset 3",
            asset_id=3,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

        response = self.client.get(f"{self.base_url}{self.GET_ASSET_NAMES_URL}")
        response_data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert len(response_data) == 3
        assert [asset["short_name"] for asset in response_data] == [
            "TEST",
            "TEST2",
            "TEST3",
        ]

    def test_get_asset_details_success(self):
        """
        GIVEN an existing asset in database
        WHEN the get asset details view is called
        THEN the asset details should be returned
        """
        params = {
            "short_name": "TEST",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "asset_class": "STOCKS",
            "asset_id": 1,
            "asset_type": "EQUITY_INDEX",
            "full_name": "Test Asset",
            "location": None,
            "maturity": None,
            "short_name": "TEST",
            "source": "",
            "ticker": "",
        }

    def test_get_asset_details_not_found(self):
        """
        GIVEN a non-existent asset
        WHEN the get asset details view is called
        THEN a 404 Not Found error should be returned
        """
        params = {
            "short_name": "NONEXISTENT",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.json()["message"]
            == "No AssetModel found matching {'short_name': 'NONEXISTENT'}"
        )

    def test_delete_asset_success(self):
        """
        GIVEN an existing asset in database
        WHEN the delete asset view is called
        THEN the asset should be deleted
        """
        query_params = "short_name=TEST"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert not AssetModel.objects.filter(short_name="TEST").exists()

    def test_delete_asset_not_found(self):
        """
        GIVEN a non-existent asset
        WHEN the delete asset view is called
        THEN a 404 Not Found error should be returned
        """
        query_params = "short_name=NONEXISTENT"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.json()["message"]
            == "No AssetModel found matching {'short_name': 'NONEXISTENT'}"
        )

    def test_get_asset_details_missing_short_name(self):
        """
        GIVEN a missing short_name parameter
        WHEN the get asset details view is called
        THEN a 400 Bad Request error should be returned
        """
        response = self.client.get(f"{self.base_url}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_message"] == {
            "short_name": ["This field is required."]
        }

    def test_delete_asset_with_related_market_price(self):
        """
        GIVEN an asset with related MarketPriceModel
        WHEN the delete asset view is called
        THEN all related MarketPriceModel should be deleted along with the asset
        """
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=date.today(),
            price=100.0,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=date.today() - timedelta(days=1),
            price=110.0,
        )

        response = self.client.delete(f"{self.base_url}?short_name=TEST")

        assert response.status_code == status.HTTP_200_OK
        assert not AssetModel.objects.filter(short_name="TEST").exists()
        assert MarketPriceModel.objects.filter(asset__short_name="TEST").count() == 0
