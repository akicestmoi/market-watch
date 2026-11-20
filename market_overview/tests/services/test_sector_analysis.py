"""Tests for sector-analysis catalog aggregation and ingestion."""

from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from market_overview.models.common import EquityIndexChoices
from market_overview.models.sector_analysis import IndexSubsectorDailyMoveModel
from market_overview.services.sector_analysis import (
    SingleNameCatalogEntry,
    _aggregate_subsector_day_moves,
    _SingleNameDayInput,
    ingest_equity_index_subsector_daily_moves,
    ingest_equity_index_subsector_daily_moves_for_date_range,
)


class TestAggregateSubsectorDayMoves(TestCase):
    """Test cases for '_aggregate_subsector_day_moves'."""

    def test_aggregate_subsector_day_moves(self):
        """
        GIVEN two names in one subsector and one name in another
        WHEN '_aggregate_subsector_day_moves' is called
        THEN weight, return, contribution, and top movers match the formulas
        """
        day_inputs = [
            _SingleNameDayInput(
                company="Soft A",
                ticker="SA",
                sector="Technology",
                subsector="Software",
                weight=10.0,
                daily_return=2.0,
            ),
            _SingleNameDayInput(
                company="Soft B",
                ticker="SB",
                sector="Technology",
                subsector="Software",
                weight=30.0,
                daily_return=-1.0,
            ),
            _SingleNameDayInput(
                company="Bank A",
                ticker="BA",
                sector="Financials",
                subsector="Banks",
                weight=20.0,
                daily_return=1.5,
            ),
        ]

        result = _aggregate_subsector_day_moves(day_inputs)

        assert [
            {
                "sector": item.sector,
                "subsector": item.subsector,
                "weight": round(item.weight, 6),
                "daily_return": round(item.daily_return, 6),
                "contribution": round(item.contribution, 6),
                "top_movers": [
                    {
                        "company": mover["company"],
                        "ticker": mover["ticker"],
                        "weight": round(mover["weight"], 6),
                        "daily_return": round(mover["daily_return"], 6),
                        "contribution": round(mover["contribution"], 6),
                    }
                    for mover in item.top_movers
                ],
            }
            for item in result
        ] == [
            {
                "sector": "Financials",
                "subsector": "Banks",
                "weight": 20.0,
                "daily_return": 1.5,
                "contribution": 0.3,
                "top_movers": [
                    {
                        "company": "Bank A",
                        "ticker": "BA",
                        "weight": 20.0,
                        "daily_return": 1.5,
                        "contribution": 0.3,
                    }
                ],
            },
            {
                "sector": "Technology",
                "subsector": "Software",
                "weight": 40.0,
                "daily_return": -0.25,
                "contribution": -0.1,
                "top_movers": [
                    {
                        "company": "Soft B",
                        "ticker": "SB",
                        "weight": 30.0,
                        "daily_return": -1.0,
                        "contribution": -0.3,
                    },
                    {
                        "company": "Soft A",
                        "ticker": "SA",
                        "weight": 10.0,
                        "daily_return": 2.0,
                        "contribution": 0.2,
                    },
                ],
            },
        ]


