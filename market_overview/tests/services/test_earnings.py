"""Tests for earnings watchlist catalog, refresh, and report ingest."""

from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel
from market_overview.services.earnings import (
    EarningsWatchlistCatalogEntry,
    ingest_earnings_watchlist,
    list_earnings_watchlist_catalog_entries,
    list_earnings_watchlist_companies_for_location,
    refresh_earnings_watchlist,
)
from market_overview.services.scrapers.yahoo import (
    YahooEarningsInformation,
    YahooEarningsSnapshot,
)


class TestListEarningsWatchlistCatalogEntries(TestCase):
    """Test cases for 'list_earnings_watchlist_catalog_entries'."""

    def test_list_earnings_watchlist_catalog_entries(self):
        """
        GIVEN the static earnings watchlist JSON
        WHEN list_earnings_watchlist_catalog_entries is called for SPX
        THEN the thirty S&P names are returned with Yahoo tickers
        """
        entries = list_earnings_watchlist_catalog_entries(EquityIndexChoices.SPX)

        assert len(entries) == 30
        assert entries[0] == EarningsWatchlistCatalogEntry(
            company="Nvidia",
            ticker="NVDA",
            equity_index=EquityIndexChoices.SPX,
        )
        assert entries[-1] == EarningsWatchlistCatalogEntry(
            company="Home Depot",
            ticker="HD",
            equity_index=EquityIndexChoices.SPX,
        )


class TestRefreshEarningsWatchlist(TestCase):
    """Test cases for 'refresh_earnings_watchlist'."""

    @patch("market_overview.services.earnings.WEIGHT_SCRAP_MAP", new_callable=dict)
    @patch("market_overview.services.earnings.list_earnings_watchlist_catalog_entries")
    @patch("market_overview.services.earnings.get_yahoo_finance_earnings_snapshot")
    def test_refresh_earnings_watchlist_updates_upcoming_and_weights(
        self,
        mock_get_snapshot,
        mock_list_catalog,
        mock_weight_scrap_map,
    ):
        """
        GIVEN a stored company with current/previous results and Yahoo upcoming + weights
        WHEN refresh_earnings_watchlist is called for SPX
        THEN upcoming and weight update and current/previous stay unchanged
        """
        EarningsWatchlistModel.objects.create(
            company="Apple",
            ticker="AAPL",
            equity_index=EquityIndexChoices.SPX.value,
            weight_pct=1.0,
            upcoming_announcement_datetime=datetime(
                2026, 10, 30, 20, 30, tzinfo=timezone.utc
            ),
            upcoming_eps_expected=2.91,
            current_reporting_period_end=date(2026, 6, 30),
            current_eps=1.57,
            previous_reporting_period_end=date(2026, 3, 31),
            previous_eps=1.20,
        )
        mock_list_catalog.return_value = [
            EarningsWatchlistCatalogEntry(
                company="Apple",
                ticker="AAPL",
                equity_index=EquityIndexChoices.SPX,
            )
        ]
        mock_get_snapshot.return_value = YahooEarningsSnapshot(
            upcoming=YahooEarningsInformation(
                announcement_datetime=datetime(2027, 1, 28, 21, 0, tzinfo=timezone.utc),
                reporting_period_end=date(2026, 12, 31),
                is_reported=False,
                eps_actual=None,
                eps_expected=3.05,
                revenue_expected=160_000_000_000.0,
                revenue=None,
                operating_income=None,
                gross_profit=None,
                ebitda=None,
            ),
            current=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 9, 30),
                is_reported=True,
                eps_actual=2.10,
                eps_expected=None,
                revenue_expected=None,
                revenue=114_000_000_000.0,
                operating_income=None,
                gross_profit=None,
                ebitda=None,
            ),
            previous=None,
        )
        mock_weight_scrap_map[EquityIndexChoices.SPX] = lambda: {"AAPL": 7.72}

        result = refresh_earnings_watchlist(
            date(2026, 10, 30),
            EquityIndexChoices.SPX,
        )

        apple = EarningsWatchlistModel.objects.get(ticker="AAPL")
        assert result == {
            "as_of": "2026-10-30",
            "earnings_results": [
                {
                    "equity_index": "SPX",
                    "companies_updated": 1,
                    "tickers_failed": [],
                    "as_of": "2026-10-30",
                }
            ],
            "weight_results": [
                {
                    "equity_index": "SPX",
                    "companies_updated": 1,
                    "tickers_failed": [],
                    "as_of": "2026-10-30",
                }
            ],
            "tickers_failed": [],
        }
        assert apple.upcoming_announcement_datetime == datetime(
            2027, 1, 28, 21, 0, tzinfo=timezone.utc
        )
        assert apple.upcoming_eps_expected == 3.05
        assert apple.weight_pct == 7.72
        assert apple.current_reporting_period_end == date(2026, 6, 30)
        assert apple.current_eps == 1.57
        assert apple.previous_reporting_period_end == date(2026, 3, 31)
        assert apple.previous_eps == 1.20


