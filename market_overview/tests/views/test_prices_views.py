from datetime import date, timedelta
from io import BytesIO
from typing import List
from unittest.mock import patch

from django.test import TestCase
from pandas.tseries.offsets import BDay
from rest_framework import status
from rest_framework.test import APIClient

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
    PriceUpdateLogModel,
    SpecialComment,
)
from market_overview.services.market_data_services import BulkUpdateAssetsPricesItem
from market_overview.services.price_ingestion_services import MarketData


class TestMarketPricesIngestionViews(TestCase):
    """Test cases for Market Prices Ingestion Views."""

    INGEST_MARKET_PRICES_URL = "/ingest"
    INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL = "/batch-ingest"

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
        self.start_date = date.today() - timedelta(days=30)
        self.end_date = date.today()
        self.price_date = date.today() - timedelta(days=1)

    @patch("market_overview.services.price_ingestion_services.get_market_data")
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_market_prices_success(self, mock_ingest, mock_get_market_data):
        """
        GIVEN a valid date
        WHEN ingesting market prices
        THEN the market prices are successfully ingested
        """
        mock_get_market_data.return_value = []
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_MARKET_PRICES_URL}",
            {"date": self.price_date.isoformat()},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Market prices successfully ingested",
            "asset_not_updated": [],
            "date": self.price_date.isoformat(),
        }
        mock_get_market_data.assert_called_once_with(self.price_date)
        mock_ingest.assert_called_once()

    def test_ingest_market_prices_missing_date(self):
        """
        GIVEN a request without a date parameter
        WHEN ingesting market prices
        THEN a 400 Bad Request error is returned
        """
        response = self.client.post(f"{self.base_url}{self.INGEST_MARKET_PRICES_URL}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]},
        }

    @patch("market_overview.services.price_ingestion_services.get_market_data")
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_market_prices_partial_success(
        self, mock_ingest, mock_get_market_data
    ):
        """
        GIVEN market data where some assets have prices and some do not
        WHEN ingesting market prices
        THEN the assets with prices are updated and assets without prices
        are listed in asset_not_updated
        """

        asset_without_price = AssetModel.objects.create(
            short_name="ASSET_WITHOUT_PRICE",
            full_name="Asset without price",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

        mock_get_market_data.return_value = [
            MarketData(asset=self.asset, price=100.0, date=self.price_date, comment=""),
            MarketData(
                asset=asset_without_price,
                price=None,
                date=self.price_date,
                comment="No price",
            ),
        ]
        mock_ingest.return_value = [
            MarketData(
                asset=asset_without_price,
                price=None,
                date=self.price_date,
                comment="No price",
            )
        ]

        response = self.client.post(
            f"{self.base_url}{self.INGEST_MARKET_PRICES_URL}",
            {"date": self.price_date.isoformat()},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Market prices successfully ingested",
            "asset_not_updated": ["ASSET_WITHOUT_PRICE"],
            "date": self.price_date.isoformat(),
        }

    def test_ingest_market_prices_invalid_date_format(self):
        """
        GIVEN a request with an invalid date format
        WHEN ingesting market prices
        THEN a 400 Bad Request error is returned
        """
        response = self.client.post(
            f"{self.base_url}{self.INGEST_MARKET_PRICES_URL}",
            {"date": "invalid-date"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "date": [
                    "Date has wrong format. Use one of these formats instead: YYYY-MM-DD."
                ]
            },
        }

    @patch(
        "market_overview.services.price_ingestion_services._get_specific_asset_market_data"
    )
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_specific_asset_prices_success(self, mock_ingest, mock_get_data):
        """
        GIVEN a valid asset short name and date range
        WHEN ingesting specific asset market prices
        THEN the asset prices are successfully ingested
        """
        mock_get_data.return_value = []
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Asset prices ingestion completed",
            "results": [
                {
                    "short_name": "TEST",
                    "status": "success",
                    "error": None,
                    "asset_not_updated": [],
                }
            ],
        }

    def test_ingest_specific_asset_prices_asset_not_found(self):
        """
        GIVEN a non-existent asset short name
        WHEN ingesting specific asset market prices
        THEN a 201 Created response is returned with error status in results
        """
        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "NONEXISTENT",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Asset prices ingestion completed",
            "results": [
                {
                    "short_name": "NONEXISTENT",
                    "status": "error",
                    "error": "Asset: NONEXISTENT does not exist in database.",
                    "asset_not_updated": None,
                }
            ],
        }

    @patch(
        "market_overview.services.price_ingestion_services._get_specific_asset_market_data"
    )
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_specific_asset_prices_start_date_after_end_date(
        self, mock_get_data, mock_ingest
    ):
        """
        GIVEN a start date that is after the end date
        WHEN ingesting specific asset market prices
        THEN a 400 Bad Request error is returned
        """
        mock_get_data.return_value = []
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                    "start_date": self.end_date.isoformat(),
                    "end_date": self.start_date.isoformat(),
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": [
                {
                    "non_field_errors": [
                        "end_date must be greater than or equal to start_date."
                    ],
                }
            ],
        }

    def test_ingest_specific_asset_prices_missing_parameters(self):
        """
        GIVEN a request without required date parameters
        WHEN ingesting specific asset market prices
        THEN a 400 Bad Request error is returned
        """
        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": [
                {
                    "start_date": [
                        "This field is required.",
                    ],
                }
            ],
        }

    @patch(
        "market_overview.services.price_ingestion_services._get_specific_asset_market_data"
    )
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_specific_asset_prices_with_asset_not_updated(
        self, mock_ingest, mock_get_data
    ):
        """
        GIVEN market data where some dates have prices and some do not
        WHEN ingesting specific asset market prices
        THEN the dates without prices are listed in asset_not_updated
        """
        mock_get_data.return_value = [
            MarketData(
                asset=self.asset, price=None, date=self.start_date, comment="No price"
            ),
            MarketData(
                asset=self.asset,
                price=100.0,
                date=self.start_date + timedelta(days=1),
                comment="",
            ),
        ]
        mock_ingest.return_value = [
            MarketData(
                asset=self.asset, price=None, date=self.start_date, comment="No price"
            )
        ]

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Asset prices ingestion completed",
            "results": [
                {
                    "short_name": "TEST",
                    "status": "success",
                    "error": None,
                    "asset_not_updated": [self.start_date.isoformat()],
                }
            ],
        }

    @patch(
        "market_overview.services.price_ingestion_services._get_specific_asset_market_data"
    )
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_specific_asset_prices_multiple_assets(
        self, mock_ingest, mock_get_data
    ):
        """
        GIVEN multiple valid assets with date ranges
        WHEN ingesting specific asset market prices
        THEN all asset prices are successfully ingested
        """
        asset2 = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

        def mock_get_data_side_effect(short_name, start_date, end_date):
            if short_name == "TEST":
                return [
                    MarketData(
                        asset=self.asset,
                        price=100.0,
                        date=start_date,
                        comment="",
                    )
                ]
            else:
                return [
                    MarketData(
                        asset=asset2,
                        price=200.0,
                        date=start_date,
                        comment="",
                    )
                ]

        mock_get_data.side_effect = mock_get_data_side_effect
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                },
                {
                    "short_name": "TEST2",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                },
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Asset prices ingestion completed",
            "results": [
                {
                    "short_name": "TEST",
                    "status": "success",
                    "error": None,
                    "asset_not_updated": [],
                },
                {
                    "short_name": "TEST2",
                    "status": "success",
                    "error": None,
                    "asset_not_updated": [],
                },
            ],
        }
        assert mock_get_data.call_count == 2

    @patch(
        "market_overview.services.price_ingestion_services._get_specific_asset_market_data"
    )
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_specific_asset_prices_partial_failure(
        self, mock_ingest, mock_get_data
    ):
        """
        GIVEN multiple assets where one exists and one doesn't
        WHEN ingesting specific asset market prices
        THEN the existing asset is processed and the non-existent one returns an error
        """
        mock_get_data.return_value = []
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                },
                {
                    "short_name": "NONEXISTENT",
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                },
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Asset prices ingestion completed",
            "results": [
                {
                    "short_name": "TEST",
                    "status": "success",
                    "error": None,
                    "asset_not_updated": [],
                },
                {
                    "short_name": "NONEXISTENT",
                    "status": "error",
                    "error": "Asset: NONEXISTENT does not exist in database.",
                    "asset_not_updated": None,
                },
            ],
        }

    @patch(
        "market_overview.services.price_ingestion_services._get_specific_asset_market_data"
    )
    @patch("market_overview.services.price_ingestion_services.ingest_market_data")
    def test_ingest_specific_asset_prices_without_end_date(
        self, mock_ingest, mock_get_data
    ):
        """
        GIVEN a valid asset with only start_date (no end_date)
        WHEN ingesting specific asset market prices
        THEN the asset price is ingested for the start_date only
        """
        mock_get_data.return_value = [
            MarketData(
                asset=self.asset,
                price=100.0,
                date=self.start_date,
                comment="",
            )
        ]
        mock_ingest.return_value = []

        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [
                {
                    "short_name": "TEST",
                    "start_date": self.start_date.isoformat(),
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "message": "Asset prices ingestion completed",
            "results": [
                {
                    "short_name": "TEST",
                    "status": "success",
                    "error": None,
                    "asset_not_updated": [],
                }
            ],
        }
        mock_get_data.assert_called_once()
        call_args = mock_get_data.call_args
        assert call_args[0][0] == "TEST"
        assert call_args[0][1] == self.start_date
        assert call_args[0][2] == (date.today() - BDay(1)).date()

    def test_ingest_specific_asset_prices_empty_list(self):
        """
        GIVEN an empty list
        WHEN ingesting specific asset market prices
        THEN a 400 Bad Request error is returned
        """
        response = self.client.post(
            f"{self.base_url}{self.INGEST_SPECIFIC_ASSET_MARKET_PRICES_URL}",
            [],
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "non_field_errors": [
                    "List cannot be empty.",
                ],
            },
        }


