from datetime import date, timedelta

from django.test import TestCase

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)
from market_overview.services.market_data_services import (
    calculate_price_change,
    get_all_asset_prices_for_date,
    get_historical_prices,
    get_yield_curve,
)


class TestMarketDataServices(TestCase):
    """Test cases for market_data_services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.price_date = date(2024, 1, 15)
        self.previous_date = date(2024, 1, 10)
        self.location = LocationChoices.US

        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )

        MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.price_date,
            price=100.0,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.previous_date,
            price=90.0,
        )

    def test_calculate_price_change_success(self):
        """
        GIVEN an existing asset and prices
        WHEN calculating price changes for valid dates
        THEN the price change is correctly calculated
        """
        reference_market_prices = get_all_asset_prices_for_date(self.price_date)
        comparison_market_prices = get_all_asset_prices_for_date(self.previous_date)

        result = calculate_price_change(
            reference_market_prices=reference_market_prices,
            comparison_market_prices=comparison_market_prices,
        )

        price_change_pct = (100 / 90 - 1) * 100
        assert result == [
            {
                "asset_class": AssetClassChoices.STOCKS,
                "asset_id": 1,
                "asset_type": AssetTypeChoices.EQUITY_INDEX,
                "comment": "",
                "comment_previous": "",
                "full_name": "Test Asset",
                "location": self.location,
                "maturity": None,
                "price": 100.0,
                "price_change": 10.0,
                "price_change_pct": price_change_pct,
                "price_previous": 90.0,
                "short_name": "TEST",
                "source": "",
            },
        ]

    def test_calculate_price_change_no_reference_data(self):
        """
        GIVEN an existing asset and prices
        WHEN calculating price changes for a reference date without prices
        THEN an empty list is returned
        """
        not_existing_date = self.price_date + timedelta(days=1)
        reference_market_prices = get_all_asset_prices_for_date(not_existing_date)
        comparison_market_prices = get_all_asset_prices_for_date(self.previous_date)

        result = calculate_price_change(
            reference_market_prices=reference_market_prices,
            comparison_market_prices=comparison_market_prices,
        )

        assert result == []

    def test_calculate_price_change_no_previous_data(self):
        """
        GIVEN an existing asset and prices
        WHEN calculating price changes for a previous date without prices
        THEN an empty list is returned
        """
        not_existing_date = self.previous_date - timedelta(days=1)
        reference_market_prices = get_all_asset_prices_for_date(self.price_date)
        comparison_market_prices = get_all_asset_prices_for_date(not_existing_date)

        result = calculate_price_change(
            reference_market_prices=reference_market_prices,
            comparison_market_prices=comparison_market_prices,
        )

        assert result == []

    def test_calculate_price_change_rates_asset_class(self):
        """
        GIVEN a rates asset and 2 prices
        WHEN calculating price changes for a rates asset
        THEN the price change is calculated in basis points
        """
        rates_asset = AssetModel.objects.create(
            short_name="RATES_TEST",
            full_name="Rates Asset",
            asset_id=2,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
        )
        MarketPriceModel.objects.create(
            asset=rates_asset,
            date=self.price_date,
            price=2.5,
        )
        MarketPriceModel.objects.create(
            asset=rates_asset,
            date=self.previous_date,
            price=2.0,
        )

        reference_market_prices = get_all_asset_prices_for_date(self.price_date)
        comparison_market_prices = get_all_asset_prices_for_date(self.previous_date)

        result = calculate_price_change(
            reference_market_prices=reference_market_prices,
            comparison_market_prices=comparison_market_prices,
        )

        rates_results = [data for data in result if data["short_name"] == "RATES_TEST"]
        assert rates_results == [
            {
                "asset_class": AssetClassChoices.RATES,
                "asset_id": 2,
                "asset_type": AssetTypeChoices.GOVERNMENT_BOND_RATE,
                "comment": "",
                "comment_previous": "",
                "full_name": "Rates Asset",
                "location": None,
                "maturity": None,
                "price": 2.5,
                "price_change": 50.0,
                "price_change_pct": None,
                "price_previous": 2.0,
                "short_name": "RATES_TEST",
                "source": "",
            },
        ]

    def test_calculate_price_change_with_none_prices(self):
        """
        GIVEN an existing asset and prices
        WHEN calculating price changes for a previous date with a None price
        THEN the price change is correctly handled and calculated as None
        """
        previous_week_date = self.previous_date - timedelta(days=7)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=previous_week_date,
            price=None,
        )

        reference_market_prices = get_all_asset_prices_for_date(self.price_date)
        comparison_market_prices = get_all_asset_prices_for_date(previous_week_date)

        result = calculate_price_change(
            reference_market_prices=reference_market_prices,
            comparison_market_prices=comparison_market_prices,
        )

        assert result == [
            {
                "asset_class": AssetClassChoices.STOCKS,
                "asset_id": 1,
                "asset_type": AssetTypeChoices.EQUITY_INDEX,
                "comment": "",
                "comment_previous": "",
                "full_name": "Test Asset",
                "location": self.location,
                "maturity": None,
                "price": 100.0,
                "price_change": None,
                "price_change_pct": None,
                "price_previous": None,
                "short_name": "TEST",
                "source": "",
            },
        ]

    def test_get_historical_prices_success(self):
        """
        GIVEN prices for an asset and date
        WHEN getting the historical prices
        THEN all historical prices for the asset are returned
        """
        next_date = self.price_date + timedelta(days=1)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=next_date,
            price=101.0,
        )

        result = get_historical_prices(short_name="TEST")

        assert result == [
            {"price": 90.0, "price_date": self.previous_date},
            {"price": 100.0, "price_date": self.price_date},
            {"price": 101.0, "price_date": next_date},
        ]

    def test_get_historical_prices_with_date_range(self):
        """
        GIVEN prices in database
        WHEN getting the historical prices for a specific asset and date range
        THEN only prices within the date range are returned
        """
        start_date = self.price_date - timedelta(days=10)
        next_date = self.price_date + timedelta(days=1)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=next_date,
            price=120.0,
        )

        result = get_historical_prices(
            short_name="TEST", start_date=start_date, end_date=self.price_date
        )

        assert result == [
            {"price": 90.0, "price_date": self.previous_date},
            {"price": 100.0, "price_date": self.price_date},
        ]

    def test_get_historical_prices_with_start_date_only(self):
        """
        GIVEN prices in database
        WHEN getting the historical prices for a specific asset and start date
        THEN only prices after the start date are returned
        """
        start_date = self.price_date - timedelta(days=2)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=start_date - timedelta(days=1),
            price=120.0,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=start_date,
            price=80.0,
        )

        result = get_historical_prices(short_name="TEST", start_date=start_date)

        assert result == [
            {"price": 80.0, "price_date": start_date},
            {"price": 100.0, "price_date": self.price_date},
        ]

    def test_get_historical_prices_with_end_date_only(self):
        """
        GIVEN prices in database
        WHEN getting the historical prices for a specific asset and end date
        THEN only prices before the end date are returned
        """
        end_date = self.price_date + timedelta(days=1)
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.price_date + timedelta(days=1),
            price=120.0,
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=end_date + timedelta(days=1),
            price=80.0,
        )

        result = get_historical_prices(short_name="TEST", end_date=end_date)

        assert result == [
            {"price": 90.0, "price_date": self.previous_date},
            {"price": 100.0, "price_date": self.price_date},
            {"price": 120.0, "price_date": self.price_date + timedelta(days=1)},
        ]

    def test_get_historical_prices_ordering(self):
        """
        GIVEN prices in database
        WHEN getting the historical prices
        THEN the prices are sorted by price_date ascending
        """
        for i in range(3):
            MarketPriceModel.objects.create(
                asset=self.asset,
                date=self.price_date - timedelta(days=i + 1),
                price=None,
            )

        result = get_historical_prices(short_name="TEST")

        assert len(result) > 1
        for i in range(len(result) - 1):
            assert result[i]["price_date"] <= result[i + 1]["price_date"]

    def test_get_historical_prices_nonexistent_asset(self):
        """
        GIVEN a non-existent asset
        WHEN getting the historical prices
        THEN an empty list is returned
        """
        result = get_historical_prices(short_name="NONEXISTENT")

        assert result == []

    def test_get_yield_curve_success(self):
        """
        GIVEN prices for yield curve assets
        WHEN getting the yield curve for a specific date and location
        THEN the yield curve is returned with all maturities
        """
        for maturity in [1.0, 2.0, 5.0, 10.0]:
            asset = AssetModel.objects.create(
                short_name=f"UST{int(maturity)}Y",
                full_name=f"US Treasury {int(maturity)}Y",
                asset_id=int(maturity),
                asset_class=AssetClassChoices.RATES,
                asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
                location=self.location,
                maturity=maturity,
            )
            MarketPriceModel.objects.create(
                asset=asset,
                date=self.price_date,
                price=2.0 + maturity * 0.1,
            )

        result = get_yield_curve(target_date=self.price_date, location=self.location)

        assert result == [
            {"maturity": 1.0, "price": 2.1, "short_name": "UST1Y"},
            {"maturity": 2.0, "price": 2.2, "short_name": "UST2Y"},
            {"maturity": 5.0, "price": 2.5, "short_name": "UST5Y"},
            {"maturity": 10.0, "price": 3.0, "short_name": "UST10Y"},
        ]

    def test_get_yield_curve_empty_result(self):
        """
        GIVEN a date that has no yield curve data
        WHEN getting the yield curve
        THEN an empty list is returned
        """
        result = get_yield_curve(target_date=self.price_date, location=self.location)

        assert result == []

    def test_get_yield_curve_ordering(self):
        """
        GIVEN a list of maturities
        WHEN getting the yield curve
        THEN the maturities are sorted by maturity, None values last
        """
        maturities = [10.0, None, 2.0, 5.0]
        for maturity in maturities:
            asset = AssetModel.objects.create(
                short_name=f"UST{int(maturity)}Y" if maturity else "USTNONE",
                full_name=(
                    f"US Treasury {int(maturity)}Y" if maturity else "US Treasury None"
                ),
                asset_id=int(maturity) if maturity else 0,
                asset_class=AssetClassChoices.RATES,
                asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
                location=self.location,
                maturity=maturity,
            )
            MarketPriceModel.objects.create(
                asset=asset,
                date=self.price_date,
                price=2.0 + (maturity * 0.1 if maturity else 0.0),
            )

        result = get_yield_curve(target_date=self.price_date, location=self.location)

        assert result == [
            {"maturity": 2.0, "price": 2.2, "short_name": "UST2Y"},
            {"maturity": 5.0, "price": 2.5, "short_name": "UST5Y"},
            {"maturity": 10.0, "price": 3.0, "short_name": "UST10Y"},
            {"maturity": None, "price": 2.0, "short_name": "USTNONE"},
        ]

    def test_get_yield_curve_multiple_asset_classes(self):
        """
        GIVEN assets with different asset classes
        WHEN getting the yield curve
        THEN only RATES assets are returned
        """
        stock_asset = AssetModel.objects.create(
            short_name="STOCK",
            full_name="Stock Asset",
            asset_id=100,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )
        MarketPriceModel.objects.create(
            asset=stock_asset,
            date=self.price_date,
            price=100.0,
        )
        rates_asset = AssetModel.objects.create(
            short_name="RATES",
            full_name="Rates Asset",
            asset_id=101,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=self.location,
            maturity=10.0,
        )
        MarketPriceModel.objects.create(
            asset=rates_asset,
            date=self.price_date,
            price=2.0,
        )

        result = get_yield_curve(target_date=self.price_date, location=self.location)

        assert result == [
            {"maturity": 10.0, "price": 2.0, "short_name": "RATES"},
        ]
