"""Tests for market recap visualization services."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from freezegun import freeze_time

from data_visualization.services.market_recap import (
    FX_MATRIX_ORDER,
    UpcomingEventGroup,
    _get_upcoming_events_from_publication_schedules,
    _get_upcoming_holidays_events,
    format_data_for_market_recap_display,
    get_fx_prices_matrix,
    _get_upcoming_events,
    group_upcoming_events_by_week,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    HolidayModel,
    LocationChoices,
    MarketPriceModel,
)


class TestMarketRecapServices(TestCase):
    """Test cases for market_recap functions."""

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


class TestGroupUpcomingEventsByWeek(TestCase):
    """Tests for ISO-week grouping of upcoming events on the market recap."""

    def test_group_upcoming_events_by_week(self):
        """
        GIVEN day-level upcoming events spanning two ISO weeks
        WHEN grouping by week
        THEN weeks are sorted and the current week is flagged
        """
        today = date(2025, 12, 16)  # Tuesday; ISO week starts 2025-12-15
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2025-12-16",
                "date_display": "2025-12-16",
                "events": [
                    {
                        "name": "This Week",
                        "location": "France",
                        "publication_date": datetime(
                            2025, 12, 16, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                    }
                ],
            },
            {
                "date": "2025-12-22",
                "date_display": "2025-12-22",
                "events": [
                    {
                        "name": "Next Week",
                        "location": "United States",
                        "publication_date": datetime(
                            2025, 12, 22, 14, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "14:00",
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert len(result) == 2
        assert result[0]["week_start"] == "2025-12-15"
        assert result[0]["is_current_week"] is True
        assert result[0]["days"][0]["date"] == "2025-12-16"
        assert result[1]["week_start"] == "2025-12-22"
        assert result[1]["is_current_week"] is False
        assert result[0]["week_label"] == "15 Dec 2025 – 19 Dec 2025"
        assert "Week of" not in result[0]["week_label"]

    def test_group_upcoming_events_focus_week_after_friday(self):
        """
        GIVEN today is Saturday and only next-week events exist
        WHEN grouping by week
        THEN the focus week is next Monday–Friday and is always included
        """
        today = date(2025, 12, 20)  # Saturday
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2025-12-22",
                "date_display": "Mon 22 Dec",
                "events": [
                    {
                        "name": "Next Week",
                        "location": "France",
                        "publication_date": datetime(
                            2025, 12, 22, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert result[0]["week_start"] == "2025-12-22"
        assert result[0]["is_current_week"] is True
        assert result[0]["week_label"] == "22 Dec 2025 – 26 Dec 2025"

    def test_group_upcoming_events_includes_empty_focus_week(self):
        """
        GIVEN no events in the focus week
        WHEN grouping by week
        THEN an empty focus week is still returned for the collapsed card
        """
        today = date(2025, 12, 16)  # Tuesday → week of 15 Dec
        upcoming: list[UpcomingEventGroup] = [
            {
                "date": "2025-12-22",
                "date_display": "Mon 22 Dec",
                "events": [
                    {
                        "name": "Later",
                        "location": "France",
                        "publication_date": datetime(
                            2025, 12, 22, 10, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "10:00",
                    }
                ],
            },
        ]
        result = group_upcoming_events_by_week(upcoming, today=today)
        assert result[0]["week_start"] == "2025-12-15"
        assert result[0]["is_current_week"] is True
        assert result[0]["days"] == []
        assert result[1]["week_start"] == "2025-12-22"


@freeze_time("2025-12-16")
class TestUpcomingEvents(TestCase):
    """Tests for market-recap upcoming event aggregation."""

    def setUp(self):
        """Set up test fixtures."""
        self.indicator = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="Test Indicator",
            name="Test Indicator Name",
            technical_name="test_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )

    @patch(
        "data_visualization.services.market_recap._get_upcoming_events_from_publication_schedules"
    )
    @patch(
        "data_visualization.services.market_recap._get_upcoming_central_bank_events"
    )
    @patch(
        "data_visualization.services.market_recap._get_upcoming_holidays_events"
    )
    def test_get_upcoming_events_success(
        self, mock_holidays, mock_cb, mock_publications
    ):
        """
        GIVEN upcoming events from different sources
        WHEN getting market recap upcoming events
        THEN all events are merged and grouped by date
        """
        event_date = datetime.now(timezone.utc) + timedelta(days=1)
        mock_publications.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": event_date,
                    "time_str": "10:00",
                }
            ]
        }
        mock_cb.return_value = {}
        mock_holidays.return_value = {}

        result = _get_upcoming_events()
        assert result == [
            {
                "date": "2025-12-17",
                "date_display": "Wed 17 Dec",
                "events": [
                    {
                        "name": "Test Indicator",
                        "location": "France",
                        "publication_date": event_date,
                        "time_str": "10:00",
                    }
                ],
            }
        ]

    @patch(
        "data_visualization.services.market_recap._get_upcoming_events_from_publication_schedules"
    )
    @patch(
        "data_visualization.services.market_recap._get_upcoming_central_bank_events"
    )
    @patch(
        "data_visualization.services.market_recap._get_upcoming_holidays_events"
    )
    def test_get_upcoming_events_merged(
        self, mock_holidays, mock_cb, mock_publications
    ):
        """
        GIVEN upcoming events from multiple sources on the same date
        WHEN getting market recap upcoming events
        THEN events are merged correctly
        """
        event_date = datetime.now(timezone.utc) + timedelta(days=1)
        holiday_date = datetime.now(timezone.utc) + timedelta(days=2)
        mock_publications.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": event_date,
                    "time_str": "10:00",
                }
            ]
        }
        mock_cb.return_value = {
            event_date.strftime("%Y-%m-%d"): [
                {
                    "name": "ECB Rates Decision",
                    "location": "Europe",
                    "publication_date": event_date,
                    "time_str": "14:00",
                }
            ]
        }
        mock_holidays.return_value = {
            holiday_date.strftime("%Y-%m-%d"): [
                {
                    "name": "Holiday",
                    "location": "Japan",
                    "publication_date": holiday_date,
                    "time_str": "HOLIDAYS",
                }
            ]
        }

        result = _get_upcoming_events()
        assert result == [
            {
                "date": "2025-12-17",
                "date_display": "Wed 17 Dec",
                "events": [
                    {
                        "name": "Test Indicator",
                        "location": "France",
                        "publication_date": event_date,
                        "time_str": "10:00",
                    },
                    {
                        "name": "ECB Rates Decision",
                        "location": "Europe",
                        "publication_date": event_date,
                        "time_str": "14:00",
                    },
                ],
            },
            {
                "date": "2025-12-18",
                "date_display": "Thu 18 Dec",
                "events": [
                    {
                        "name": "Holiday",
                        "location": "Japan",
                        "publication_date": holiday_date,
                        "time_str": "HOLIDAYS",
                    }
                ],
            },
        ]

    def test_get_upcoming_events_from_publication_schedules(self):
        """
        GIVEN publication schedules with upcoming dates
        WHEN getting upcoming events from publication schedules
        THEN events are returned correctly
        """
        today = date(2025, 12, 16)
        future_date = datetime.combine(today, time(10, 30, 0)).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=5)
        PublicationScheduleModel.objects.create(
            indicator=self.indicator,
            current_publication_date=future_date,
            next_publication_date=future_date + timedelta(days=30),
        )

        result = _get_upcoming_events_from_publication_schedules(today)
        assert result == {
            "2025-12-21": [
                {
                    "name": "Test Indicator",
                    "location": "France",
                    "publication_date": datetime(
                        2025, 12, 21, 10, 30, 0, tzinfo=timezone.utc
                    ),
                    # Stored UTC 10:30 → Europe/Paris winter (CET) 11:30
                    "time_str": "11:30",
                }
            ]
        }

    def test_get_upcoming_holidays_events(self):
        """
        GIVEN upcoming holidays
        WHEN getting upcoming holidays events
        THEN events are returned correctly
        """
        today = date(2025, 12, 16)
        HolidayModel.objects.create(
            id=1,
            name="Holiday",
            date=django_timezone.now() + timedelta(days=2),
            location=LocationChoices.JP,
        )
        result = _get_upcoming_holidays_events(today)
        assert result == {
            "2025-12-18": [
                {
                    "name": "Holiday",
                    "location": "Japan",
                    "publication_date": datetime(
                        2025, 12, 18, 0, 0, 0, tzinfo=timezone.utc
                    ),
                    "time_str": "HOLIDAYS",
                }
            ]
        }
