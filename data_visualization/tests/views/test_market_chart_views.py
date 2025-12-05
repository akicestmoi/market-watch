import json
from datetime import date, timedelta

from django.test import Client, TestCase
from pandas.tseries.offsets import BDay

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
)


class TestMarketChartsView(TestCase):
    """Test cases for market_charts_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/market-charts/"
        self.reference_date = (date.today() - BDay(1)).date()
        self.previous_curve_date = (self.reference_date - BDay(1)).date()
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
        self.asset_crypto = AssetModel.objects.create(
            short_name="BTC",
            full_name="Bitcoin",
            asset_id=3,
            asset_class=AssetClassChoices.CRYPTO,
            asset_type=AssetTypeChoices.CRYPTO_SPOT_RATE,
            location=LocationChoices.US,
        )
        self.asset_commodity = AssetModel.objects.create(
            short_name="Gold",
            full_name="Gold",
            asset_id=4,
            asset_class=AssetClassChoices.COMMODITIES,
            asset_type=AssetTypeChoices.COMMODITIY_FUTURE_SPOT_PRICE,
            location=LocationChoices.US,
        )
        self.asset_rate = AssetModel.objects.create(
            short_name="UST10Y",
            full_name="US Treasury 10 Year",
            asset_id=5,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=LocationChoices.US,
            maturity=10.0,
        )

    def test_market_charts_view_success(self):
        """
        GIVEN valid parameters
        WHEN accessing market charts view
        THEN the view renders successfully with chart data
        """
        query_params = f"reference_date={self.reference_date.isoformat()}&previous_curve_date={self.previous_curve_date.isoformat()}"
        response = self.client.get(f"{self.base_url}?{query_params}")

        assert response.status_code == 200
        default_reference_date = (date.today() - BDay(1)).date()
        default_previous_curve_date = (date.today() - BDay(2)).date()
        assert response.context.get("reference_date") == self.reference_date.isoformat()
        assert (
            response.context.get("previous_curve_date")
            == self.previous_curve_date.isoformat()
        )
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_curve_date")
            == default_previous_curve_date.isoformat()
        )
        dropdown_values_str = response.context.get("dropdown_values")
        assert dropdown_values_str is not None
        dropdown_values = json.loads(dropdown_values_str)
        assert dropdown_values == {
            "stocks": [
                {"short_name": "DJIA", "full_name": "Dow Jones Industrial Average"}
            ],
            "fx": [{"short_name": "EURUSD", "full_name": "Euro US Dollar"}],
            "crypto": [{"short_name": "BTC", "full_name": "Bitcoin"}],
            "commodity": [{"short_name": "Gold", "full_name": "Gold"}],
            "rates": [{"short_name": "UST10Y", "full_name": "US Treasury 10 Year"}],
            "locations": [
                "United States",
                "Europe",
                "Germany",
                "France",
                "Japan",
            ],
        }
        selected_values_str = response.context.get("selected_values")
        assert selected_values_str is not None
        selected_values = json.loads(selected_values_str)
        assert selected_values == {
            "reference_date": self.reference_date.isoformat(),
            "previous_curve_date": self.previous_curve_date.isoformat(),
            "yield_curve_location": "United States",
            "stock_name": "DJIA",
            "fx_name": "EURUSD",
            "crypto_name": "BTC",
            "commodity_name": "Gold",
            "main_rate": "UST10Y",
            "spread_rate": None,
            "stock_chart_duration": "1M",
            "fx_chart_duration": "1M",
            "crypto_chart_duration": "1M",
            "commodity_chart_duration": "1M",
            "spread_rates_chart_duration": "1M",
            "stock_name_compare": None,
            "fx_name_compare": None,
            "crypto_name_compare": None,
            "commodity_name_compare": None,
        }
        labels_str = response.context.get("labels")
        assert labels_str is not None
        labels = json.loads(labels_str)
        assert labels == {
            "stocks": "Dow Jones Industrial Average",
            "fx": "Euro US Dollar",
            "crypto": "Bitcoin",
            "commodity": "Gold",
            "yield_curve_location": "United States",
            "main_rate": "UST10Y",
            "main_rate_full_name": "US Treasury 10 Year",
            "spread_rate": None,
            "stock_name_compare": None,
            "fx_name_compare": None,
            "crypto_name_compare": None,
            "commodity_name_compare": None,
        }
        market_data_str = response.context.get("market_data")
        assert market_data_str is not None
        market_data = json.loads(market_data_str)
        assert market_data == {
            "stock_prices": [],
            "stock_prices_compare": [],
            "fx_prices": [],
            "fx_prices_compare": [],
            "crypto_prices": [],
            "crypto_prices_compare": [],
            "commodity_prices": [],
            "commodity_prices_compare": [],
            "reference_yield_curve": [],
            "previous_yield_curve": [],
            "spread_rates": [],
        }

    def test_market_charts_view_default_values(self):
        """
        GIVEN no parameters
        WHEN accessing market charts view
        THEN default values are used
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        default_reference_date = (date.today() - BDay(1)).date()
        default_previous_curve_date = (date.today() - BDay(2)).date()
        assert (
            response.context.get("reference_date") == default_reference_date.isoformat()
        )
        assert (
            response.context.get("previous_curve_date")
            == default_previous_curve_date.isoformat()
        )
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_curve_date")
            == default_previous_curve_date.isoformat()
        )

    def test_market_charts_view_future_reference_date(self):
        """
        GIVEN a reference date in the future
        WHEN accessing market charts view
        THEN an error message is displayed
        """
        future_date = date.today() + timedelta(days=1)
        query_params = f"reference_date={future_date.isoformat()}&previous_curve_date={self.previous_curve_date.isoformat()}"
        response = self.client.get(f"{self.base_url}?{query_params}")

        assert response.status_code == 200
        default_reference_date = (date.today() - BDay(1)).date()
        default_previous_curve_date = (date.today() - BDay(2)).date()
        assert response.context.get("reference_date") == future_date.isoformat()
        assert (
            response.context.get("previous_curve_date")
            == self.previous_curve_date.isoformat()
        )
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_curve_date")
            == default_previous_curve_date.isoformat()
        )
        error_messages = response.context.get("error_messages")
        assert error_messages is not None
        assert json.loads(error_messages) == {
            "reference_date": f"Reference date {future_date} must be before today {date.today()}."
        }

    def test_market_charts_view_reference_date_before_previous_curve_date(self):
        """
        GIVEN a reference date before the previous curve date
        WHEN accessing market charts view
        THEN an error message is displayed
        """
        query_params = f"reference_date={self.previous_curve_date.isoformat()}&previous_curve_date={self.reference_date.isoformat()}"
        response = self.client.get(f"{self.base_url}?{query_params}")

        assert response.status_code == 200
        default_reference_date = (date.today() - BDay(1)).date()
        default_previous_curve_date = (date.today() - BDay(2)).date()
        assert (
            response.context.get("reference_date")
            == self.previous_curve_date.isoformat()
        )
        assert (
            response.context.get("previous_curve_date")
            == self.reference_date.isoformat()
        )
        assert (
            response.context.get("default_reference_date")
            == default_reference_date.isoformat()
        )
        assert (
            response.context.get("default_previous_curve_date")
            == default_previous_curve_date.isoformat()
        )
        error_messages = response.context.get("error_messages")
        assert error_messages is not None
        assert json.loads(error_messages) == {
            "previous_curve_date": f"Reference date {self.previous_curve_date} must be greater than the previous curve date {self.reference_date}."
        }
