from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase

from data_visualization.services.market_chart_services import (
    ChartDuration,
    MarketChartsFrontData,
    get_market_charts_dropdown_values,
    get_market_charts_labels,
    get_market_charts_market_data,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
)


class TestMarketChartServices(TestCase):
    """Test cases for market_chart_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.reference_date = date(2024, 1, 15)
        self.previous_curve_date = date(2024, 1, 10)

        self.asset_stock = AssetModel.objects.create(
            short_name="DJIA",
            full_name="Dow Jones Industrial Average",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
        )
        self.asset_fx = AssetModel.objects.create(
            short_name="EURUSD",
            full_name="Euro US Dollar",
            asset_id=2,
            asset_class=AssetClassChoices.FX,
            asset_type=AssetTypeChoices.FX_SPOT_RATE,
            location=LocationChoices.EU,
        )
        self.asset_rate = AssetModel.objects.create(
            short_name="UST10Y",
            full_name="US Treasury 10 Year",
            asset_id=3,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=LocationChoices.US,
        )

    def test_get_market_charts_dropdown_values_success(self):
        """
        GIVEN existing assets
        WHEN getting market charts dropdown values
        THEN the correct dropdown values are returned
        """
        result = get_market_charts_dropdown_values()
        assert result == {
            "stocks": [
                {
                    "full_name": "Dow Jones Industrial Average",
                    "short_name": "DJIA",
                },
            ],
            "fx": [
                {
                    "full_name": "Euro US Dollar",
                    "short_name": "EURUSD",
                },
            ],
            "crypto": [],
            "commodity": [],
            "rates": [
                {
                    "full_name": "US Treasury 10 Year",
                    "short_name": "UST10Y",
                },
            ],
            "locations": [
                "United States",
                "Europe",
                "Germany",
                "France",
                "Japan",
            ],
        }

    def test_get_market_charts_labels_success(self):
        """
        GIVEN dropdown values and front data
        WHEN getting market charts labels
        THEN the correct labels are returned
        """
        dropdown_values = get_market_charts_dropdown_values()
        front_data = MarketChartsFrontData(
            reference_date=self.reference_date,
            previous_curve_date=self.previous_curve_date,
            yield_curve_location=str(LocationChoices.US.label),
            stock_name="DJIA",
            fx_name="EURUSD",
            crypto_name="BTC",
            commodity_name="Gold",
            main_rate="UST10Y",
            spread_rate=None,
            stock_chart_duration=ChartDuration.ONE_MONTH,
            fx_chart_duration=ChartDuration.ONE_MONTH,
            crypto_chart_duration=ChartDuration.ONE_MONTH,
            commodity_chart_duration=ChartDuration.ONE_MONTH,
            spread_rates_chart_duration=ChartDuration.ONE_MONTH,
            stock_name_compare="",
            fx_name_compare="",
            crypto_name_compare="",
            commodity_name_compare="",
        )

        result = get_market_charts_labels(dropdown_values, front_data)
        assert result == {
            "stocks": "Dow Jones Industrial Average",
            "fx": "Euro US Dollar",
            "crypto": None,
            "commodity": None,
            "yield_curve_location": str(LocationChoices.US.label),
            "main_rate": "UST10Y",
            "main_rate_full_name": "US Treasury 10 Year",
            "spread_rate": None,
            "stock_name_compare": None,
            "fx_name_compare": None,
            "crypto_name_compare": None,
            "commodity_name_compare": None,
        }

    def test_get_market_charts_labels_with_compare_assets(self):
        """
        GIVEN dropdown values and front data with compare assets
        WHEN getting market charts labels
        THEN the correct labels including compare assets are returned
        """
        dropdown_values = get_market_charts_dropdown_values()
        front_data = MarketChartsFrontData(
            reference_date=self.reference_date,
            previous_curve_date=self.previous_curve_date,
            yield_curve_location=str(LocationChoices.US.label),
            stock_name="DJIA",
            fx_name="EURUSD",
            crypto_name="BTC",
            commodity_name="Gold",
            main_rate="UST10Y",
            spread_rate=None,
            stock_chart_duration=ChartDuration.ONE_MONTH,
            fx_chart_duration=ChartDuration.ONE_MONTH,
            crypto_chart_duration=ChartDuration.ONE_MONTH,
            commodity_chart_duration=ChartDuration.ONE_MONTH,
            spread_rates_chart_duration=ChartDuration.ONE_MONTH,
            stock_name_compare="DJIA",
            fx_name_compare="EURUSD",
            crypto_name_compare="",
            commodity_name_compare="",
        )

        result = get_market_charts_labels(dropdown_values, front_data)
        assert result == {
            "stocks": "Dow Jones Industrial Average",
            "fx": "Euro US Dollar",
            "crypto": None,
            "commodity": None,
            "yield_curve_location": str(LocationChoices.US.label),
            "main_rate": "UST10Y",
            "main_rate_full_name": "US Treasury 10 Year",
            "spread_rate": None,
            "stock_name_compare": "Dow Jones Industrial Average",
            "fx_name_compare": "Euro US Dollar",
            "crypto_name_compare": None,
            "commodity_name_compare": None,
        }

    def test_get_market_charts_labels_wrong_asset_name(self):
        """
        GIVEN dropdown values and front data with wrong asset name
        WHEN getting market charts labels
        THEN None labels are returned for wrong asset name
        """
        dropdown_values = get_market_charts_dropdown_values()
        front_data = MarketChartsFrontData(
            reference_date=self.reference_date,
            previous_curve_date=self.previous_curve_date,
            yield_curve_location=str(LocationChoices.US.label),
            stock_name="WRONG",
            fx_name="WRONG",
            crypto_name="",
            commodity_name="",
            main_rate="UST10Y",
            spread_rate=None,
            stock_chart_duration=ChartDuration.ONE_MONTH,
            fx_chart_duration=ChartDuration.ONE_MONTH,
            crypto_chart_duration=ChartDuration.ONE_MONTH,
            commodity_chart_duration=ChartDuration.ONE_MONTH,
            spread_rates_chart_duration=ChartDuration.ONE_MONTH,
            stock_name_compare="",
            fx_name_compare="",
            crypto_name_compare="",
            commodity_name_compare="",
        )

        result = get_market_charts_labels(dropdown_values, front_data)
        assert result == {
            "stocks": None,
            "fx": None,
            "crypto": None,
            "commodity": None,
            "yield_curve_location": str(LocationChoices.US.label),
            "main_rate": "UST10Y",
            "main_rate_full_name": "US Treasury 10 Year",
            "spread_rate": None,
            "stock_name_compare": None,
            "fx_name_compare": None,
            "crypto_name_compare": None,
            "commodity_name_compare": None,
        }

    @patch(
        "data_visualization.services.market_chart_services.market_data_services.get_historical_prices"
    )
    @patch(
        "data_visualization.services.market_chart_services.market_data_services.get_yield_curve"
    )
    def test_get_market_charts_market_data_success(
        self, mock_get_yield_curve, mock_get_historical_prices
    ):
        """
        GIVEN front data and mocked market data services
        WHEN getting market charts market data
        THEN the correct market data is returned
        """
        mock_get_historical_prices.return_value = [
            {"price_date": self.reference_date - timedelta(days=1), "price": 100.0},
            {"price_date": self.reference_date, "price": 105.0},
        ]
        mock_get_yield_curve.return_value = [
            {"maturity": 1.0, "yield": 2.0},
            {"maturity": 10.0, "yield": 3.0},
        ]

        front_data = MarketChartsFrontData(
            reference_date=self.reference_date,
            previous_curve_date=self.previous_curve_date,
            yield_curve_location=str(LocationChoices.US.label),
            stock_name="DJIA",
            fx_name="EURUSD",
            crypto_name="BTC",
            commodity_name="Gold",
            main_rate="UST10Y",
            spread_rate=None,
            stock_chart_duration=ChartDuration.ONE_MONTH,
            fx_chart_duration=ChartDuration.ONE_MONTH,
            crypto_chart_duration=ChartDuration.ONE_MONTH,
            commodity_chart_duration=ChartDuration.ONE_MONTH,
            spread_rates_chart_duration=ChartDuration.ONE_MONTH,
            stock_name_compare="",
            fx_name_compare="",
            crypto_name_compare="",
            commodity_name_compare="",
        )

        result = get_market_charts_market_data(
            self.reference_date, self.previous_curve_date, front_data
        )
        assert result == {
            "commodity_prices": [
                {
                    "price": 100.0,
                    "price_date": self.reference_date - timedelta(days=1),
                },
                {
                    "price": 105.0,
                    "price_date": self.reference_date,
                },
            ],
            "commodity_prices_compare": [],
            "crypto_prices": [
                {
                    "price": 100.0,
                    "price_date": self.reference_date - timedelta(days=1),
                },
                {
                    "price": 105.0,
                    "price_date": self.reference_date,
                },
            ],
            "crypto_prices_compare": [],
            "fx_prices": [
                {
                    "price": 100.0,
                    "price_date": self.reference_date - timedelta(days=1),
                },
                {
                    "price": 105.0,
                    "price_date": self.reference_date,
                },
            ],
            "fx_prices_compare": [],
            "previous_yield_curve": [
                {
                    "maturity": 1.0,
                    "yield": 2.0,
                },
                {
                    "maturity": 10.0,
                    "yield": 3.0,
                },
            ],
            "reference_yield_curve": [
                {
                    "maturity": 1.0,
                    "yield": 2.0,
                },
                {
                    "maturity": 10.0,
                    "yield": 3.0,
                },
            ],
            "spread_rates": [
                {
                    "price": 10000.0,
                    "price_date": self.reference_date - timedelta(days=1),
                },
                {
                    "price": 10500.0,
                    "price_date": self.reference_date,
                },
            ],
            "stock_prices": [
                {
                    "price": 100.0,
                    "price_date": self.reference_date - timedelta(days=1),
                },
                {
                    "price": 105.0,
                    "price_date": self.reference_date,
                },
            ],
            "stock_prices_compare": [],
        }

    @patch(
        "data_visualization.services.market_chart_services.market_data_services.get_historical_prices"
    )
    @patch(
        "data_visualization.services.market_chart_services.market_data_services.get_yield_curve"
    )
    def test_get_market_charts_market_data_with_spread_rate(
        self, mock_get_yield_curve, mock_get_historical_prices
    ):
        """
        GIVEN front data with spread rate
        WHEN getting market charts market data
        THEN the spread rates are calculated correctly
        """

        def historical_prices_side_effect(asset_name, start_date, end_date):
            if asset_name == "UST10Y":
                return [
                    {
                        "price_date": self.reference_date - timedelta(days=1),
                        "price": 0.02,
                    },
                    {"price_date": self.reference_date, "price": 0.025},
                ]
            elif asset_name == "UST2Y":
                return [
                    {
                        "price_date": self.reference_date - timedelta(days=1),
                        "price": 0.01,
                    },
                    {"price_date": self.reference_date, "price": 0.015},
                ]
            return []

        mock_get_historical_prices.side_effect = historical_prices_side_effect
        mock_get_yield_curve.return_value = []

        front_data = MarketChartsFrontData(
            reference_date=self.reference_date,
            previous_curve_date=self.previous_curve_date,
            yield_curve_location=str(LocationChoices.US.label),
            stock_name="DJIA",
            fx_name="EURUSD",
            crypto_name="BTC",
            commodity_name="Gold",
            main_rate="UST10Y",
            spread_rate="UST2Y",
            stock_chart_duration=ChartDuration.ONE_MONTH,
            fx_chart_duration=ChartDuration.ONE_MONTH,
            crypto_chart_duration=ChartDuration.ONE_MONTH,
            commodity_chart_duration=ChartDuration.ONE_MONTH,
            spread_rates_chart_duration=ChartDuration.ONE_MONTH,
            stock_name_compare="",
            fx_name_compare="",
            crypto_name_compare="",
            commodity_name_compare="",
        )

        result = get_market_charts_market_data(
            self.reference_date, self.previous_curve_date, front_data
        )
        assert result == {
            "commodity_prices": [],
            "commodity_prices_compare": [],
            "crypto_prices": [],
            "crypto_prices_compare": [],
            "fx_prices": [],
            "fx_prices_compare": [],
            "previous_yield_curve": [],
            "reference_yield_curve": [],
            "spread_rates": [
                {
                    "price": (0.02 - 0.01) * 100,
                    "price_date": self.reference_date - timedelta(days=1),
                },
                {
                    "price": (0.025 - 0.015) * 100,
                    "price_date": self.reference_date,
                },
            ],
            "stock_prices": [],
            "stock_prices_compare": [],
        }
