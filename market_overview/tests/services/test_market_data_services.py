from datetime import date, timedelta

import pytest  # type: ignore[reportMissingImports]
from django.test import TestCase

import core.services as core_services
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
    get_all_asset_prices_for_date_without_holidays,
    get_historical_prices,
    get_yield_curve,
)
from market_overview.services.price_ingestion_services import SpecialComment


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

        assert result == [
            {
                "asset_class": "STOCKS",
                "asset_id": 1,
                "asset_type": "EQUITY_INDEX",
                "comment": None,
                "comment_previous": "",
                "full_name": "Test Asset",
                "location": "US",
                "maturity": None,
                "price": None,
                "price_change": None,
                "price_change_pct": None,
                "price_previous": 90.0,
                "short_name": "TEST",
                "source": "",
            },
        ]

    def test_calculate_price_change_no_previous_data(self):
        """
        GIVEN an existing asset and prices
        WHEN calculating price changes for a previous date without prices
        THEN reference data is returned with None for previous fields
        """
        not_existing_date = self.previous_date - timedelta(days=1)
        reference_market_prices = get_all_asset_prices_for_date(self.price_date)
        comparison_market_prices = get_all_asset_prices_for_date(not_existing_date)

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
                "comment_previous": None,
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
        THEN the maturities are sorted by maturity, None values converted to 0.0
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
            {"maturity": 0.0, "price": 2.0, "short_name": "USTNONE"},
            {"maturity": 2.0, "price": 2.2, "short_name": "UST2Y"},
            {"maturity": 5.0, "price": 2.5, "short_name": "UST5Y"},
            {"maturity": 10.0, "price": 3.0, "short_name": "UST10Y"},
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

    def test_get_yield_curve_includes_interbank_rates(self):
        """
        GIVEN both government bond rates and interbank rates
        WHEN getting the yield curve for US location with include_interbank_rates=True
        THEN both types are included, but EFFR is excluded (only SOFR for interbank)
        """
        # Create government bond rate
        gov_asset = AssetModel.objects.create(
            short_name="UST2Y",
            full_name="US Treasury 2 Year",
            asset_id=2,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=self.location,
            maturity=2.0,
        )
        MarketPriceModel.objects.create(
            asset=gov_asset,
            date=self.price_date,
            price=2.5,
        )

        # Create interbank rate EFFR (should be excluded for US)
        interbank_asset_effr = AssetModel.objects.create(
            short_name="EFFR",
            full_name="Effective Fed Funds Rate",
            asset_id=500,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=self.location,
            maturity=0.0,
        )
        MarketPriceModel.objects.create(
            asset=interbank_asset_effr,
            date=self.price_date,
            price=2.0,
        )

        # Create interbank rate SOFR (should be included for US)
        interbank_asset_sofr = AssetModel.objects.create(
            short_name="SOFR",
            full_name="Secured Overnight Financing Rate",
            asset_id=520,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=self.location,
            maturity=0.0,
        )
        MarketPriceModel.objects.create(
            asset=interbank_asset_sofr,
            date=self.price_date,
            price=2.1,
        )

        result = get_yield_curve(target_date=self.price_date, location=self.location)
        assert result == [
            {"maturity": 0.0, "price": 2.1, "short_name": "SOFR"},
            {"maturity": 2.0, "price": 2.5, "short_name": "UST2Y"},
        ]

    def test_get_yield_curve_us_excludes_effr(self):
        """
        GIVEN EFFR and SOFR interbank rates for US location
        WHEN getting the yield curve
        THEN only SOFR is included, EFFR is excluded
        """
        effr_asset = AssetModel.objects.create(
            short_name="EFFR",
            full_name="Effective Fed Funds Rate",
            asset_id=500,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.US,
            maturity=0.0,
        )
        MarketPriceModel.objects.create(
            asset=effr_asset,
            date=self.price_date,
            price=2.0,
        )

        sofr_asset = AssetModel.objects.create(
            short_name="SOFR",
            full_name="Secured Overnight Financing Rate",
            asset_id=520,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.US,
            maturity=0.0,
        )
        MarketPriceModel.objects.create(
            asset=sofr_asset,
            date=self.price_date,
            price=2.1,
        )

        result = get_yield_curve(
            target_date=self.price_date, location=LocationChoices.US
        )
        short_names = [point["short_name"] for point in result]
        assert short_names == ["SOFR"]

    def test_get_yield_curve_excludes_interbank_rates_when_false(self):
        """
        GIVEN both government bond rates and interbank rates
        WHEN getting the yield curve with include_interbank_rates=False
        THEN only government bond rates are included
        """
        # Create government bond rate
        gov_asset = AssetModel.objects.create(
            short_name="UST2Y",
            full_name="US Treasury 2 Year",
            asset_id=2,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=self.location,
            maturity=2.0,
        )
        MarketPriceModel.objects.create(
            asset=gov_asset,
            date=self.price_date,
            price=2.5,
        )

        # Create interbank rate SOFR (should be excluded)
        interbank_asset = AssetModel.objects.create(
            short_name="SOFR",
            full_name="Secured Overnight Financing Rate",
            asset_id=520,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=self.location,
            maturity=0.0,
        )
        MarketPriceModel.objects.create(
            asset=interbank_asset,
            date=self.price_date,
            price=2.1,
        )

        result = get_yield_curve(
            target_date=self.price_date,
            location=self.location,
            include_interbank_rates=False,
        )
        assert result == [
            {"maturity": 2.0, "price": 2.5, "short_name": "UST2Y"},
        ]

    def test_get_yield_curve_fr_includes_eu(self):
        """
        GIVEN assets for both FR and EU locations
        WHEN getting the yield curve for FR location
        THEN both FR and EU assets are included
        """
        # Create FR government bond
        fr_asset = AssetModel.objects.create(
            short_name="OAT2Y",
            full_name="French Government Bond 2 Year",
            asset_id=26,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.GOVERNMENT_BOND_RATE,
            location=LocationChoices.FR,
            maturity=2.0,
        )
        MarketPriceModel.objects.create(
            asset=fr_asset,
            date=self.price_date,
            price=2.5,
        )

        # Create EU interbank rate
        eu_interbank_asset = AssetModel.objects.create(
            short_name="ESTR",
            full_name="Euro Short-Term Rate",
            asset_id=19,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.EU,
            maturity=0.0,
        )
        MarketPriceModel.objects.create(
            asset=eu_interbank_asset,
            date=self.price_date,
            price=2.0,
        )

        # Create EU government bond
        eu_gov_asset = AssetModel.objects.create(
            short_name="EURIBOR3M",
            full_name="Euribor 3 Month",
            asset_id=22,
            asset_class=AssetClassChoices.RATES,
            asset_type=AssetTypeChoices.INTERBANK_RATE,
            location=LocationChoices.EU,
            maturity=0.25,
        )
        MarketPriceModel.objects.create(
            asset=eu_gov_asset,
            date=self.price_date,
            price=2.1,
        )

        result = get_yield_curve(
            target_date=self.price_date, location=LocationChoices.FR
        )

        assert result == [
            {"maturity": 0.0, "price": 2.0, "short_name": "ESTR"},
            {"maturity": 0.25, "price": 2.1, "short_name": "EURIBOR3M"},
            {"maturity": 2.0, "price": 2.5, "short_name": "OAT2Y"},
        ]

    def test_get_all_asset_prices_for_date_without_holidays_no_holidays(self):
        """
        GIVEN market prices for a date without any bank holidays
        WHEN getting asset prices for that date without holidays
        THEN all market prices for that date are returned
        """
        result = get_all_asset_prices_for_date_without_holidays(
            price_date=self.price_date
        )
        result_dict = [price.convert_to_dict() for price in result]

        expected = core_services.convert_query_to_dictionary_list(
            queryset=MarketPriceModel.objects.filter(date=self.price_date)
        )

        assert len(result_dict) == len(expected)
        assert result_dict == expected

    def test_get_all_asset_prices_for_date_without_holidays_with_holiday(self):
        """
        GIVEN market prices for a date where one asset has a bank holiday
        WHEN getting asset prices for that date without holidays
        THEN the holiday price is replaced with the last non-holiday price
        before or on that date
        """
        holiday_date = self.price_date
        previous_non_holiday_date = self.previous_date
        earlier_date = self.previous_date - timedelta(days=5)
        future_date = self.price_date + timedelta(days=5)

        second_asset = AssetModel.objects.create(
            short_name="SECOND_ASSET",
            full_name="Second Asset",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=earlier_date,
            price=50.0,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=previous_non_holiday_date,
            price=60.0,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=holiday_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=future_date,
            price=80.0,
        )

        result = [
            price.convert_to_dict()
            for price in get_all_asset_prices_for_date_without_holidays(
                price_date=holiday_date
            )
        ]

        assert result == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "date": holiday_date,
                "price": 100.0,
                "comment": "",
            },
            {
                "asset_id": 2,
                "asset_short_name": "SECOND_ASSET",
                "date": previous_non_holiday_date,
                "price": 60.0,
                "comment": "",
            },
        ]

    def test_get_all_asset_prices_for_date_without_holidays_multiple_holidays(self):
        """
        GIVEN market prices for a date where multiple assets have bank holidays
        WHEN getting asset prices for that date without holidays
        THEN all holiday prices are replaced with their respective last non-holiday prices
        """
        holiday_date = self.price_date
        previous_non_holiday_date = self.previous_date
        earlier_date = self.previous_date - timedelta(days=5)

        second_asset = AssetModel.objects.create(
            short_name="SECOND_ASSET",
            full_name="Second Asset",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=previous_non_holiday_date,
            price=60.0,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=holiday_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )

        third_asset = AssetModel.objects.create(
            short_name="THIRD_ASSET",
            full_name="Third Asset",
            asset_id=3,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )
        MarketPriceModel.objects.create(
            asset=third_asset,
            date=earlier_date,
            price=70.0,
        )
        MarketPriceModel.objects.create(
            asset=third_asset,
            date=holiday_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )

        result = [
            price.convert_to_dict()
            for price in get_all_asset_prices_for_date_without_holidays(
                price_date=holiday_date
            )
        ]

        assert result == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "date": holiday_date,
                "price": 100.0,
                "comment": "",
            },
            {
                "asset_id": 2,
                "asset_short_name": "SECOND_ASSET",
                "date": previous_non_holiday_date,
                "price": 60.0,
                "comment": "",
            },
            {
                "asset_id": 3,
                "asset_short_name": "THIRD_ASSET",
                "date": earlier_date,
                "price": 70.0,
                "comment": "",
            },
        ]

    def test_get_all_asset_prices_for_date_without_holidays_error_raised(self):
        """
        GIVEN an asset that only has bank holiday prices on or before the date
        WHEN getting asset prices for that date without holidays
        THEN a ValueError is raised
        """
        holiday_date = self.price_date
        future_date = self.price_date + timedelta(days=5)
        second_asset = AssetModel.objects.create(
            short_name="SECOND_ASSET",
            full_name="Second Asset",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=holiday_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=future_date,
            price=80.0,
        )

        with pytest.raises(ValueError) as exc_info:
            get_all_asset_prices_for_date_without_holidays(price_date=holiday_date)

        assert "No market price found for SECOND_ASSET without holidays" in str(
            exc_info.value
        )

    def test_get_all_asset_prices_for_date_without_holidays_empty_date(self):
        """
        GIVEN a date with no market prices
        WHEN getting asset prices for that date without holidays
        THEN an empty list is returned
        """
        empty_date = self.price_date + timedelta(days=10)

        result = get_all_asset_prices_for_date_without_holidays(price_date=empty_date)

        assert result == []

    def test_get_all_asset_prices_for_date_without_holidays_mixed_comments(self):
        """
        GIVEN market prices for a date with mixed comments
        WHEN getting asset prices for that date without holidays
        THEN only bank holiday prices are replaced, regular prices remain unchanged
        """
        holiday_date = self.price_date
        previous_non_holiday_date = self.previous_date

        second_asset = AssetModel.objects.create(
            short_name="SECOND_ASSET",
            full_name="Second Asset",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=self.location,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=previous_non_holiday_date,
            price=60.0,
        )
        MarketPriceModel.objects.create(
            asset=second_asset,
            date=holiday_date,
            price=None,
            comment=SpecialComment.BANK_HOLIDAY,
        )

        result = [
            price.convert_to_dict()
            for price in get_all_asset_prices_for_date_without_holidays(
                price_date=holiday_date
            )
        ]

        assert result == [
            {
                "asset_id": 1,
                "asset_short_name": "TEST",
                "date": holiday_date,
                "price": 100.0,
                "comment": "",
            },
            {
                "asset_id": 2,
                "asset_short_name": "SECOND_ASSET",
                "date": previous_non_holiday_date,
                "price": 60.0,
                "comment": "",
            },
        ]