class TestMarketPricesViews(TestCase):
    """Test cases for Market Prices Views."""

    LIST_MARKET_PRICES_URL = "/list-all"
    GET_ASSETS_WITHOUT_PRICES_URL = "/get-assets-without-prices"
    BULK_UPDATE_ASSETS_PRICES_URL = "/bulk-update"
    BULK_UPDATE_ASSETS_PRICES_FROM_CSV_URL = "/bulk-update-from-csv"

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
        self.price_date = date(2025, 11, 14)
        self.previous_date = date(2025, 11, 13)
        self.location = LocationChoices.US
        self.reference_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.price_date,
            price=100.0,
        )
        self.previous_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.previous_date,
            price=90.0,
        )

    def test_get_market_price_success(self):
        """
        GIVEN a market price that exists for an asset and date
        WHEN getting the market price
        THEN the market price is returned
        """
        params = {
            "date": self.price_date.isoformat(),
            "short_name": "TEST",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "comment": "",
            "date": self.price_date.isoformat(),
            "price": 100.0,
            "asset": {
                "asset_class": "STOCKS",
                "asset_id": 1,
                "asset_type": "EQUITY_INDEX",
                "full_name": "Test Asset",
                "location": None,
                "maturity": None,
                "short_name": "TEST",
                "source": "",
                "ticker": "",
            },
        }

    def test_get_market_price_not_found(self):
        """
        GIVEN an asset that does not exist
        WHEN getting its market price
        THEN a 404 Not Found error is returned
        """
        params = {
            "date": self.price_date.isoformat(),
            "short_name": "NONEXISTENT",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_market_price_missing_parameters(self):
        """
        GIVEN an asset and price
        WHEN getting its market price without parameters
        THEN a 400 Bad Request error is returned
        """
        params = {
            "short_name": "TEST",
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]}
        }

        params = {
            "date": self.price_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"short_name": ["This field is required."]}
        }

        response = self.client.get(f"{self.base_url}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "short_name": ["This field is required."],
                "date": ["This field is required."],
            }
        }

    def test_list_market_prices_success(self):
        """
        GIVEN a market price that exists for an asset and date
        WHEN listing the market prices
        THEN the market prices are returned
        """
        params = {
            "date": self.price_date.isoformat(),
        }
        response = self.client.get(
            f"{self.base_url}{self.LIST_MARKET_PRICES_URL}", params
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "comment": "",
                "date": self.price_date.isoformat(),
                "price": 100.0,
                "asset": {
                    "asset_class": "STOCKS",
                    "asset_id": 1,
                    "asset_type": "EQUITY_INDEX",
                    "full_name": "Test Asset",
                    "location": None,
                    "maturity": None,
                    "short_name": "TEST",
                    "source": "",
                    "ticker": "",
                },
            }
        ]

    def test_list_market_prices_empty(self):
        """
        GIVEN a date that has no market prices
        WHEN listing the market prices
        THEN an empty list is returned
        """
        params = {
            "date": (self.price_date + timedelta(days=1)).isoformat(),
        }
        response = self.client.get(
            f"{self.base_url}{self.LIST_MARKET_PRICES_URL}", params
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_market_prices_missing_date(self):
        """
        GIVEN an asset and price
        WHEN listing the market prices without a date parameter
        THEN a 400 Bad Request error is returned
        """
        params = {
            "short_name": "TEST",
        }
        response = self.client.get(
            f"{self.base_url}{self.LIST_MARKET_PRICES_URL}", params
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {"date": ["This field is required."]}
        }

    def test_list_market_prices_multiple_assets(self):
        """
        GIVEN a date that has multiple prices
        WHEN listing the market prices
        THEN all market prices for the date are returned
        """
        asset2 = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        MarketPriceModel.objects.create(
            asset=asset2,
            date=self.price_date,
            price=200.0,
        )

        params = {
            "date": self.price_date.isoformat(),
        }
        response = self.client.get(
            f"{self.base_url}{self.LIST_MARKET_PRICES_URL}", params
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "comment": "",
                "date": self.price_date.isoformat(),
                "price": 100.0,
                "asset": {
                    "asset_class": "STOCKS",
                    "asset_id": 1,
                    "asset_type": "EQUITY_INDEX",
                    "full_name": "Test Asset",
                    "location": None,
                    "maturity": None,
                    "short_name": "TEST",
                    "source": "",
                    "ticker": "",
                },
            },
            {
                "comment": "",
                "date": self.price_date.isoformat(),
                "price": 200.0,
                "asset": {
                    "asset_class": "STOCKS",
                    "asset_id": 2,
                    "asset_type": "EQUITY_INDEX",
                    "full_name": "Test Asset 2",
                    "location": None,
                    "maturity": None,
                    "short_name": "TEST2",
                    "source": "",
                    "ticker": "",
                },
            },
        ]

    def test_get_assets_without_prices_success(self):
        """
        GIVEN an asset with a price date that has no prices
        WHEN getting the assets without prices
        THEN the asset is returned
        """
        none_price_date = self.price_date - timedelta(days=5)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date,
            price=None,
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": none_price_date.isoformat(),
                "comment": "",
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
            }
        ]

    def test_get_assets_without_prices_with_date_filter(self):
        """
        GIVEN assets without prices on different dates
        WHEN getting the assets without prices with start_date and end_date filters
        THEN only assets within the date range are returned
        """
        none_price_date_1 = self.price_date - timedelta(days=5)
        none_price_date_2 = none_price_date_1 + timedelta(days=1)
        none_price_date_3 = none_price_date_1 + timedelta(days=3)

        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_1,
            price=None,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_2,
            price=None,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_3,
            price=None,
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}?start_date={none_price_date_1.isoformat()}&end_date={none_price_date_2.isoformat()}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": none_price_date_2.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            },
            {
                "date": none_price_date_1.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            },
        ]

    def test_get_assets_without_prices_excludes_holidays_by_default(self):
        """
        GIVEN assets without prices including bank holidays
        WHEN getting the assets without prices without include_holidays parameter
        THEN bank holidays are excluded from results
        """
        none_price_date = self.price_date - timedelta(days=5)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date + timedelta(days=1),
            price=None,
            comment="",
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": (none_price_date + timedelta(days=1)).isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            }
        ]

    def test_get_assets_without_prices_includes_holidays_when_requested(self):
        """
        GIVEN assets without prices including bank holidays
        WHEN getting the assets without prices with include_holidays=True
        THEN bank holidays are included in results
        """
        none_price_date = self.price_date - timedelta(days=5)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date + timedelta(days=1),
            price=None,
            comment="",
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}?include_holidays=true"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": (none_price_date + timedelta(days=1)).isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            },
            {
                "date": none_price_date.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": SpecialComment.BANK_HOLIDAY,
            },
        ]

    def test_get_assets_without_prices_with_start_date_only(self):
        """
        GIVEN assets without prices on different dates
        WHEN getting the assets without prices with only start_date
        THEN only assets on or after start_date are returned
        """
        none_price_date_1 = self.price_date - timedelta(days=5)
        none_price_date_2 = none_price_date_1 + timedelta(days=3)

        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_1,
            price=None,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_2,
            price=None,
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}?start_date={(none_price_date_1 + timedelta(days=1)).isoformat()}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": none_price_date_2.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            }
        ]

    def test_get_assets_without_prices_with_end_date_only(self):
        """
        GIVEN assets without prices on different dates
        WHEN getting the assets without prices with only end_date
        THEN only assets on or before end_date are returned
        """
        none_price_date_1 = self.price_date - timedelta(days=5)
        none_price_date_2 = none_price_date_1 + timedelta(days=3)

        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_1,
            price=None,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_2,
            price=None,
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}?end_date={(none_price_date_1 + timedelta(days=1)).isoformat()}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": none_price_date_1.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            }
        ]

    def test_get_assets_without_prices_with_combined_filters(self):
        """
        GIVEN assets without prices on different dates including holidays
        WHEN getting the assets without prices with all filters
        THEN only assets matching all criteria are returned
        """
        none_price_date_1 = self.price_date - timedelta(days=5)
        none_price_date_2 = none_price_date_1 + timedelta(days=1)
        none_price_date_3 = none_price_date_1 + timedelta(days=3)

        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_1,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_2,
            price=None,
            comment="",
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=none_price_date_3,
            price=None,
            comment="",
        )

        response = self.client.get(
            f"{self.base_url}{self.GET_ASSETS_WITHOUT_PRICES_URL}?start_date={none_price_date_1.isoformat()}&end_date={none_price_date_2.isoformat()}&include_holidays=true"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "date": none_price_date_2.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": "",
            },
            {
                "date": none_price_date_1.isoformat(),
                "short_name": "TEST",
                "full_name": "Test Asset",
                "maturity": None,
                "comment": SpecialComment.BANK_HOLIDAY,
            },
        ]

    def test_bulk_update_assets_prices_success(self):
        """
        GIVEN a list of updates
        WHEN bulk updating the assets prices
        THEN the prices are updated
        """
        updates: List[BulkUpdateAssetsPricesItem] = [
            {
                "date": self.price_date,
                "short_name": "TEST",
                "price": 150.0,
                "logs": "Test update",
            }
        ]

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "asset": {
                    "asset_class": "STOCKS",
                    "asset_id": 1,
                    "asset_type": "EQUITY_INDEX",
                    "full_name": "Test Asset",
                    "location": None,
                    "maturity": None,
                    "short_name": "TEST",
                    "source": "",
                    "ticker": "",
                },
                "comment": "",
                "date": self.price_date.isoformat(),
                "price": 150.0,
            },
        ]
        updated_price = MarketPriceModel.objects.get(
            asset=self.asset, date=self.price_date
        )
        assert updated_price.price == 150.0

    def test_bulk_update_assets_prices_empty_list(self):
        """
        GIVEN an empty list of updates
        WHEN bulk updating the assets prices
        THEN an empty list is returned
        """
        updates: List[BulkUpdateAssetsPricesItem] = []

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_bulk_update_assets_prices_nonexistent_asset(self):
        """
        GIVEN a list of updates for a nonexistent asset
        WHEN bulk updating the assets prices
        THEN a 404 Not Found error is returned
        """
        updates: List[BulkUpdateAssetsPricesItem] = [
            {
                "date": self.price_date,
                "short_name": "NONEXISTENT",
                "price": 150.0,
                "logs": "Test update",
            }
        ]

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["message"].startswith(
            "No MarketPriceModel found matching {'date':"
        )

    def test_bulk_update_assets_prices_nonexistent_market_price(self):
        """
        GIVEN a list of updates for a nonexistent market price (date + asset combination)
        WHEN bulk updating the assets prices
        THEN a 404 Not Found error is returned
        """
        updates: List[BulkUpdateAssetsPricesItem] = [
            {
                "date": self.price_date + timedelta(days=1),
                "short_name": "TEST",
                "price": 150.0,
                "logs": "Test update",
            }
        ]

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["message"].startswith(
            "No MarketPriceModel found matching {'date':"
        )

    def test_bulk_cannot_update_existing_prices_to_none(self):
        """
        GIVEN non-null existing price
        WHEN bulk updating the assets prices to None
        THEN a 400 Bad Request error is returned
        """
        updates: List[dict] = [
            {
                "date": self.price_date,
                "short_name": "TEST",
                "price": None,
                "logs": "Test update",
            }
        ]
        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": [
                {
                    "price": [
                        "This field may not be null.",
                    ],
                },
            ],
        }

    def test_bulk_update_assets_prices_with_default_logs(self):
        """
        GIVEN a list of updates with no logs
        WHEN bulk updating the assets prices
        THEN a log is created with the default message
        """
        updates: List[dict] = [
            {
                "date": self.price_date,
                "short_name": "TEST",
                "price": 150.0,
            }
        ]

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        log = PriceUpdateLogModel.objects.get(
            market_price__asset=self.asset, market_price__date=self.price_date
        )
        assert (
            log.logs
            == "Bulk update of assets prices. Updated price from 100.0 to 150.0."
        )

    def test_bulk_update_assets_prices_with_custom_logs(self):
        """
        GIVEN a list of updates with a custom logs message
        WHEN bulk updating the assets prices
        THEN a log is created with the custom message
        """
        updates: List[BulkUpdateAssetsPricesItem] = [
            {
                "date": self.price_date,
                "short_name": "TEST",
                "price": 150.0,
                "logs": "Custom log message",
            }
        ]

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            data=updates,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        log = PriceUpdateLogModel.objects.get(
            market_price__asset=self.asset, market_price__date=self.price_date
        )
        assert log.logs == "Custom log message Updated price from 100.0 to 150.0."

    def test_bulk_update_assets_prices_multiple_updates(self):
        """
        GIVEN a list of updates on different dates and different assets
        WHEN bulk updating the assets prices
        THEN all prices are correctlyupdated
        """
        second_asset = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=self.price_date,
            price=100.0,
        )

        updates: List[BulkUpdateAssetsPricesItem] = [
            {
                "date": self.price_date,
                "short_name": "TEST",
                "price": 150.0,
                "logs": "Update 1",
            },
            {
                "date": self.previous_date,
                "short_name": "TEST",
                "price": 200.0,
                "logs": "Update 2",
            },
            {
                "date": self.price_date,
                "short_name": "TEST2",
                "price": 80.0,
                "logs": "Update 3",
            },
        ]

        response = self.client.patch(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_URL}",
            updates,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3
        assert (
            MarketPriceModel.objects.get(asset=self.asset, date=self.price_date).price
            == 150.0
        )
        assert (
            MarketPriceModel.objects.get(
                asset=self.asset, date=self.previous_date
            ).price
            == 200.0
        )
        assert (
            MarketPriceModel.objects.get(asset=second_asset, date=self.price_date).price
            == 80.0
        )

    def test_csv_bulk_update_success(self):
        """
        GIVEN a CSV file with a list of updates
        WHEN bulk updating the assets prices from the CSV file
        THEN the prices are correctly updated
        """
        csv_content = "date,short_name,price,logs\n"
        csv_content += f"{self.price_date.isoformat()},TEST,200.0,CSV update\n"
        csv_file = BytesIO(csv_content.encode("utf-8"))

        response = self.client.post(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_FROM_CSV_URL}",
            {"csv_file": csv_file},
            format="multipart",
        )
        assert response.status_code == status.HTTP_200_OK
        updated_price = MarketPriceModel.objects.get(
            asset=self.asset, date=self.price_date
        )
        assert updated_price.price == 200.0

    def test_csv_bulk_update_invalid_format(self):
        """
        GIVEN a CSV file with an invalid format
        WHEN bulk updating the assets prices from the CSV file
        THEN a 400 Bad Request error is returned
        """
        csv_content = "invalid,columns\n"
        csv_content += f"{self.price_date.isoformat()},TEST\n"
        csv_file = BytesIO(csv_content.encode("utf-8"))

        response = self.client.post(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_FROM_CSV_URL}",
            {"csv_file": csv_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.json().get("detail", {}).get("exception")
            == "CSV file must have the following columns: date, logs, price, short_name."
        )

    def test_csv_bulk_update_empty_file(self):
        """
        GIVEN an empty CSV file
        WHEN bulk updating the assets prices from the CSV file
        THEN a 400 Bad Request error is returned
        """
        csv_file = BytesIO(b"")

        response = self.client.post(
            f"{self.base_url}{self.BULK_UPDATE_ASSETS_PRICES_FROM_CSV_URL}",
            {"csv_file": csv_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error_message": {
                "csv_file": [
                    "The submitted file is empty.",
                ],
            }
        }


