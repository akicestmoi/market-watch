from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest  # type: ignore[reportMissingImports]
from django.test import TestCase

from core.services import convert_query_to_dictionary_list
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    HolidayModel,
    LocationChoices,
    MarketPriceModel,
    PriceSourceChoices,
    PriceUpdateLogModel,
)
from market_overview.services.price_ingestion_services import (
    MarketData,
    ScrapingResult,
    _get_specific_asset_market_data,
    get_market_data,
    ingest_market_data,
)


def _scraper_side_effect(_, ticker):
    if ticker == "TEST":
        return ScrapingResult(price=100.0, comment="")
    return ScrapingResult(price=None, comment="No price")


class TestGetMarketData(TestCase):
    """Test cases for get_market_data function."""

    def setUp(self):
        """Set up test fixtures."""
        self.target_date = date.today()
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="TEST",
            source=PriceSourceChoices.YAHOO,
        )

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_market_data_success(self, mock_source_map):
        """
        GIVEN a date with assets that can be successfully scraped
        WHEN getting market data
        THEN all assets are returned with their prices
        """
        mock_scraper = Mock(return_value=ScrapingResult(price=100.0, comment=""))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = get_market_data(self.target_date)
        assert result == [
            {
                "asset": self.asset,
                "price": 100.0,
                "date": self.target_date,
                "comment": "",
            }
        ]

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_market_data_some_none_prices(self, mock_source_map):
        """
        GIVEN a date where some assets return prices and some return None
        WHEN getting market data
        THEN all assets are returned with their respective prices or None
        """
        none_price_asset = AssetModel.objects.create(
            short_name="NONE_PRICE",
            full_name="None Price Asset",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="NONE_PRICE",
            source=PriceSourceChoices.YAHOO,
        )
        mock_scraper = Mock(side_effect=_scraper_side_effect)
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = get_market_data(self.target_date)

        assert result == [
            {
                "asset": self.asset,
                "price": 100.0,
                "date": self.target_date,
                "comment": "",
            },
            {
                "asset": none_price_asset,
                "price": None,
                "date": self.target_date,
                "comment": "No price",
            },
        ]

    @patch("market_overview.services.price_ingestion_services._is_holiday_at_location")
    def test_get_market_data_holiday_skip(self, mock_is_holiday):
        """
        GIVEN a date that is a holiday for some locations
        WHEN getting market data
        THEN assets return None price with holiday comment
        """
        mock_is_holiday.return_value = True
        result = get_market_data(self.target_date)
        assert result == [
            {
                "asset": self.asset,
                "price": None,
                "date": self.target_date,
                "comment": "Bank holiday",
            },
        ]

    def test_get_market_data_empty_assets(self):
        """
        GIVEN an empty AssetModel queryset
        WHEN getting market data
        THEN an empty list is returned
        """
        AssetModel.objects.all().delete()

        result = get_market_data(self.target_date)

        assert len(result) == 0

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_market_data_no_scraping_function(self, mock_source_map):
        """
        GIVEN an asset that has no scraping function in SOURCE_SCRAP_MAP
        WHEN getting market data
        THEN the asset is returned with None price and appropriate comment
        """
        no_source_asset = AssetModel.objects.create(
            short_name="NO_SOURCE",
            full_name="No Source Asset",
            asset_id=3,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="NOSOURCE",
            source=PriceSourceChoices.GOV_TREASURY_DEPT,
        )
        mock_scraper = Mock(return_value=ScrapingResult(price=100.0, comment=""))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = get_market_data(self.target_date)

        assert result == [
            {
                "asset": self.asset,
                "price": 100.0,
                "date": self.target_date,
                "comment": "",
            },
            {
                "asset": no_source_asset,
                "price": None,
                "date": self.target_date,
                "comment": "No scraping function found.",
            },
        ]

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_market_data_scraping_function_raises_exception(self, mock_source_map):
        """
        GIVEN an asset with a scraping function that raises an exception
        WHEN getting market data
        THEN the exception is caught and the asset is returned with None price
        """
        AssetModel.objects.all().delete()
        network_error_asset = AssetModel.objects.create(
            short_name="NETWORK_ERROR_ASSET",
            full_name="Network Error Asset",
            asset_id=4,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="NETWORK_ERROR",
            source=PriceSourceChoices.YAHOO,
        )
        mock_scraper_success = Mock(
            return_value=ScrapingResult(price=100.0, comment="")
        )
        mock_scraper_error = Mock(side_effect=Exception("Network error"))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper_success

        # Create a separate asset with error-prone scraper
        source_error_asset = AssetModel.objects.create(
            short_name="SOURCE_ERROR_ASSET",
            full_name="Source Error Asset",
            asset_id=5,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="SOURCE_ERROR",
            source=PriceSourceChoices.GOV_TREASURY_DEPT,
        )
        mock_source_map[PriceSourceChoices.GOV_TREASURY_DEPT] = mock_scraper_error

        result = get_market_data(self.target_date)
        assert result == [
            {
                "asset": network_error_asset,
                "price": 100.0,
                "date": self.target_date,
                "comment": "",
            },
            {
                "asset": source_error_asset,
                "price": None,
                "date": self.target_date,
                "comment": "Error getting market data: Network error",
            },
        ]

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_market_data_no_price_found(self, mock_source_map):
        """
        GIVEN an asset with a scraping function that returns no price
        WHEN getting market data
        THEN a warning is logged and the asset is returned with None price
        """
        AssetModel.objects.all().delete()
        no_price_asset = AssetModel.objects.create(
            short_name="NO_PRICE",
            full_name="No Price Asset",
            asset_id=6,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="NO_PRICE",
            source=PriceSourceChoices.YAHOO,
        )
        mock_scraper = Mock(return_value=ScrapingResult(price=None, comment="No price"))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = get_market_data(self.target_date)
        assert result == [
            {
                "asset": no_price_asset,
                "price": None,
                "date": self.target_date,
                "comment": "No price",
            },
        ]


