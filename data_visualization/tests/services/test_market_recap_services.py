from datetime import date

from django.test import TestCase

from data_visualization.services.market_recap_services import (
    format_data_for_market_recap_display,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)


class TestMarketRecapServices(TestCase):
    """Test cases for market_recap_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.reference_date = date(2024, 1, 15)
        self.previous_date = date(2024, 1, 10)

        self.asset_stocks = AssetModel.objects.create(
            short_name="STOCK1",
            full_name="Stock 1",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
        )
        self.asset_rates = AssetModel.objects.create(
            short_name="RATE1",
            full_name="Rate 1",
            asset_id=2,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=LocationChoices.US,
            maturity=10.0,
        )

        self.reference_price_stocks = MarketPriceModel.objects.create(
            asset=self.asset_stocks,
            date=self.reference_date,
            price=100.0,
        )
        self.previous_price_stocks = MarketPriceModel.objects.create(
            asset=self.asset_stocks,
            date=self.previous_date,
            price=90.0,
        )

        self.reference_price_rates = MarketPriceModel.objects.create(
            asset=self.asset_rates,
            date=self.reference_date,
            price=2.5,
        )
        self.previous_price_rates = MarketPriceModel.objects.create(
            asset=self.asset_rates,
            date=self.previous_date,
            price=2.42,
        )

    def test_format_data_for_market_recap_display_success(self):
        """
        GIVEN reference and previous market prices
        WHEN formatting data for market recap display
        THEN the data is correctly formatted with locations and asset classes
        """

        reference_prices = [self.reference_price_stocks, self.reference_price_rates]
        previous_prices = [self.previous_price_stocks, self.previous_price_rates]

        result = format_data_for_market_recap_display(reference_prices, previous_prices)
        assert result == [
            {
                "asset_class": AssetClassChoices.STOCKS.label,
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": LocationChoices.US,
                                "asset": "STOCK1",
                                "name": "Stock 1",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": 90.0,
                                "price_change": 10.0,
                                "price_change_pct": (100.0 / 90.0 - 1) * 100,
                            }
                        ],
                    }
                ],
            },
            {
                "asset_class": AssetClassChoices.RATES.label,
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": LocationChoices.US,
                                "asset": "RATE1",
                                "name": "Rate 1",
                                "maturity": 10.0,
                                "price": 2.5,
                                "previous_price": 2.42,
                                "price_change": (2.5 - 2.42) * 100,
                                "price_change_pct": None,
                            }
                        ],
                    }
                ],
            },
        ]

    def test_format_data_for_market_recap_display_multiple_locations(self):
        """
        GIVEN reference and previous market prices with multiple locations
        WHEN formatting data for market recap display
        THEN the data is correctly grouped by location
        """
        asset_eu = AssetModel.objects.create(
            short_name="STOCK2",
            full_name="Stock 2",
            asset_id=3,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.EU,
        )
        reference_price_eu = MarketPriceModel.objects.create(
            asset=asset_eu,
            date=self.reference_date,
            price=200.0,
        )
        previous_price_eu = MarketPriceModel.objects.create(
            asset=asset_eu,
            date=self.previous_date,
            price=180.0,
        )

        reference_prices = [
            self.reference_price_stocks,
            self.reference_price_rates,
            reference_price_eu,
        ]
        previous_prices = [
            self.previous_price_stocks,
            self.previous_price_rates,
            previous_price_eu,
        ]

        result = format_data_for_market_recap_display(reference_prices, previous_prices)
        assert result == [
            {
                "asset_class": AssetClassChoices.STOCKS.label,
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": LocationChoices.US,
                                "asset": "STOCK1",
                                "name": "Stock 1",
                                "maturity": None,
                                "price": 100.0,
                                "previous_price": 90.0,
                                "price_change": 10.0,
                                "price_change_pct": (100.0 / 90.0 - 1) * 100,
                            }
                        ],
                    },
                    {
                        "location": "Europe",
                        "assets": [
                            {
                                "country": LocationChoices.EU,
                                "asset": "STOCK2",
                                "name": "Stock 2",
                                "maturity": None,
                                "price": 200.0,
                                "previous_price": 180.0,
                                "price_change": 20.0,
                                "price_change_pct": (200.0 / 180.0 - 1) * 100,
                            }
                        ],
                    },
                ],
            },
            {
                "asset_class": AssetClassChoices.RATES.label,
                "locations": [
                    {
                        "assets": [
                            {
                                "asset": "RATE1",
                                "country": LocationChoices.US,
                                "maturity": 10.0,
                                "name": "Rate 1",
                                "previous_price": 2.42,
                                "price": 2.5,
                                "price_change": (2.5 - 2.42) * 100,
                                "price_change_pct": None,
                            },
                        ],
                        "location": "North America",
                    },
                ],
            },
        ]

    def test_format_data_for_market_recap_display_no_previous_price(self):
        """
        GIVEN reference prices without corresponding previous prices
        WHEN formatting data for market recap display
        THEN the data is formatted with None for previous price fields
        """
        reference_prices = [self.reference_price_stocks]
        previous_prices = []

        result = format_data_for_market_recap_display(reference_prices, previous_prices)

        assert result == [
            {
                "asset_class": AssetClassChoices.STOCKS.label,
                "locations": [
                    {
                        "location": "North America",
                        "assets": [
                            {
                                "country": LocationChoices.US,
                                "asset": "STOCK1",
                                "name": "Stock 1",
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

    def test_format_data_for_market_recap_display_sorted_by_maturity(self):
        """
        GIVEN reference and previous market prices with multiple rates
        WHEN formatting data for market recap display
        THEN the rates are sorted by maturity
        """
        asset_rates_5y = AssetModel.objects.create(
            short_name="RATE5Y",
            full_name="Rate 5Y",
            asset_id=4,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=LocationChoices.US,
            maturity=5.0,
        )
        reference_price_5y = MarketPriceModel.objects.create(
            asset=asset_rates_5y,
            date=self.reference_date,
            price=1.50,
        )
        previous_price_5y = MarketPriceModel.objects.create(
            asset=asset_rates_5y,
            date=self.previous_date,
            price=1.45,
        )

        reference_prices = [self.reference_price_rates, reference_price_5y]
        previous_prices = [self.previous_price_rates, previous_price_5y]

        result = format_data_for_market_recap_display(reference_prices, previous_prices)

        rates_data = next(
            item
            for item in result
            if item["asset_class"] == AssetClassChoices.RATES.label
        )
        assert rates_data == {
            "asset_class": AssetClassChoices.RATES.label,
            "locations": [
                {
                    "location": "North America",
                    "assets": [
                        {
                            "country": LocationChoices.US,
                            "asset": "RATE5Y",
                            "name": "Rate 5Y",
                            "maturity": 5.0,
                            "price": 1.50,
                            "previous_price": 1.45,
                            "price_change": (1.50 - 1.45) * 100,
                            "price_change_pct": None,
                        },
                        {
                            "country": LocationChoices.US,
                            "asset": "RATE1",
                            "name": "Rate 1",
                            "maturity": 10.0,
                            "price": 2.5,
                            "previous_price": 2.42,
                            "price_change": (2.5 - 2.42) * 100,
                            "price_change_pct": None,
                        },
                    ],
                }
            ],
        }