class TestIngestEarningsWatchlist(TestCase):
    """Test cases for 'ingest_earnings_watchlist'."""

    @patch("market_overview.services.earnings.WEIGHT_SCRAP_MAP", new_callable=dict)
    @patch("market_overview.services.earnings.list_earnings_watchlist_catalog_entries")
    @patch("market_overview.services.earnings.get_yahoo_finance_earnings_snapshot")
    def test_ingest_seeds_upcoming_current_previous(
        self,
        mock_get_snapshot,
        mock_list_catalog,
        mock_weight_scrap_map,
    ):
        """
        GIVEN one catalog company and a Yahoo upcoming/current/previous snapshot
        WHEN ingest runs for the first time
        THEN upcoming, current, and previous information are written from Yahoo
        """
        mock_list_catalog.return_value = [
            EarningsWatchlistCatalogEntry(
                company="Apple",
                ticker="AAPL",
                equity_index=EquityIndexChoices.SPX,
            )
        ]
        mock_get_snapshot.return_value = YahooEarningsSnapshot(
            upcoming=YahooEarningsInformation(
                announcement_datetime=datetime(
                    2026, 10, 30, 20, 30, tzinfo=timezone.utc
                ),
                reporting_period_end=date(2026, 9, 30),
                is_reported=False,
                eps_actual=None,
                eps_expected=2.91,
                revenue_expected=156_000_000_000.0,
                revenue=None,
                operating_income=None,
                gross_profit=None,
                ebitda=None,
            ),
            current=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 6, 30),
                is_reported=True,
                eps_actual=1.57,
                eps_expected=1.43,
                revenue_expected=None,
                revenue=94_000_000_000.0,
                operating_income=28_000_000_000.0,
                gross_profit=44_000_000_000.0,
                ebitda=32_000_000_000.0,
            ),
            previous=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 3, 31),
                is_reported=True,
                eps_actual=1.20,
                eps_expected=1.10,
                revenue_expected=None,
                revenue=80_000_000_000.0,
                operating_income=20_000_000_000.0,
                gross_profit=40_000_000_000.0,
                ebitda=25_000_000_000.0,
            ),
        )
        mock_weight_scrap_map[EquityIndexChoices.SPX] = lambda: {"AAPL": 7.0}

        result = ingest_earnings_watchlist(
            as_of=date(2026, 10, 1),
            equity_index=EquityIndexChoices.SPX,
        )

        apple = EarningsWatchlistModel.objects.get(ticker="AAPL")
        assert result["earnings_results"] == [
            {
                "equity_index": "SPX",
                "companies_updated": 1,
                "tickers_failed": [],
                "as_of": "2026-10-01",
            }
        ]
        assert apple.weight_pct == 7.0

        assert apple.upcoming_announcement_datetime == datetime(
            2026, 10, 30, 20, 30, tzinfo=timezone.utc
        )
        assert apple.upcoming_eps_expected == 2.91
        assert apple.upcoming_revenue_expected == 156_000_000_000.0
        assert apple.current_reporting_period_end == date(2026, 6, 30)
        assert apple.current_eps == 1.57
        assert apple.previous_reporting_period_end == date(2026, 3, 31)
        assert apple.previous_eps == 1.20

    @patch("market_overview.services.earnings.WEIGHT_SCRAP_MAP", new_callable=dict)
    @patch("market_overview.services.earnings.list_earnings_watchlist_catalog_entries")
    @patch("market_overview.services.earnings.get_yahoo_finance_earnings_snapshot")
    def test_ingest_updates_exp_daily_without_rolling(
        self,
        mock_get_snapshot,
        mock_list_catalog,
        mock_weight_scrap_map,
    ):
        """
        GIVEN a stored company and Yahoo showing newer upcoming and different reports
        WHEN ingest runs on a non-T+1 as_of
        THEN only upcoming_* fields refresh; current_* and previous_* stay unchanged
        """
        mock_weight_scrap_map[EquityIndexChoices.SPX] = lambda: {"AAPL": 7.0}
        EarningsWatchlistModel.objects.create(
            company="Apple",
            ticker="AAPL",
            equity_index=EquityIndexChoices.SPX.value,
            upcoming_announcement_datetime=datetime(
                2026, 10, 30, 20, 30, tzinfo=timezone.utc
            ),
            upcoming_reporting_period_end=date(2026, 9, 30),
            upcoming_eps_expected=2.91,
            upcoming_revenue_expected=156_000_000_000.0,
            current_reporting_period_end=date(2026, 6, 30),
            current_eps=1.57,
            current_eps_expected=1.43,
            current_revenue=94_000_000_000.0,
            previous_reporting_period_end=date(2026, 3, 31),
            previous_eps=1.20,
        )
        mock_list_catalog.return_value = [
            EarningsWatchlistCatalogEntry(
                company="Apple",
                ticker="AAPL",
                equity_index=EquityIndexChoices.SPX,
            )
        ]
        mock_get_snapshot.return_value = YahooEarningsSnapshot(
            upcoming=YahooEarningsInformation(
                announcement_datetime=datetime(2027, 1, 28, 21, 0, tzinfo=timezone.utc),
                reporting_period_end=date(2026, 12, 31),
                is_reported=False,
                eps_actual=None,
                eps_expected=3.05,
                revenue_expected=160_000_000_000.0,
                revenue=None,
                operating_income=None,
                gross_profit=None,
                ebitda=None,
            ),
            current=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 9, 30),
                is_reported=True,
                eps_actual=2.10,
                eps_expected=None,
                revenue_expected=None,
                revenue=114_000_000_000.0,
                operating_income=35_000_000_000.0,
                gross_profit=54_000_000_000.0,
                ebitda=39_000_000_000.0,
            ),
            previous=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 6, 30),
                is_reported=True,
                eps_actual=1.57,
                eps_expected=1.43,
                revenue_expected=None,
                revenue=94_000_000_000.0,
                operating_income=28_000_000_000.0,
                gross_profit=44_000_000_000.0,
                ebitda=32_000_000_000.0,
            ),
        )

        ingest_earnings_watchlist(
            as_of=date(2026, 10, 15),
            equity_index=EquityIndexChoices.SPX,
        )

        apple = EarningsWatchlistModel.objects.get(ticker="AAPL")
        assert apple.upcoming_announcement_datetime == datetime(
            2027, 1, 28, 21, 0, tzinfo=timezone.utc
        )
        assert apple.upcoming_reporting_period_end == date(2026, 12, 31)
        assert apple.upcoming_eps_expected == 3.05
        assert apple.upcoming_revenue_expected == 160_000_000_000.0
        assert apple.current_reporting_period_end == date(2026, 6, 30)
        assert apple.current_eps == 1.57
        assert apple.previous_reporting_period_end == date(2026, 3, 31)
        assert apple.previous_eps == 1.20

    @patch("market_overview.services.earnings.WEIGHT_SCRAP_MAP", new_callable=dict)
    @patch("market_overview.services.earnings.list_earnings_watchlist_catalog_entries")
    @patch("market_overview.services.earnings.get_yahoo_finance_earnings_snapshot")
    def test_ingest_rolls_on_upcoming_t_plus_one_as_of(
        self,
        mock_get_snapshot,
        mock_list_catalog,
        mock_weight_scrap_map,
    ):
        """
        GIVEN stored upcoming call date equal to as_of
        WHEN ingest runs
        THEN current rolls to previous and upcoming rolls into current
        """
        mock_weight_scrap_map[EquityIndexChoices.SPX] = lambda: {"AAPL": 7.0}
        EarningsWatchlistModel.objects.create(
            company="Apple",
            ticker="AAPL",
            equity_index=EquityIndexChoices.SPX.value,
            upcoming_announcement_datetime=datetime(
                2026, 10, 30, 20, 30, tzinfo=timezone.utc
            ),
            upcoming_reporting_period_end=date(2026, 9, 30),
            upcoming_eps_expected=2.91,
            upcoming_revenue_expected=156_000_000_000.0,
            current_reporting_period_end=date(2026, 6, 30),
            current_eps=1.57,
            current_eps_expected=1.43,
            current_revenue=94_000_000_000.0,
            current_operating_income=28_000_000_000.0,
            current_gross_profit=44_000_000_000.0,
            current_ebitda=32_000_000_000.0,
        )
        mock_list_catalog.return_value = [
            EarningsWatchlistCatalogEntry(
                company="Apple",
                ticker="AAPL",
                equity_index=EquityIndexChoices.SPX,
            )
        ]
        mock_get_snapshot.return_value = YahooEarningsSnapshot(
            upcoming=YahooEarningsInformation(
                announcement_datetime=datetime(2027, 1, 28, 21, 0, tzinfo=timezone.utc),
                reporting_period_end=None,
                is_reported=False,
                eps_actual=None,
                eps_expected=3.05,
                revenue_expected=160_000_000_000.0,
                revenue=None,
                operating_income=None,
                gross_profit=None,
                ebitda=None,
            ),
            current=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 9, 30),
                is_reported=True,
                eps_actual=2.10,
                eps_expected=None,
                revenue_expected=None,
                revenue=114_000_000_000.0,
                operating_income=35_000_000_000.0,
                gross_profit=54_000_000_000.0,
                ebitda=39_000_000_000.0,
            ),
            previous=YahooEarningsInformation(
                announcement_datetime=None,
                reporting_period_end=date(2026, 6, 30),
                is_reported=True,
                eps_actual=1.57,
                eps_expected=1.43,
                revenue_expected=None,
                revenue=94_000_000_000.0,
                operating_income=28_000_000_000.0,
                gross_profit=44_000_000_000.0,
                ebitda=32_000_000_000.0,
            ),
        )

        ingest_earnings_watchlist(
            as_of=date(2026, 10, 30),
            equity_index=EquityIndexChoices.SPX,
        )

        apple = EarningsWatchlistModel.objects.get(ticker="AAPL")
        assert apple.previous_reporting_period_end == date(2026, 6, 30)
        assert apple.previous_eps == 1.57
        assert apple.previous_eps_expected == 1.43
        assert apple.previous_revenue == 94_000_000_000.0
        assert apple.current_reporting_period_end == date(2026, 9, 30)
        assert apple.current_eps_expected == 2.91
        assert apple.current_revenue_expected == 156_000_000_000.0
        assert apple.current_eps == 2.10
        assert apple.current_revenue == 114_000_000_000.0
        assert apple.upcoming_announcement_datetime == datetime(
            2027, 1, 28, 21, 0, tzinfo=timezone.utc
        )
        assert apple.upcoming_eps_expected == 3.05


