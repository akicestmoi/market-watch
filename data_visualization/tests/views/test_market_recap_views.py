import json
from datetime import date

from django.test import Client, TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)


@freeze_time("2025-12-16")
class TestMarketRecapView(TestCase):
    """Test cases for market_recap_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/market-recap/"
        self.reference_date = date(2025, 12, 15)
        self.previous_date = date(2025, 12, 12)

        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
        )
        self.reference_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.reference_date,
            price=100.0,
        )
        self.previous_price = MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.previous_date,
            price=90.0,
        )

    def test_market_recap_view_success(self):
        """
        GIVEN valid reference and previous dates with market prices
        WHEN accessing market recap view
        THEN the view renders successfully with market data
        """
        params = {
            "reference_date": self.reference_date.isoformat(),
            "previous_date": self.previous_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)
        assert response.status_code == 200
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": "US",
                                "asset": "TEST",
                                "name": "Test Asset",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": 90.0,
                                "price_change": 10.0,
                                "price_change_pct": 11.111111111111116,
                            }
                        ],
                    }
                ],
            }
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == self.reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == self.previous_date.isoformat()
        )

    def test_market_recap_view_default_dates(self):
        """
        GIVEN no date parameters
        WHEN accessing market recap view
        THEN default dates are used
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        default_reference_date = date(2025, 12, 15)
        default_previous_date = date(2025, 12, 12)
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": "US",
                                "asset": "TEST",
                                "name": "Test Asset",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": 90.0,
                                "price_change": 10.0,
                                "price_change_pct": 11.111111111111116,
                            }
                        ],
                    }
                ],
            }
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert (
            response.context.get("reference_date") == default_reference_date.isoformat()
        )
        assert (
            response.context.get("previous_date") == default_previous_date.isoformat()
        )
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == default_previous_date.isoformat()
        )

    def test_market_recap_view_future_reference_date(self):
        """
        GIVEN a reference date in the future
        WHEN accessing market recap view
        THEN an error message is displayed
        """
        future_date = date(2025, 12, 17)
        params = {
            "reference_date": future_date.isoformat(),
            "previous_date": self.previous_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == 200
        default_reference_date = date(2025, 12, 15)
        default_previous_date = date(2025, 12, 12)
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "assets": [
                            {
                                "asset": "TEST",
                                "country": "US",
                                "maturity": None,
                                "name": "Test Asset",
                                "previous_price": 90.0,
                                "price": None,
                                "price_change": None,
                                "price_change_pct": None,
                            },
                        ],
                        "location": "North America",
                    },
                ],
            },
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == future_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == default_previous_date.isoformat()
        )
        error_messages = response.context.get("error_messages")
        assert error_messages is not None
        assert json.loads(error_messages) == {
            "reference_date": "Reference date 2025-12-17 must be before today 2025-12-16.",
            "reference_market_prices": f"No data found for reference date {future_date}.",
        }

    def test_market_recap_view_reference_date_before_previous(self):
        """
        GIVEN a reference date before the previous date
        WHEN accessing market recap view
        THEN an error message is displayed
        """
        params = {
            "reference_date": self.previous_date.isoformat(),
            "previous_date": self.reference_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == 200
        default_reference_date = date(2025, 12, 15)
        default_previous_date = date(2025, 12, 12)
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "assets": [
                            {
                                "asset": "TEST",
                                "country": "US",
                                "maturity": None,
                                "name": "Test Asset",
                                "previous_price": 100.0,
                                "price": 90.0,
                                "price_change": -10.0,
                                "price_change_pct": -9.999999999999998,
                            },
                        ],
                        "location": "North America",
                    },
                ],
            },
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == self.previous_date.isoformat()
        assert response.context.get("previous_date") == self.reference_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == default_previous_date.isoformat()
        )
        error_messages = response.context.get("error_messages")
        assert error_messages is not None
        assert json.loads(error_messages) == {
            "previous_date": f"Reference date {self.previous_date} must be greater than the previous date {self.reference_date}."
        }

    def test_market_recap_view_no_reference_data(self):
        """
        GIVEN a reference date with no market prices
        WHEN accessing market recap view
        THEN an error message is displayed
        """
        self.reference_price.delete()
        params = {
            "reference_date": self.reference_date.isoformat(),
            "previous_date": self.previous_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == 200
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "assets": [
                            {
                                "asset": "TEST",
                                "country": "US",
                                "maturity": None,
                                "name": "Test Asset",
                                "previous_price": 90.0,
                                "price": None,
                                "price_change": None,
                                "price_change_pct": None,
                            },
                        ],
                        "location": "North America",
                    },
                ],
            },
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == self.reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == self.previous_date.isoformat()
        )
        error_messages = response.context.get("error_messages")
        assert error_messages is not None
        assert json.loads(error_messages) == {
            "reference_market_prices": f"No data found for reference date {self.reference_date}."
        }

    def test_market_recap_view_no_previous_data(self):
        """
        GIVEN a previous date with no market prices
        WHEN accessing market recap view
        THEN reference data is displayed with None for previous fields
        """
        self.previous_price.delete()
        params = {
            "reference_date": self.reference_date.isoformat(),
            "previous_date": self.previous_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == 200
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": "US",
                                "asset": "TEST",
                                "name": "Test Asset",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": None,
                                "price_change": None,
                                "price_change_pct": None,
                            }
                        ],
                    }
                ],
            }
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == self.reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == self.previous_date.isoformat()
        )
        error_messages = response.context.get("error_messages")
        assert error_messages is not None
        assert json.loads(error_messages) == {
            "previous_market_prices": f"No data found for reference date {self.previous_date}."
        }

    def test_market_recap_view_some_assets_no_reference_data(self):
        """
        GIVEN some assets have reference data and some don't
        WHEN accessing market recap view
        THEN all assets are correctly displayed
        """
        asset2 = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
        )
        MarketPriceModel.objects.create(
            asset=asset2,
            date=self.previous_date,
            price=85.0,
        )

        params = {
            "reference_date": self.reference_date.isoformat(),
            "previous_date": self.previous_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == 200
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": "US",
                                "asset": "TEST",
                                "name": "Test Asset",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": 90.0,
                                "price_change": 10.0,
                                "price_change_pct": 11.111111111111116,
                            },
                            {
                                "country": "US",
                                "asset": "TEST2",
                                "name": "Test Asset 2",
                                "maturity": None,
                                "price": None,
                                "previous_price": 85.0,
                                "price_change": None,
                                "price_change_pct": None,
                            },
                        ],
                    }
                ],
            }
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == self.reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == self.previous_date.isoformat()
        )

    def test_market_recap_view_some_assets_no_previous_data(self):
        """
        GIVEN some assets have previous data and some don't
        WHEN accessing market recap view
        THEN assets without previous data show with None for previous fields
        """
        asset2 = AssetModel.objects.create(
            short_name="TEST2",
            full_name="Test Asset 2",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
        )
        MarketPriceModel.objects.create(
            asset=asset2,
            date=self.reference_date,
            price=95.0,
        )

        params = {
            "reference_date": self.reference_date.isoformat(),
            "previous_date": self.previous_date.isoformat(),
        }
        response = self.client.get(self.base_url, params)

        assert response.status_code == 200
        assert response.context.get("data_to_display") == [
            {
                "asset_class": "Stocks",
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": "US",
                                "asset": "TEST",
                                "name": "Test Asset",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": 90.0,
                                "price_change": 10.0,
                                "price_change_pct": 11.111111111111116,
                            },
                            {
                                "country": "US",
                                "asset": "TEST2",
                                "name": "Test Asset 2",
                                "maturity": None,
                                "price": 95.0,
                                "previous_price": None,
                                "price_change": None,
                                "price_change_pct": None,
                            },
                        ],
                    }
                ],
            }
        ]
        assert response.context.get("left_asset_classes") == [
            "Stocks",
            "Commodities",
            "Exchange Rates",
            "Crypto Exchange Rates",
            "Others",
        ]
        assert response.context.get("right_asset_classes") == ["Interest Rates"]
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert response.context.get("previous_date") == self.previous_date.isoformat()
        assert (
            response.context.get("default_reference_date")
            == self.reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_date")
            == self.previous_date.isoformat()
        )
