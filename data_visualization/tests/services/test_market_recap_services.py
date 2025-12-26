from datetime import date

from django.test import TestCase

from data_visualization.services.market_recap_services import (
    FX_MATRIX_ORDER,
    format_data_for_market_recap_display,
    get_fx_prices_matrix,
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

        self.asset_eurusd = AssetModel.objects.create(
            short_name="EURUSD",
            full_name="EUR-USD Exchange Rate",
            asset_id=1,
            asset_class=AssetClassChoices.FX,
            asset_type=AssetTypeChoices.FX_SPOT_RATE,
            location=None,
        )
        self.asset_gbpusd = AssetModel.objects.create(
            short_name="GBPUSD",
            full_name="GBP-USD Exchange Rate",
            asset_id=2,
            asset_class=AssetClassChoices.FX,
            asset_type=AssetTypeChoices.FX_SPOT_RATE,
            location=None,
        )
        self.asset_usdjpy = AssetModel.objects.create(
            short_name="USDJPY",
            full_name="USD-JPY Exchange Rate",
            asset_id=3,
            asset_class=AssetClassChoices.FX,
            asset_type=AssetTypeChoices.FX_SPOT_RATE,
            location=None,
        )
        self.asset_eurjpy = AssetModel.objects.create(
            short_name="EURJPY",
            full_name="EUR-JPY Exchange Rate",
            asset_id=4,
            asset_class=AssetClassChoices.FX,
            asset_type=AssetTypeChoices.FX_SPOT_RATE,
            location=None,
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

    def test_get_fx_prices_matrix(self):
        """
        GIVEN FX prices
        WHEN getting FX prices matrix
        THEN the matrix correctly shows percentage changes
        """
        MarketPriceModel.objects.create(
            asset=self.asset_eurusd,
            date=self.reference_date,
            price=1.10,
        )
        MarketPriceModel.objects.create(
            asset=self.asset_eurusd,
            date=self.previous_date,
            price=1.08,
        )

        MarketPriceModel.objects.create(
            asset=self.asset_gbpusd,
            date=self.reference_date,
            price=1.25,
        )
        MarketPriceModel.objects.create(
            asset=self.asset_gbpusd,
            date=self.previous_date,
            price=1.20,
        )

        MarketPriceModel.objects.create(
            asset=self.asset_usdjpy,
            date=self.reference_date,
            price=150.0,
        )
        MarketPriceModel.objects.create(
            asset=self.asset_usdjpy,
            date=self.previous_date,
            price=145.0,
        )

        MarketPriceModel.objects.create(
            asset=self.asset_eurjpy,
            date=self.reference_date,
            price=165.0,
        )
        MarketPriceModel.objects.create(
            asset=self.asset_eurjpy,
            date=self.previous_date,
            price=160.0,
        )

        # Check USDEUR percentage change: (1/1.10 - 1/1.08) / 1/1.08 * 100
        expected_usdeur_change = ((1 / 1.10) - (1 / 1.08)) / (1 / 1.08) * 100
        # Check USDGBP percentage change: (1/1.25 - 1/1.20) / 1/1.20 * 100
        expected_usdgbp_change = ((1 / 1.25) - (1 / 1.20)) / (1 / 1.20) * 100
        # Check USDJPY percentage change: (150.0 - 145.0) / 145.0 * 100
        expected_usdjpy_change = (150.0 - 145.0) / 145.0 * 100
        expected_usd_result = {
            "AUD": 0.0,
            "CHF": 0.0,
            "CNY": 0.0,
            "EUR": expected_usdeur_change,
            "GBP": expected_usdgbp_change,
            "JPY": expected_usdjpy_change,
            "USD": 0.0,
            "currency": "USD",
        }
        # Check EURUSD percentage change: (1.10 - 1.08) / 1.08 * 100
        expected_eurusd_change = (1.10 - 1.08) / 1.08 * 100
        # Check EURJPY percentage change: (165.0 - 160.0) / 160.0 * 100
        expected_eurjpy_change = (165.0 - 160.0) / 160.0 * 100
        expected_eur_result = {
            "AUD": 0.0,
            "CHF": 0.0,
            "CNY": 0.0,
            "EUR": 0.0,
            "GBP": 0.0,
            "JPY": expected_eurjpy_change,
            "USD": expected_eurusd_change,
            "currency": "EUR",
        }
        # Check GBPUSD percentage change: (1.25 - 1.20) / 1.20 * 100
        expected_gbpusd_change = (1.25 - 1.20) / 1.20 * 100
        expected_gbp_result = {
            "AUD": 0.0,
            "CHF": 0.0,
            "CNY": 0.0,
            "EUR": 0.0,
            "GBP": 0.0,
            "JPY": 0.0,
            "USD": expected_gbpusd_change,
            "currency": "GBP",
        }
        # Check JPYUSD percentage change: (1/150.0 - 1/145.0) / 1/145.0 * 100
        expected_jpyusd_change = ((1 / 150.0) - (1 / 145.0)) / (1 / 145.0) * 100
        # Check JPYEUR percentage change: (1/165.0 - 1/160.0) / 1/160.0 * 100
        expected_jpyeur_change = ((1 / 165.0) - (1 / 160.0)) / (1 / 160.0) * 100
        expected_jpy_result = {
            "AUD": 0.0,
            "CHF": 0.0,
            "CNY": 0.0,
            "EUR": expected_jpyeur_change,
            "GBP": 0.0,
            "JPY": 0.0,
            "USD": expected_jpyusd_change,
            "currency": "JPY",
        }
        # And all other missing pairs should be set to 0
        missing_currencies = ["CHF", "AUD", "CNY"]
        missing_pairs_result = [
            {
                "AUD": 0.0,
                "CHF": 0.0,
                "CNY": 0.0,
                "EUR": 0.0,
                "GBP": 0.0,
                "JPY": 0.0,
                "USD": 0.0,
                "currency": currency,
            }
            for currency in missing_currencies
        ]

        result = get_fx_prices_matrix(self.reference_date, self.previous_date)
        assert result == [
            expected_eur_result,
            expected_usd_result,
            expected_gbp_result,
            expected_jpy_result,
            *missing_pairs_result,
        ]
        # Verify the order of the result is the same as FX_MATRIX_ORDER
        assert [item["currency"] for item in result] == FX_MATRIX_ORDER

    def test_get_fx_prices_matrix_no_previous_prices(self):
        """
        GIVEN FX prices only for current date
        WHEN getting FX prices matrix
        THEN the matrix handles division by zero gracefully
        """
        MarketPriceModel.objects.create(
            asset=self.asset_eurusd,
            date=self.reference_date,
            price=1.10,
        )
        # No previous prices

        result = get_fx_prices_matrix(self.reference_date, self.previous_date)

        # Should return list of dicts with all zeros (no previous data to compare)
        assert isinstance(result, list)
        assert len(result) == len(FX_MATRIX_ORDER)

        # Create a lookup map for easier access
        result_map = {row["currency"]: row for row in result}

        # All values should be 0 (no previous data to compare)
        for currency1 in FX_MATRIX_ORDER:
            for currency2 in FX_MATRIX_ORDER:
                value = result_map[currency1][currency2]
                assert float(value) == 0.0

    def test_get_fx_prices_matrix_none_prices_handling(self):
        """
        GIVEN no FX prices for current date
        WHEN getting FX prices matrix
        THEN the matrix handles None values gracefully
        """
        # Pair with None price on current date
        MarketPriceModel.objects.create(
            asset=self.asset_eurusd,
            date=self.reference_date,
            price=None,
        )
        MarketPriceModel.objects.create(
            asset=self.asset_eurusd,
            date=self.previous_date,
            price=1.10,
        )

        # Pair with None price on previous date
        MarketPriceModel.objects.create(
            asset=self.asset_eurjpy,
            date=self.reference_date,
            price=1.08,
        )
        MarketPriceModel.objects.create(
            asset=self.asset_eurjpy,
            date=self.previous_date,
            price=None,
        )

        result = get_fx_prices_matrix(self.reference_date, self.previous_date)

        # Should return list of dicts with all zeros (no previous data to compare)
        assert isinstance(result, list)
        assert len(result) == len(FX_MATRIX_ORDER)

        # Create a lookup map for easier access
        result_map = {row["currency"]: row for row in result}

        # All values should be 0 (no previous data to compare)
        for currency1 in FX_MATRIX_ORDER:
            for currency2 in FX_MATRIX_ORDER:
                value = result_map[currency1][currency2]
                assert float(value) == 0.0