class TestListEarningsWatchlistCompaniesForLocation(TestCase):
    """Test cases for 'list_earnings_watchlist_companies_for_location'."""

    @patch("market_overview.services.earnings.set_cached_earnings_watchlist_companies")
    @patch("market_overview.services.earnings.get_cached_earnings_watchlist_companies")
    def test_list_earnings_watchlist_companies_for_location(
        self,
        mock_get_cached_earnings_watchlist_companies,
        mock_set_cached_earnings_watchlist_companies,
    ):
        """
        GIVEN two US watchlist rows with different weights
        WHEN list_earnings_watchlist_companies_for_location is called for US
        THEN companies are returned heaviest-first with upcoming/current/previous
        """
        mock_get_cached_earnings_watchlist_companies.return_value = None

        EarningsWatchlistModel.objects.bulk_create(
            [
                EarningsWatchlistModel(
                    company="Apple",
                    ticker="AAPL",
                    equity_index=EquityIndexChoices.SPX.value,
                    weight_pct=7.0,
                    upcoming_announcement_datetime=datetime(
                        2027, 1, 28, 21, 0, tzinfo=timezone.utc
                    ),
                    upcoming_eps_expected=2.91,
                    upcoming_revenue_expected=156_000_000_000.0,
                    current_reporting_period_end=date(2026, 9, 30),
                    current_eps=2.10,
                    current_eps_expected=1.98,
                    previous_reporting_period_end=date(2026, 6, 30),
                    previous_eps=1.57,
                    previous_eps_expected=1.43,
                ),
                EarningsWatchlistModel(
                    company="Nvidia",
                    ticker="NVDA",
                    equity_index=EquityIndexChoices.SPX.value,
                    weight_pct=8.0,
                    upcoming_announcement_datetime=datetime(
                        2026, 11, 19, 21, 0, tzinfo=timezone.utc
                    ),
                    upcoming_eps_expected=1.00,
                    current_reporting_period_end=date(2026, 7, 31),
                    current_eps=1.05,
                    current_eps_expected=1.00,
                    current_revenue=50_000_000_000.0,
                    current_operating_income=30_000_000_000.0,
                    current_gross_profit=35_000_000_000.0,
                    current_ebitda=32_000_000_000.0,
                ),
            ]
        )

        result = list_earnings_watchlist_companies_for_location(LocationChoices.US)

        assert result == [
            {
                "company": "Nvidia",
                "ticker": "NVDA",
                "equity_index": "SPX",
                "weight_pct": 8.0,
                "upcoming": {
                    "announcement_datetime": "2026-11-19T21:00:00+00:00",
                    "reporting_period_end": None,
                    "eps_expected": 1.0,
                    "revenue_expected": None,
                },
                "current": {
                    "reporting_period_end": "2026-07-31",
                    "eps": 1.05,
                    "eps_expected": 1.0,
                    "revenue_expected": None,
                    "revenue": 50_000_000_000.0,
                    "operating_income": 30_000_000_000.0,
                    "gross_profit": 35_000_000_000.0,
                    "ebitda": 32_000_000_000.0,
                },
                "previous": {
                    "reporting_period_end": None,
                    "eps": None,
                    "eps_expected": None,
                    "revenue_expected": None,
                    "revenue": None,
                    "operating_income": None,
                    "gross_profit": None,
                    "ebitda": None,
                },
            },
            {
                "company": "Apple",
                "ticker": "AAPL",
                "equity_index": "SPX",
                "weight_pct": 7.0,
                "upcoming": {
                    "announcement_datetime": "2027-01-28T21:00:00+00:00",
                    "reporting_period_end": None,
                    "eps_expected": 2.91,
                    "revenue_expected": 156_000_000_000.0,
                },
                "current": {
                    "reporting_period_end": "2026-09-30",
                    "eps": 2.1,
                    "eps_expected": 1.98,
                    "revenue_expected": None,
                    "revenue": None,
                    "operating_income": None,
                    "gross_profit": None,
                    "ebitda": None,
                },
                "previous": {
                    "reporting_period_end": "2026-06-30",
                    "eps": 1.57,
                    "eps_expected": 1.43,
                    "revenue_expected": None,
                    "revenue": None,
                    "operating_income": None,
                    "gross_profit": None,
                    "ebitda": None,
                },
            },
        ]
        mock_set_cached_earnings_watchlist_companies.assert_called_once_with(
            LocationChoices.US,
            result,
        )
