"""Tests for trade ranking ingestion helpers."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeFlowChoices,
    TradeRankingModel,
    TradeTypeChoices,
)
from economic_overview.services.scrapers.common import (
    ScrapedTradeProductPartnerRanking,
    ScrapedTradeRanking,
    TradeProductCodesByPeriodFlow,
)
from economic_overview.services.trade_ranking import (
    TradeRankingIngestReport,
    TradeRankingIngestStatus,
    TradeRankingLocationResult,
    _list_trade_rankings_from_product_partner_scrape,
    _list_trade_rankings_from_topn_scrape,
    _replace_trade_ranking_product_partner_sets,
    ingest_trade_rankings,
    upsert_trade_rankings,
)


class TestUpsertTradeRankings(TestCase):
    """Replace trade ranking sets from normalized scrape rankings."""

    def test_upsert_trade_rankings_replaces_topn_set(self):
        """
        GIVEN an existing merchandise ranking for FR import product
        WHEN upsert_trade_rankings writes a new Top list
        THEN only the new product codes remain for that ranking set
        """
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.MERCHANDISE.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            rank=1,
            product_code="27",
            product_label="Old fuels",
            partner_code="",
            partner_label="",
            trade_value=1.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        upserted_count = upsert_trade_rankings(
            EconomicDataLocationChoices.FR,
            _list_trade_rankings_from_topn_scrape(
                [
                    ScrapedTradeRanking(
                        period=date(2023, 1, 1),
                        flow=TradeFlowChoices.IMPORT.value,
                        breakdown=TradeBreakdownChoices.PRODUCT.value,
                        rank=1,
                        item_code="87",
                        item_label="Vehicles",
                        trade_value=100.0,
                    ),
                    ScrapedTradeRanking(
                        period=date(2023, 1, 1),
                        flow=TradeFlowChoices.IMPORT.value,
                        breakdown=TradeBreakdownChoices.PRODUCT.value,
                        rank=2,
                        item_code="84",
                        item_label="Machinery",
                        trade_value=80.0,
                    ),
                ]
            ),
            trade_type=TradeTypeChoices.MERCHANDISE,
        )
        assert upserted_count == 2
        rankings = list(
            TradeRankingModel.objects.filter(
                trade_type=TradeTypeChoices.MERCHANDISE.value,
                location=EconomicDataLocationChoices.FR.value,
                period=date(2023, 1, 1),
                flow=TradeFlowChoices.IMPORT.value,
                breakdown=TradeBreakdownChoices.PRODUCT.value,
            ).order_by("rank")
        )
        assert [
            (ranking.rank, ranking.product_code, ranking.trade_value)
            for ranking in rankings
        ] == [(1, "87", 100.0), (2, "84", 80.0)]

    def test_upsert_trade_rankings_replaces_product_partner_set(self):
        """
        GIVEN an existing energy partner ranking for FR crude imports
        WHEN upsert_trade_rankings writes a new Top partner list
        THEN only the new partners remain for that product ranking set
        """
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            product_code="2709",
            product_label="Crude petroleum",
            partner_code="XX",
            partner_label="Old",
            rank=1,
            trade_value=1.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        upserted_count = upsert_trade_rankings(
            EconomicDataLocationChoices.FR,
            _list_trade_rankings_from_product_partner_scrape(
                [
                    ScrapedTradeProductPartnerRanking(
                        period=date(2023, 1, 1),
                        flow=TradeFlowChoices.IMPORT.value,
                        product_code="2709",
                        product_label="Crude petroleum",
                        partner_code="NO",
                        partner_label="Norway",
                        rank=1,
                        trade_value=50.0,
                    )
                ]
            ),
            trade_type=TradeTypeChoices.ENERGY,
        )
        assert upserted_count == 1
        rankings = list(
            TradeRankingModel.objects.filter(
                trade_type=TradeTypeChoices.ENERGY.value,
                location=EconomicDataLocationChoices.FR.value,
                product_code="2709",
            )
        )
        assert [
            (ranking.partner_code, ranking.rank, ranking.trade_value)
            for ranking in rankings
        ] == [("NO", 1, 50.0)]

    def test_replace_trade_ranking_product_partner_sets_clears_empty_scrape(self):
        """
        GIVEN an existing product×partner ranking set for FR crude imports
        WHEN the expected product has no scraped partners
        THEN that ranking set is cleared
        """
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            product_code="2709",
            product_label="Crude petroleum",
            partner_code="XX",
            partner_label="Old",
            rank=1,
            trade_value=1.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        upserted_count = _replace_trade_ranking_product_partner_sets(
            EconomicDataLocationChoices.FR,
            [
                TradeProductCodesByPeriodFlow(
                    period=date(2023, 1, 1),
                    flow=TradeFlowChoices.IMPORT.value,
                    product_codes=["2709"],
                )
            ],
            [],
            trade_type=TradeTypeChoices.ENERGY,
        )
        assert upserted_count == 0
        assert (
            TradeRankingModel.objects.filter(
                trade_type=TradeTypeChoices.ENERGY.value,
                location=EconomicDataLocationChoices.FR.value,
                product_code="2709",
                breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            ).count()
            == 0
        )


class TestIngestTradeRankings(TestCase):
    """Gate trade ingest on calendar day 1 unless forced."""

    @patch(
        "economic_overview.services.trade_ranking.ingest_trade_rankings_for_location"
    )
    def test_ingest_trade_rankings_skips_outside_first_of_month(
        self, mock_ingest_location
    ):
        """
        GIVEN a mid-month as_of date
        WHEN ingest_trade_rankings runs without force
        THEN the run is skipped and no location ingest is called
        """
        report = ingest_trade_rankings(
            trade_type=TradeTypeChoices.MERCHANDISE,
            as_of=date(2025, 11, 4),
        )
        assert report == TradeRankingIngestReport(
            as_of="2025-11-04",
            status=TradeRankingIngestStatus.SKIPPED.value,
            message=("Skipped: 2025-11-04 is not the first calendar day of the month."),
            results=[],
        )
        mock_ingest_location.assert_not_called()

    @patch(
        "economic_overview.services.trade_ranking.ingest_trade_rankings_for_location"
    )
    def test_ingest_trade_rankings_runs_on_first_of_month(self, mock_ingest_location):
        """
        GIVEN the first calendar day of the month
        WHEN ingest_trade_rankings runs for one trade type
        THEN each trade location is ingested
        """
        mock_ingest_location.return_value = TradeRankingLocationResult(
            location="FR",
            trade_type=TradeTypeChoices.MERCHANDISE.value,
            status=TradeRankingIngestStatus.SUCCESS.value,
            upserted_count=1,
            message="ok",
        )
        report = ingest_trade_rankings(
            trade_type=TradeTypeChoices.MERCHANDISE,
            as_of=date(2025, 11, 1),
        )
        assert report == TradeRankingIngestReport(
            as_of="2025-11-01",
            status=TradeRankingIngestStatus.SUCCESS.value,
            message="Merchandise trade ranking ingest: 3 location(s) updated, 0 failed.",
            results=[
                TradeRankingLocationResult(
                    location="FR",
                    trade_type=TradeTypeChoices.MERCHANDISE.value,
                    status=TradeRankingIngestStatus.SUCCESS.value,
                    upserted_count=1,
                    message="ok",
                ),
                TradeRankingLocationResult(
                    location="FR",
                    trade_type=TradeTypeChoices.MERCHANDISE.value,
                    status=TradeRankingIngestStatus.SUCCESS.value,
                    upserted_count=1,
                    message="ok",
                ),
                TradeRankingLocationResult(
                    location="FR",
                    trade_type=TradeTypeChoices.MERCHANDISE.value,
                    status=TradeRankingIngestStatus.SUCCESS.value,
                    upserted_count=1,
                    message="ok",
                ),
            ],
        )
        assert mock_ingest_location.call_count == 3

    @patch(
        "economic_overview.services.trade_ranking.ingest_trade_rankings_for_location"
    )
    def test_ingest_trade_rankings_fails_when_any_location_fails(
        self, mock_ingest_location
    ):
        """
        GIVEN one location succeeds and another fails
        WHEN ingest_trade_rankings aggregates the run
        THEN the overall status is failed
        """
        mock_ingest_location.side_effect = [
            TradeRankingLocationResult(
                location="US",
                trade_type=TradeTypeChoices.MERCHANDISE.value,
                status=TradeRankingIngestStatus.SUCCESS.value,
                upserted_count=2,
                message="ok",
            ),
            TradeRankingLocationResult(
                location="FR",
                trade_type=TradeTypeChoices.MERCHANDISE.value,
                status=TradeRankingIngestStatus.FAILED.value,
                upserted_count=0,
                message="scrape error",
            ),
            TradeRankingLocationResult(
                location="JP",
                trade_type=TradeTypeChoices.MERCHANDISE.value,
                status=TradeRankingIngestStatus.SUCCESS.value,
                upserted_count=1,
                message="ok",
            ),
        ]
        report = ingest_trade_rankings(
            trade_type=TradeTypeChoices.MERCHANDISE,
            as_of=date(2025, 11, 1),
        )
        assert report == TradeRankingIngestReport(
            as_of="2025-11-01",
            status=TradeRankingIngestStatus.FAILED.value,
            message="Merchandise trade ranking ingest: 2 location(s) updated, 1 failed.",
            results=[
                TradeRankingLocationResult(
                    location="US",
                    trade_type=TradeTypeChoices.MERCHANDISE.value,
                    status=TradeRankingIngestStatus.SUCCESS.value,
                    upserted_count=2,
                    message="ok",
                ),
                TradeRankingLocationResult(
                    location="FR",
                    trade_type=TradeTypeChoices.MERCHANDISE.value,
                    status=TradeRankingIngestStatus.FAILED.value,
                    upserted_count=0,
                    message="scrape error",
                ),
                TradeRankingLocationResult(
                    location="JP",
                    trade_type=TradeTypeChoices.MERCHANDISE.value,
                    status=TradeRankingIngestStatus.SUCCESS.value,
                    upserted_count=1,
                    message="ok",
                ),
            ],
        )