class TestDeleteMarketPricesView(TestCase):
    """Test cases for Delete Market Prices View."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.base_url = "/markets/prices"
        self.asset1 = AssetModel.objects.create(
            short_name="TEST1",
            full_name="Test Asset 1",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.asset2 = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.date1 = date(2025, 1, 15)
        self.date2 = date(2025, 2, 15)
        self.date3 = date(2025, 3, 15)

        # Create market prices
        self.price1 = MarketPriceModel.objects.create(
            asset=self.asset1,
            date=self.date1,
            price=100.0,
        )
        self.price2 = MarketPriceModel.objects.create(
            asset=self.asset1,
            date=self.date2,
            price=110.0,
        )
        self.price3 = MarketPriceModel.objects.create(
            asset=self.asset1,
            date=self.date3,
            price=120.0,
        )
        self.price4 = MarketPriceModel.objects.create(
            asset=self.asset2,
            date=self.date1,
            price=200.0,
        )
        self.price5 = MarketPriceModel.objects.create(
            asset=self.asset2,
            date=self.date2,
            price=210.0,
        )

    def test_delete_market_prices_by_start_date(self):
        """
        GIVEN market prices exist
        WHEN deleting prices with start_date filter
        THEN prices from that date onwards are deleted
        """
        query_params = f"start_date={self.date2.isoformat()}"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 3,
        }
        assert MarketPriceModel.objects.filter(id=self.price1.id).exists()
        assert MarketPriceModel.objects.filter(id=self.price4.id).exists()
        assert MarketPriceModel.objects.count() == 2

    def test_delete_market_prices_by_end_date(self):
        """
        GIVEN market prices exist
        WHEN deleting prices with end_date filter
        THEN prices up to that date are deleted
        """
        query_params = f"end_date={self.date2.isoformat()}"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 4,
        }
        assert MarketPriceModel.objects.filter(id=self.price3.id).exists()
        assert MarketPriceModel.objects.count() == 1

    def test_delete_market_prices_by_short_names(self):
        """
        GIVEN market prices exist for multiple assets
        WHEN deleting prices with short_names filter
        THEN prices for those assets are deleted
        """
        query_params = "short_names=TEST1"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 3,
        }
        assert MarketPriceModel.objects.filter(id=self.price4.id).exists()
        assert MarketPriceModel.objects.filter(id=self.price5.id).exists()
        assert MarketPriceModel.objects.count() == 2

    def test_delete_market_prices_by_multiple_short_names(self):
        """
        GIVEN market prices exist for multiple assets
        WHEN deleting prices with multiple short_names
        THEN prices for all specified assets are deleted
        """
        query_params = "short_names=TEST1,TEST2"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 5,
        }
        assert MarketPriceModel.objects.count() == 0

    def test_delete_market_prices_by_date_range(self):
        """
        GIVEN market prices exist
        WHEN deleting prices with start_date and end_date filters
        THEN prices within the date range are deleted
        """
        query_params = (
            f"start_date={self.date1.isoformat()}&end_date={self.date2.isoformat()}"
        )
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 4,
        }
        assert MarketPriceModel.objects.filter(id=self.price3.id).exists()
        assert MarketPriceModel.objects.count() == 1

    def test_delete_market_prices_by_all_filters(self):
        """
        GIVEN market prices exist
        WHEN deleting prices with all filters combined
        THEN prices matching all criteria are deleted
        """
        query_params = f"start_date={self.date1.isoformat()}&end_date={self.date2.isoformat()}&short_names=TEST1"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 2,
        }
        assert MarketPriceModel.objects.filter(id=self.price3.id).exists()
        assert MarketPriceModel.objects.filter(id=self.price4.id).exists()
        assert MarketPriceModel.objects.filter(id=self.price5.id).exists()
        assert MarketPriceModel.objects.count() == 3

    def test_delete_market_prices_no_parameters(self):
        """
        GIVEN a delete request
        WHEN no parameters are provided
        THEN a 400 Bad Request error is returned
        """
        response = self.client.delete(f"{self.base_url}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "At least one of" in str(response.json().get("error_message", ""))

    def test_delete_market_prices_no_matching_records(self):
        """
        GIVEN a delete request
        WHEN no prices match the criteria
        THEN 0 records are deleted and success response is returned
        """
        query_params = f"start_date={date(2026, 1, 1).isoformat()}"
        response = self.client.delete(f"{self.base_url}?{query_params}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "message": "Market prices successfully deleted.",
            "deleted_count": 0,
        }
        assert MarketPriceModel.objects.count() == 5
