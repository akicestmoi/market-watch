"""Tests for Eurostat Comext trade ranking scrapers."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeFlowChoices,
)
from economic_overview.services.scrapers.common import ScrapedTradeRanking
from economic_overview.services.scrapers.eurostat_comext import (
    _list_comext_observations,
    _list_top_trade_rankings,
    get_trade_rankings_from_comext,
)


class TestListComextObservations(TestCase):
    """Decode JSON-stat Comext payloads into trade observations."""

    def test_list_comext_observations(self):
        """
        GIVEN a one-product × two-partner Comext JSON-stat payload
        WHEN _list_comext_observations decodes it
        THEN both partner cells are returned with labels and values
        """
        observations = _list_comext_observations(
            {
                "id": [
                    "freq",
                    "reporter",
                    "partner",
                    "product",
                    "flow",
                    "indicators",
                    "time",
                ],
                "size": [1, 1, 2, 1, 1, 1, 1],
                "value": {"0": 10.0, "1": 20.0},
                "dimension": {
                    "partner": {
                        "category": {
                            "index": {"NO": 0, "US": 1},
                            "label": {"NO": "Norway", "US": "United States"},
                        }
                    },
                    "product": {
                        "category": {
                            "index": {"2709": 0},
                            "label": {"2709": "Crude"},
                        }
                    },
                },
            }
        )
        assert observations == [
            {
                "product_code": "2709",
                "product_label": "Crude",
                "partner_code": "NO",
                "partner_label": "Norway",
                "trade_value": 10.0,
            },
            {
                "product_code": "2709",
                "product_label": "Crude",
                "partner_code": "US",
                "partner_label": "United States",
                "trade_value": 20.0,
            },
        ]


class TestListTopTradeRankings(TestCase):
    """Collapse Comext cells into Top-N rankings."""

    def test_list_top_trade_rankings_product(self):
        """
        GIVEN WORLD partner HS2 cells
        WHEN _list_top_trade_rankings builds the product breakdown
        THEN items are ranked by value
        """
        rankings = _list_top_trade_rankings(
            [
                {
                    "product_code": "87",
                    "product_label": "Vehicles",
                    "partner_code": "WORLD",
                    "partner_label": "World",
                    "trade_value": 100.0,
                },
                {
                    "product_code": "84",
                    "product_label": "Machinery",
                    "partner_code": "WORLD",
                    "partner_label": "World",
                    "trade_value": 80.0,
                },
            ],
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT,
            breakdown=TradeBreakdownChoices.PRODUCT,
            top_n=30,
        )
        assert rankings == [
            ScrapedTradeRanking(
                period=date(2023, 1, 1),
                flow="IMPORT",
                breakdown="PRODUCT",
                rank=1,
                item_code="87",
                item_label="Vehicles",
                trade_value=100.0,
            ),
            ScrapedTradeRanking(
                period=date(2023, 1, 1),
                flow="IMPORT",
                breakdown="PRODUCT",
                rank=2,
                item_code="84",
                item_label="Machinery",
                trade_value=80.0,
            ),
        ]


class TestGetTradeRankingsFromComext(TestCase):
    """Public Comext trade entry point with mocked HTTP."""

    @patch("economic_overview.services.scrapers.eurostat_comext._fetch_comext_json")
    def test_get_trade_rankings_from_comext(self, mock_fetch):
        """
        GIVEN Comext returns product and partner payloads for one year
        WHEN get_trade_rankings_from_comext runs
        THEN Top rankings are returned for both breakdowns and both flows
        """
        mock_fetch.side_effect = [
            {
                "id": ["partner", "product"],
                "size": [1, 1],
                "value": {"0": 50.0},
                "dimension": {
                    "partner": {
                        "category": {
                            "index": {"WORLD": 0},
                            "label": {"WORLD": "World"},
                        }
                    },
                    "product": {
                        "category": {
                            "index": {"87": 0},
                            "label": {"87": "Vehicles"},
                        }
                    },
                },
            },
            {
                "id": ["partner", "product"],
                "size": [1, 1],
                "value": {"0": 40.0},
                "dimension": {
                    "partner": {
                        "category": {
                            "index": {"DE": 0},
                            "label": {"DE": "Germany"},
                        }
                    },
                    "product": {
                        "category": {
                            "index": {"TOTAL": 0},
                            "label": {"TOTAL": "Total"},
                        }
                    },
                },
            },
        ] * 2
        rankings = get_trade_rankings_from_comext([2023], top_n=30)
        assert len(rankings) == 4
        assert {ranking["breakdown"] for ranking in rankings} == {
            "PRODUCT",
            "PARTNER",
        }
        assert {ranking["flow"] for ranking in rankings} == {"IMPORT", "EXPORT"}