class TestIngestEquityIndexSubsectorDailyMoves(TestCase):
    """Test cases for 'ingest_equity_index_subsector_daily_moves'."""

    @patch(
        "market_overview.services.sector_analysis.get_yahoo_finance_daily_returns_for_date_range"
    )
    @patch(
        "market_overview.services.sector_analysis.WEIGHT_SCRAP_MAP", new_callable=dict
    )
    @patch("market_overview.services.sector_analysis.list_single_name_catalog_entries")
    def test_ingest_equity_index_subsector_daily_moves(
        self,
        mock_list_catalog,
        mock_weight_scrap_map,
        mock_returns,
    ):
        """
        GIVEN catalog names with weights and Yahoo returns
        WHEN ingest_equity_index_subsector_daily_moves runs for SPX
        THEN subsector moves and top movers are upserted
        """
        mock_list_catalog.return_value = [
            SingleNameCatalogEntry(
                company="Apple",
                ticker="AAPL",
                sector="Information Technology",
                subsector="Technology Hardware",
                equity_index=EquityIndexChoices.SPX,
            ),
            SingleNameCatalogEntry(
                company="Missing Weight Co",
                ticker="MISS",
                sector="Financials",
                subsector="Banks",
                equity_index=EquityIndexChoices.SPX,
            ),
            SingleNameCatalogEntry(
                company="Missing Return Co",
                ticker="NR",
                sector="Energy",
                subsector="Oil",
                equity_index=EquityIndexChoices.SPX,
            ),
        ]
        weight_scraper = Mock()
        weight_scraper.return_value = {"AAPL": 8.0, "NR": 1.0}
        mock_weight_scrap_map[EquityIndexChoices.SPX] = weight_scraper
        mock_returns.return_value = {date(2026, 11, 18): {"AAPL": 1.25}}

        result = ingest_equity_index_subsector_daily_moves(
            EquityIndexChoices.SPX,
            date(2026, 11, 18),
        )

        assert result == {
            "date": "2026-11-18",
            "equity_index": "SPX",
            "subsectors_upserted": 1,
            "names_missing_weight": ["MISS"],
            "names_missing_return": ["NR"],
        }
        stored = list(IndexSubsectorDailyMoveModel.objects.all())
        assert [
            (
                row.equity_index,
                row.date.isoformat(),
                row.sector,
                row.subsector,
                row.weight,
                row.daily_return,
                row.contribution,
                row.top_movers,
            )
            for row in stored
        ] == [
            (
                "SPX",
                "2026-11-18",
                "Information Technology",
                "Technology Hardware",
                8.0,
                1.25,
                0.1,
                [
                    {
                        "company": "Apple",
                        "ticker": "AAPL",
                        "weight": 8.0,
                        "daily_return": 1.25,
                        "contribution": 0.1,
                    }
                ],
            )
        ]

    @patch(
        "market_overview.services.sector_analysis.get_yahoo_finance_daily_returns_for_date_range"
    )
    @patch(
        "market_overview.services.sector_analysis.WEIGHT_SCRAP_MAP", new_callable=dict
    )
    @patch("market_overview.services.sector_analysis.list_single_name_catalog_entries")
    def test_ingest_equity_index_subsector_daily_moves_for_date_range(
        self,
        mock_list_catalog,
        mock_weight_scrap_map,
        mock_returns,
    ):
        """
        GIVEN Yahoo returns for two trading days
        WHEN ingest_equity_index_subsector_daily_moves_for_date_range runs
        THEN one subsector move is upserted per day
        """
        mock_list_catalog.return_value = [
            SingleNameCatalogEntry(
                company="Apple",
                ticker="AAPL",
                sector="Information Technology",
                subsector="Technology Hardware",
                equity_index=EquityIndexChoices.SPX,
            ),
        ]
        weight_scraper = Mock()
        weight_scraper.return_value = {"AAPL": 8.0}
        mock_weight_scrap_map[EquityIndexChoices.SPX] = weight_scraper
        mock_returns.return_value = {
            date(2026, 11, 17): {"AAPL": 1.0},
            date(2026, 11, 18): {"AAPL": 2.0},
        }

        result = ingest_equity_index_subsector_daily_moves_for_date_range(
            EquityIndexChoices.SPX,
            date(2026, 11, 17),
            date(2026, 11, 18),
        )

        assert result == [
            {
                "date": "2026-11-17",
                "equity_index": "SPX",
                "subsectors_upserted": 1,
                "names_missing_weight": [],
                "names_missing_return": [],
            },
            {
                "date": "2026-11-18",
                "equity_index": "SPX",
                "subsectors_upserted": 1,
                "names_missing_weight": [],
                "names_missing_return": [],
            },
        ]
        assert IndexSubsectorDailyMoveModel.objects.count() == 2