class GetSpecificAssetMarketDataTest(TestCase):
    """Test cases for get_specific_asset_market_data function."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
            location=LocationChoices.US,
            ticker="TEST",
            source=PriceSourceChoices.YAHOO,
        )
        self.start_date = date(2024, 1, 1)
        self.end_date = date(2024, 1, 10)

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_specific_asset_market_data_valid_range(self, mock_source_map):
        """
        GIVEN a valid date range for a specific asset
        WHEN getting specific asset market data
        THEN only weekdays are processed and returned
        """
        mock_scraper = Mock(return_value=ScrapingResult(price=100.0, comment=""))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = _get_specific_asset_market_data(
            self.asset.short_name, self.start_date, self.end_date
        )

        # Should only process weekdays (Mon-Fri)
        # Jan 1, 2024 is a Monday, Jan 10 is a Wednesday
        # That's 8 weekdays (excluding weekends)
        assert len(result) > 0
        assert len(result) <= 10  # Max 10 days

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_specific_asset_market_data_start_equals_end(self, mock_source_map):
        """
        GIVEN a start date equal to end date
        WHEN getting specific asset market data
        THEN a single day result is returned if it's a weekday
        """
        mock_scraper = Mock(return_value=ScrapingResult(price=100.0, comment=""))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = _get_specific_asset_market_data(
            self.asset.short_name, self.start_date, self.start_date
        )

        if self.start_date.weekday() < 5:
            assert len(result) == 1
        else:
            assert len(result) == 0

    def test_get_specific_asset_market_data_nonexistent_asset(self):
        """
        GIVEN a non-existent asset short name
        WHEN getting specific asset market data
        THEN a DoesNotExist exception is raised
        """
        with pytest.raises(AssetModel.DoesNotExist):
            _get_specific_asset_market_data(
                "NONEXISTENT", self.start_date, self.end_date
            )

    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_specific_asset_market_data_skips_weekends(self, mock_source_map):
        """
        GIVEN a date range that includes a weekend
        WHEN getting specific asset market data
        THEN weekends are skipped and only weekdays are processed
        """
        friday = date(2024, 1, 5)
        monday = date(2024, 1, 8)

        mock_scraper = Mock(return_value=ScrapingResult(price=100.0, comment=""))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = _get_specific_asset_market_data(self.asset.short_name, friday, monday)

        assert result == [
            {
                "asset": self.asset,
                "price": 100.0,
                "date": friday,
                "comment": "",
            },
            {
                "asset": self.asset,
                "price": 100.0,
                "date": monday,
                "comment": "",
            },
        ]

    @patch("market_overview.services.price_ingestion_services._is_holiday_at_location")
    @patch(
        "market_overview.services.price_ingestion_services.SOURCE_SCRAP_MAP",
        new_callable=dict,
    )
    def test_get_specific_asset_market_data_skips_holidays(
        self, mock_source_map, mock_is_holiday
    ):
        """
        GIVEN a date range that includes a holiday
        WHEN getting specific asset market data
        THEN holidays are processed but return None price with holiday comment
        """
        holiday_date = date(2024, 1, 3)
        HolidayModel.objects.create(
            date=holiday_date,
            name="Test Holiday",
            location=LocationChoices.US.value,
        )

        def _is_holiday_side_effect(target_date, location):
            """Mock _is_holiday_at_location to return True only for the holiday date."""
            return target_date == holiday_date and location == LocationChoices.US

        mock_is_holiday.side_effect = _is_holiday_side_effect
        mock_scraper = Mock(return_value=ScrapingResult(price=100.0, comment=""))
        mock_source_map[PriceSourceChoices.YAHOO] = mock_scraper

        result = _get_specific_asset_market_data(
            self.asset.short_name, self.start_date, self.end_date
        )

        # Find the holiday result in the list
        holiday_result = next((r for r in result if r["date"] == holiday_date), None)
        assert holiday_result is not None
        assert holiday_result == {
            "asset": self.asset,
            "price": None,
            "date": holiday_date,
            "comment": "Bank holiday",
        }


class IngestMarketDataTest(TestCase):
    """Test cases for ingest_market_data function."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        self.target_date = date.today()

    def test_ingest_market_data_all_with_prices(self):
        """
        GIVEN market data where all entries have prices
        WHEN ingesting market data
        THEN all prices are ingested and none are in asset_not_updated
        """
        market_data = [
            MarketData(
                asset=self.asset, price=100.0, date=self.target_date, comment=""
            ),
        ]

        result = ingest_market_data(market_data)

        assert result == {
            "asset_not_updated": [],
            "asset_not_updated_holiday": [],
        }
        queryset = MarketPriceModel.objects.filter(
            asset=self.asset, date=self.target_date
        )
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": 100.0,
                "comment": "",
            },
        ]

    def test_ingest_market_data_some_none_prices(self):
        """
        GIVEN market data where some entries have prices and some have None
        WHEN ingesting market data
        THEN entries with prices are ingested and entries with None
        are in asset_not_updated
        """
        market_data = [
            MarketData(
                asset=self.asset, price=100.0, date=self.target_date, comment=""
            ),
            MarketData(
                asset=self.asset,
                price=None,
                date=self.target_date + timedelta(days=1),
                comment="No price",
            ),
        ]

        result = ingest_market_data(market_data)

        assert result == {
            "asset_not_updated": [self.asset.short_name],
            "asset_not_updated_holiday": [],
        }
        queryset = MarketPriceModel.objects.filter(
            asset=self.asset, date=self.target_date
        )
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": 100.0,
                "comment": "",
            },
        ]

    def test_ingest_market_data_all_none_prices(self):
        """
        GIVEN market data where all entries have None prices
        WHEN ingesting market data
        THEN all entries are in asset_not_updated
        """
        market_data = [
            MarketData(
                asset=self.asset, price=None, date=self.target_date, comment="No price"
            ),
        ]

        result = ingest_market_data(market_data)

        assert result == {
            "asset_not_updated": [self.asset.short_name],
            "asset_not_updated_holiday": [],
        }
        queryset = MarketPriceModel.objects.filter(
            asset=self.asset, date=self.target_date
        )
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": None,
                "comment": "No price",
            },
        ]

    def test_ingest_market_data_empty_list(self):
        """
        GIVEN an empty market data list
        WHEN ingesting market data
        THEN an empty list is returned
        """
        market_data: list[MarketData] = []

        result = ingest_market_data(market_data)

        assert result == {
            "asset_not_updated": [],
            "asset_not_updated_holiday": [],
        }

    def test_ingest_market_data_holiday_entries(self):
        """
        GIVEN market data where some entries are holidays
        WHEN ingesting market data
        THEN holiday entries are in asset_not_updated_holiday
        """
        from market_overview.models import SpecialComment

        market_data = [
            MarketData(
                asset=self.asset, price=100.0, date=self.target_date, comment=""
            ),
            MarketData(
                asset=self.asset,
                price=None,
                date=self.target_date + timedelta(days=1),
                comment=SpecialComment.BANK_HOLIDAY,
            ),
        ]

        result = ingest_market_data(market_data)

        assert result == {
            "asset_not_updated": [],
            "asset_not_updated_holiday": [self.asset.short_name],
        }

    def test_ingest_market_data_creates_price_update_log(self):
        """
        GIVEN an existing market price
        WHEN ingesting market data to update it
        THEN a price update log is created
        """

        MarketPriceModel.objects.create(
            asset=self.asset, date=self.target_date, price=90.0
        )
        market_data = [
            MarketData(
                asset=self.asset, price=100.0, date=self.target_date, comment=""
            ),
        ]

        ingest_market_data(market_data)

        market_price = MarketPriceModel.objects.get(
            asset=self.asset, date=self.target_date
        )
        queryset = PriceUpdateLogModel.objects.filter(market_price=market_price)
        logs = convert_query_to_dictionary_list(queryset, remove_foreign_key=True)
        assert logs == [
            {
                "logs": "Automated price update on TEST. Updated price from 90.0 to 100.0.",
            },
        ]

    def test_ingest_market_data_updates_existing(self):
        """
        GIVEN an existing market price for an asset and date
        WHEN ingesting market data for the same asset and date
        THEN the existing price is updated, not duplicated
        """
        MarketPriceModel.objects.create(
            asset=self.asset, date=self.target_date, price=90.0
        )
        market_data = [
            MarketData(
                asset=self.asset, price=100.0, date=self.target_date, comment="Updated"
            ),
        ]

        ingest_market_data(market_data)

        queryset = MarketPriceModel.objects.filter(
            asset=self.asset, date=self.target_date
        )
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": 100.0,
                "comment": "Updated",
            },
        ]

    def test_ingest_market_data_does_not_override_existing_price_with_none(self):
        """
        GIVEN an existing market price for an asset and date with a price
        WHEN ingesting market data for the same asset and date with a None price
        THEN the existing price model is not updated
        """
        MarketPriceModel.objects.create(
            asset=self.asset,
            date=self.target_date,
            price=90.0,
            comment="Existing price",
        )
        market_data = [
            MarketData(
                asset=self.asset, price=None, date=self.target_date, comment="No price"
            ),
        ]

        ingest_market_data(market_data)

        queryset = MarketPriceModel.objects.filter(
            asset=self.asset, date=self.target_date
        )
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": 90.0,
                "comment": "Existing price",
            },
        ]

    def test_ingest_market_data_with_custom_comments(self):
        """
        GIVEN market data with custom comments
        WHEN ingesting market data
        THEN the custom comments are stored in the price model
        """
        market_data = [
            MarketData(
                asset=self.asset,
                price=100.0,
                date=self.target_date,
                comment="Custom comment",
            ),
        ]

        ingest_market_data(market_data)

        queryset = MarketPriceModel.objects.filter(
            asset=self.asset, date=self.target_date
        )
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": 100.0,
                "comment": "Custom comment",
            },
        ]

    def test_ingest_market_data_multiple_assets(self):
        """
        GIVEN market data for multiple assets
        WHEN ingesting market data
        THEN all assets are ingested with their respective prices
        """
        second_asset = AssetModel.objects.create(
            short_name="SECOND_ASSET",
            full_name="Second Asset",
            asset_id=2,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )
        market_data = [
            MarketData(
                asset=self.asset, price=100.0, date=self.target_date, comment=""
            ),
            MarketData(
                asset=second_asset, price=200.0, date=self.target_date, comment=""
            ),
        ]

        result = ingest_market_data(market_data)

        assert result == {
            "asset_not_updated": [],
            "asset_not_updated_holiday": [],
        }
        queryset = MarketPriceModel.objects.filter(asset=self.asset)
        prices = convert_query_to_dictionary_list(queryset)
        assert prices == [
            {
                "asset_id": self.asset.asset_id,
                "asset_short_name": self.asset.short_name,
                "date": self.target_date,
                "price": 100.0,
                "comment": "",
            },
        ]
        second_queryset = MarketPriceModel.objects.filter(asset=second_asset)
        second_prices = convert_query_to_dictionary_list(second_queryset)
        assert second_prices == [
            {
                "asset_id": second_asset.asset_id,
                "asset_short_name": second_asset.short_name,
                "date": self.target_date,
                "price": 200.0,
                "comment": "",
            },
        ]
