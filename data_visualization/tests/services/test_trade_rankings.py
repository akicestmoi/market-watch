"""Tests for trade ranking chart panels."""

from datetime import date

from django.test import TestCase

from data_visualization.services.economic_charts.trade_rankings import (
    TradeBarPoint,
    TradeCellObservation,
    TradeRankingChartsPanel,
    TradeRankingObservation,
    _format_trade_partner_label,
    get_trade_ranking_panel,
    list_trade_bars_from_observations,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.economic_indicators import EconomicDataCategoryChoices
from economic_overview.models.trade_ranking import (
    TradeBreakdownChoices,
    TradeFlowChoices,
    TradeRankingModel,
    TradeTypeChoices,
)


class TestGetTradeRankingPanel(TestCase):
    """Build trade panels from stored rankings."""

    def test_get_trade_ranking_panel_merchandise(self):
        """
        GIVEN FR merchandise product rankings for 2023
        WHEN get_trade_ranking_panel is called for FR merchandise
        THEN the panel includes ranking observations and default import/product bars
        """
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.MERCHANDISE.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            rank=1,
            product_code="87",
            product_label="Vehicles",
            partner_code="",
            partner_label="",
            trade_value=100.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.MERCHANDISE.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            rank=2,
            product_code="84",
            product_label="Machinery",
            partner_code="",
            partner_label="",
            trade_value=80.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        panel = get_trade_ranking_panel(
            EconomicDataLocationChoices.FR,
            trade_type=TradeTypeChoices.MERCHANDISE,
        )
        assert panel == TradeRankingChartsPanel(
            panel="merchandise",
            panel_label="Merchandise Trade",
            category=str(EconomicDataCategoryChoices.MACROECONOMICS.label),
            panel_id="merchandise-trade-fr",
            title="FR Merchandise Trade — By Product",
            location="FR",
            as_of_year=2023,
            available_years=[2023],
            flow=TradeFlowChoices.IMPORT.value,
            flow_options=[
                {"value": "IMPORT", "label": "Import"},
                {"value": "EXPORT", "label": "Export"},
            ],
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            breakdown_options=[
                {"value": "PRODUCT", "label": "By Product"},
                {"value": "PARTNER", "label": "By Partner"},
            ],
            product_code="",
            product_options=[
                {"value": "84", "label": "Machinery"},
                {"value": "87", "label": "Vehicles"},
            ],
            partner_code="",
            partner_options=[],
            top_n=20,
            max_top_n=20,
            line_top_n=5,
            ranking_observations=[
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PRODUCT",
                    item_code="87",
                    item_label="Vehicles",
                    rank=1,
                    trade_value=0.1,
                ),
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PRODUCT",
                    item_code="84",
                    item_label="Machinery",
                    rank=2,
                    trade_value=0.08,
                ),
            ],
            cell_observations=[],
            bars=[
                TradeBarPoint(
                    item_code="87",
                    item_label="Vehicles",
                    rank=1,
                    trade_value=0.1,
                ),
                TradeBarPoint(
                    item_code="84",
                    item_label="Machinery",
                    rank=2,
                    trade_value=0.08,
                ),
            ],
            value_axis_label="k€",
            description=(
                "Annual customs merchandise rankings (not balance-of-payments). "
                "Partners exclude world and regional aggregates. Partner view with a "
                "product filter reads that product's stored Top partners only."
            ),
        )

    def test_list_trade_bars_from_observations(self):
        """
        GIVEN mixed ranking observations
        WHEN list_trade_bars_from_observations filters import products Top 1
        THEN only the matching top rank bar is returned
        """
        bars = list_trade_bars_from_observations(
            [
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PRODUCT",
                    item_code="87",
                    item_label="Vehicles",
                    rank=1,
                    trade_value=100.0,
                ),
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PRODUCT",
                    item_code="84",
                    item_label="Machinery",
                    rank=2,
                    trade_value=80.0,
                ),
                TradeRankingObservation(
                    year=2023,
                    flow="EXPORT",
                    breakdown="PRODUCT",
                    item_code="87",
                    item_label="Vehicles",
                    rank=1,
                    trade_value=90.0,
                ),
            ],
            [],
            year=2023,
            flow="IMPORT",
            breakdown="PRODUCT",
            product_code="",
            partner_code="",
            top_n=1,
        )
        assert bars == [
            TradeBarPoint(
                item_code="87",
                item_label="Vehicles",
                rank=1,
                trade_value=100.0,
            )
        ]

    def test_get_trade_ranking_panel_energy(self):
        """
        GIVEN FR energy Top-N products, partners, and product×partner cells
        WHEN get_trade_ranking_panel is called for FR energy
        THEN product bars come from Top-N rankings and cells stay for cross filters
        """
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            rank=1,
            product_code="2709",
            product_label="Crude petroleum",
            partner_code="",
            partner_label="",
            trade_value=100.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            rank=2,
            product_code="271111",
            product_label="LNG",
            partner_code="",
            partner_label="",
            trade_value=30.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PARTNER.value,
            rank=1,
            product_code="",
            product_label="",
            partner_code="NO",
            partner_label="Norway",
            trade_value=60.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PARTNER.value,
            rank=2,
            product_code="",
            product_label="",
            partner_code="US",
            partner_label="United States",
            trade_value=70.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            product_code="2709",
            product_label="Crude petroleum",
            partner_code="NO",
            partner_label="Norway",
            rank=1,
            trade_value=60.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            product_code="2709",
            product_label="Crude petroleum",
            partner_code="US",
            partner_label="United States",
            rank=2,
            trade_value=40.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.ENERGY.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PRODUCT_PARTNER.value,
            product_code="271111",
            product_label="LNG",
            partner_code="US",
            partner_label="United States",
            rank=1,
            trade_value=30.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        panel = get_trade_ranking_panel(
            EconomicDataLocationChoices.FR,
            trade_type=TradeTypeChoices.ENERGY,
        )
        assert panel == TradeRankingChartsPanel(
            panel="energy",
            panel_label="Energy Trade",
            category=str(EconomicDataCategoryChoices.MACROECONOMICS.label),
            panel_id="energy-trade-fr",
            title="FR Energy Trade — By Product",
            location="FR",
            as_of_year=2023,
            available_years=[2023],
            flow=TradeFlowChoices.IMPORT.value,
            flow_options=[
                {"value": "IMPORT", "label": "Import"},
                {"value": "EXPORT", "label": "Export"},
            ],
            breakdown=TradeBreakdownChoices.PRODUCT.value,
            breakdown_options=[
                {"value": "PRODUCT", "label": "By Product"},
                {"value": "PARTNER", "label": "By Partner"},
            ],
            product_code="",
            product_options=[
                {"value": "2709", "label": "Crude petroleum"},
                {"value": "271111", "label": "LNG"},
            ],
            partner_code="",
            partner_options=[
                {"value": "NO", "label": "Norway"},
                {"value": "US", "label": "United States"},
            ],
            top_n=10,
            max_top_n=10,
            line_top_n=5,
            ranking_observations=[
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PARTNER",
                    item_code="NO",
                    item_label="Norway",
                    rank=1,
                    trade_value=0.06,
                ),
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PARTNER",
                    item_code="US",
                    item_label="United States",
                    rank=2,
                    trade_value=0.07,
                ),
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PRODUCT",
                    item_code="2709",
                    item_label="Crude petroleum",
                    rank=1,
                    trade_value=0.1,
                ),
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PRODUCT",
                    item_code="271111",
                    item_label="LNG",
                    rank=2,
                    trade_value=0.03,
                ),
            ],
            cell_observations=[
                TradeCellObservation(
                    year=2023,
                    flow="IMPORT",
                    product_code="2709",
                    product_label="Crude petroleum",
                    partner_code="NO",
                    partner_label="Norway",
                    rank=1,
                    trade_value=0.06,
                ),
                TradeCellObservation(
                    year=2023,
                    flow="IMPORT",
                    product_code="2709",
                    product_label="Crude petroleum",
                    partner_code="US",
                    partner_label="United States",
                    rank=2,
                    trade_value=0.04,
                ),
                TradeCellObservation(
                    year=2023,
                    flow="IMPORT",
                    product_code="271111",
                    product_label="LNG",
                    partner_code="US",
                    partner_label="United States",
                    rank=1,
                    trade_value=0.03,
                ),
            ],
            bars=[
                TradeBarPoint(
                    item_code="2709",
                    item_label="Crude petroleum",
                    rank=1,
                    trade_value=0.1,
                ),
                TradeBarPoint(
                    item_code="271111",
                    item_label="LNG",
                    rank=2,
                    trade_value=0.03,
                ),
            ],
            value_axis_label="k€",
            description=(
                "Annual customs energy trade (HS energy products). Partner view with a "
                "product filter reads that product's stored Top partners only."
            ),
        )

    def test_list_trade_bars_from_observations_partner_with_product_filter(self):
        """
        GIVEN product×partner cells for crude and LNG
        WHEN partner breakdown is filtered to crude
        THEN only crude's stored Top partners are returned
        """
        bars = list_trade_bars_from_observations(
            [],
            [
                TradeCellObservation(
                    year=2023,
                    flow="IMPORT",
                    product_code="2709",
                    product_label="Crude petroleum",
                    partner_code="NO",
                    partner_label="Norway",
                    rank=1,
                    trade_value=60.0,
                ),
                TradeCellObservation(
                    year=2023,
                    flow="IMPORT",
                    product_code="2709",
                    product_label="Crude petroleum",
                    partner_code="US",
                    partner_label="United States",
                    rank=2,
                    trade_value=40.0,
                ),
                TradeCellObservation(
                    year=2023,
                    flow="IMPORT",
                    product_code="271111",
                    product_label="LNG",
                    partner_code="US",
                    partner_label="United States",
                    rank=1,
                    trade_value=30.0,
                ),
            ],
            year=2023,
            flow="IMPORT",
            breakdown=TradeBreakdownChoices.PARTNER.value,
            product_code="2709",
            partner_code="",
            top_n=10,
        )
        assert bars == [
            TradeBarPoint(
                item_code="NO",
                item_label="Norway",
                rank=1,
                trade_value=60.0,
            ),
            TradeBarPoint(
                item_code="US",
                item_label="United States",
                rank=2,
                trade_value=40.0,
            ),
        ]

    def test_format_trade_partner_label(self):
        """
        GIVEN a partner label with an '(incl. …)' suffix
        WHEN _format_trade_partner_label is called
        THEN the parenthetical note is dropped
        """
        assert _format_trade_partner_label("China (incl. Hong Kong)") == "China"

    def test_get_trade_ranking_panel_excludes_unspecified_partners(self):
        """
        GIVEN FR merchandise partner rankings including an unspecified QV partner
        WHEN get_trade_ranking_panel is called for partner breakdown
        THEN the unspecified partner is omitted and incl. notes are stripped
        """
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.MERCHANDISE.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PARTNER.value,
            rank=1,
            product_code="",
            product_label="",
            partner_code="CN",
            partner_label="China (incl. Hong Kong)",
            trade_value=100.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        TradeRankingModel.objects.create(
            trade_type=TradeTypeChoices.MERCHANDISE.value,
            location=EconomicDataLocationChoices.FR.value,
            period=date(2023, 1, 1),
            flow=TradeFlowChoices.IMPORT.value,
            breakdown=TradeBreakdownChoices.PARTNER.value,
            rank=2,
            product_code="",
            product_label="",
            partner_code="QV",
            partner_label=(
                "Countries and territories not specified "
                "within the framework of intra-Union trade"
            ),
            trade_value=90.0,
            source=EconomicDataSourceChoices.EUROSTAT.value,
        )
        panel = get_trade_ranking_panel(
            EconomicDataLocationChoices.FR,
            trade_type=TradeTypeChoices.MERCHANDISE,
            breakdown=TradeBreakdownChoices.PARTNER,
        )
        assert panel == TradeRankingChartsPanel(
            panel="merchandise",
            panel_label="Merchandise Trade",
            category=str(EconomicDataCategoryChoices.MACROECONOMICS.label),
            panel_id="merchandise-trade-fr",
            title="FR Merchandise Trade — By Partner",
            location="FR",
            as_of_year=2023,
            available_years=[2023],
            flow=TradeFlowChoices.IMPORT.value,
            flow_options=[
                {"value": "IMPORT", "label": "Import"},
                {"value": "EXPORT", "label": "Export"},
            ],
            breakdown=TradeBreakdownChoices.PARTNER.value,
            breakdown_options=[
                {"value": "PRODUCT", "label": "By Product"},
                {"value": "PARTNER", "label": "By Partner"},
            ],
            product_code="",
            product_options=[],
            partner_code="",
            partner_options=[{"value": "CN", "label": "China"}],
            top_n=20,
            max_top_n=20,
            line_top_n=5,
            ranking_observations=[
                TradeRankingObservation(
                    year=2023,
                    flow="IMPORT",
                    breakdown="PARTNER",
                    item_code="CN",
                    item_label="China",
                    rank=1,
                    trade_value=0.1,
                )
            ],
            cell_observations=[],
            bars=[
                TradeBarPoint(
                    item_code="CN",
                    item_label="China",
                    rank=1,
                    trade_value=0.1,
                )
            ],
            value_axis_label="k€",
            description=(
                "Annual customs merchandise rankings (not balance-of-payments). "
                "Partners exclude world and regional aggregates. Partner view with a "
                "product filter reads that product's stored Top partners only."
            ),
        )
