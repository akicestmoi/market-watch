from datetime import date, timedelta

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    MarketPriceModel,
    PriceUpdateLogModel,
)


class TestPriceUpdateLogsViews(TestCase):
    """Test cases for Price Update Logs Views."""

    GET_PRICE_UPDATE_LOGS_URL = "/get-price-update-logs"

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/markets/prices"
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.price_date = date(2024, 1, 15)
        self.previous_date = date(2024, 1, 14)
        self.market_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.price_date,
            price=100.0,
        )
        self.log = PriceUpdateLogModel.objects.create(
            market_price=self.market_price,
            logs="First log on first market price",
        )
        PriceUpdateLogModel.objects.create(
            market_price=self.market_price,
            logs="Second log on first market price",
        )
        previous_date = self.price_date - timedelta(days=1)
        self.previous_market_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date=previous_date,
            price=100.0,
        )
        PriceUpdateLogModel.objects.create(
            market_price=self.previous_market_price,
            logs="Third log on previous market price",
        )
        self.other_asset = AssetModel.objects.create(
            short_name="OTHER_TEST",
            full_name="Test OtherAsset",
            asset_id=2,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
        )
        self.other_market_price = MarketPriceModel.objects.create(
            asset=self.other_asset,
            date=self.price_date,
            price=10.0,
        )
        PriceUpdateLogModel.objects.create(
            market_price=self.other_market_price,
            logs="Fourth log on other asset's market price",
        )

    def test_get_price_update_logs_success(self):
        """
        GIVEN existing price update logs
        WHEN the GET price update logs endpoint is called
        THEN the list of all price update logs should be returned
        """
        response = self.client.get(f"{self.base_url}{self.GET_PRICE_UPDATE_LOGS_URL}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "logs": "Fourth log on other asset's market price",
                "market_price_id": self.other_market_price.pk,
            },
            {
                "logs": "Third log on previous market price",
                "market_price_id": self.previous_market_price.pk,
            },
            {
                "logs": "Second log on first market price",
                "market_price_id": self.market_price.pk,
            },
            {
                "logs": "First log on first market price",
                "market_price_id": self.market_price.pk,
            },
        ]

    def test_get_price_update_logs_with_filters(self):
        """
        GIVEN existing price update logs
        WHEN the GET price update logs endpoint is called with filters
        THEN the list of price update logs should be returned
        """
        query_params = f"?price_date={self.price_date.isoformat()}&short_name=TEST"
        response = self.client.get(
            f"{self.base_url}{self.GET_PRICE_UPDATE_LOGS_URL}{query_params}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "logs": "Second log on first market price",
                "market_price_id": self.market_price.pk,
            },
            {
                "logs": "First log on first market price",
                "market_price_id": self.market_price.pk,
            },
        ]

    def test_get_price_update_logs_with_price_date_only(self):
        """
        GIVEN existing price update logs
        WHEN the GET price update logs endpoint is called with price_date filter only
        THEN the list of price update logs should be returned
        """
        response = self.client.get(
            f"{self.base_url}{self.GET_PRICE_UPDATE_LOGS_URL}",
            {"price_date": self.price_date.isoformat()},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "logs": "Fourth log on other asset's market price",
                "market_price_id": self.other_market_price.pk,
            },
            {
                "logs": "Second log on first market price",
                "market_price_id": self.market_price.pk,
            },
            {
                "logs": "First log on first market price",
                "market_price_id": self.market_price.pk,
            },
        ]

    def test_get_price_update_logs_with_short_name_only(self):
        """
        GIVEN existing price update logs
        WHEN the GET price update logs endpoint is called with short_name filter only
        THEN the list of price update logs should be returned
        """
        query_params = f"?short_name={self.asset.short_name}"
        response = self.client.get(
            f"{self.base_url}{self.GET_PRICE_UPDATE_LOGS_URL}{query_params}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "logs": "Third log on previous market price",
                "market_price_id": self.previous_market_price.pk,
            },
            {
                "logs": "Second log on first market price",
                "market_price_id": self.market_price.pk,
            },
            {
                "logs": "First log on first market price",
                "market_price_id": self.market_price.pk,
            },
        ]

    def test_get_price_update_logs_with_nonexistent_asset(self):
        """
        GIVEN existing price update logs
        WHEN the GET price update logs endpoint is called with a nonexistent asset
        THEN the response should be a 404 error
        """
        query_params = "?short_name=NONEXISTENT"
        response = self.client.get(
            f"{self.base_url}{self.GET_PRICE_UPDATE_LOGS_URL}{query_params}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "error_message": "Asset: NONEXISTENT does not exist in database."
        }

    def test_get_price_update_logs_filters_on_nonexistent_date(self):
        """
        GIVEN existing price update logs
        WHEN the GET price update logs endpoint is called with a nonexistent date
        THEN the response should be a 200 OK and an empty list
        """
        query_params = f"?price_date={(date.today() + timedelta(days=100)).isoformat()}&short_name={self.asset.short_name}"
        response = self.client.get(
            f"{self.base_url}{self.GET_PRICE_UPDATE_LOGS_URL}{query_params}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
