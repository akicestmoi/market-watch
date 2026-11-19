"""Tests for industry profitability chart panel derivation."""

from datetime import date

from django.test import TestCase

from data_visualization.services.config import ChartPeriodWindow
from data_visualization.services.economic_charts.industry_profitability import (
    IndustryProfitabilityObservation,
    IndustryProfitabilityPanel,
    IndustryProfitabilityPoint,
    IndustryProfitabilityRankBy,
    IndustryProfitabilityRankByOption,
    _get_industry_profitability_panel,
    get_industry_profitability_panels,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.industry_profitability import (
    IndustryClassificationChoices,
    IndustryProfitabilityModel,
)


def _create_fr_industry_row(
    *,
    industry_code: str,
    industry_label: str,
    year: int,
    turnover: float,
    operating_profit: float,
    gva: float,
) -> IndustryProfitabilityModel:
    """Save one FR industry-year profitability figure for derive tests."""
    return IndustryProfitabilityModel.objects.create(
        location=EconomicDataLocationChoices.FR.value,
        classification=IndustryClassificationChoices.NACE_REV2_DIVISION.value,
        industry_code=industry_code,
        industry_label=industry_label,
        period=date(year, 1, 1),
        turnover=turnover,
        operating_profit=operating_profit,
        gva=gva,
        base_unit=IndicatorBaseUnitChoices.M.value,
        base_currency=IndicatorBaseCurrencyChoices.EUR.value,
        source=EconomicDataSourceChoices.EUROSTAT.value,
    )


_RANK_BY_OPTIONS = [
    IndustryProfitabilityRankByOption(value="turnover", label="Turnover"),
    IndustryProfitabilityRankByOption(
        value="operating_profit", label="Operating Profit"
    ),
    IndustryProfitabilityRankByOption(value="margin", label="Margin"),
    IndustryProfitabilityRankByOption(value="gva", label="GVA"),
]


class TestGetIndustryProfitabilityPanel(TestCase):
    """Tests for _get_industry_profitability_panel and panels helpers."""

    def setUp(self):
        """Seed FR industry profitability figures for 2022–2023."""
        _create_fr_industry_row(
            industry_code="C10",
            industry_label="Manufacture of food products",
            year=2023,
            turnover=400.0,
            operating_profit=40.0,
            gva=120.0,
        )
        _create_fr_industry_row(
            industry_code="C11",
            industry_label="Manufacture of beverages",
            year=2023,
            turnover=100.0,
            operating_profit=10.0,
            gva=30.0,
        )
        _create_fr_industry_row(
            industry_code="C12",
            industry_label="Manufacture of tobacco products",
            year=2023,
            turnover=250.0,
            operating_profit=25.0,
            gva=200.0,
        )
        _create_fr_industry_row(
            industry_code="C10",
            industry_label="Manufacture of food products",
            year=2022,
            turnover=300.0,
            operating_profit=30.0,
            gva=90.0,
        )
        _create_fr_industry_row(
            industry_code="C11",
            industry_label="Manufacture of beverages",
            year=2022,
            turnover=80.0,
            operating_profit=8.0,
            gva=24.0,
        )
        _create_fr_industry_row(
            industry_code="C12",
            industry_label="Manufacture of tobacco products",
            year=2022,
            turnover=200.0,
            operating_profit=20.0,
            gva=160.0,
        )

    def test_get_industry_profitability_panel_ranks_by_turnover(self):
        """
        GIVEN FR industry profitability figures for 2022–2023
        WHEN deriving the panel with default Turnover rank-by
        THEN industries are ranked by turnover and history is kept for line members
        """
        panel = _get_industry_profitability_panel(
            EconomicDataLocationChoices.FR,
            line_top_n=2,
            bar_top_n=3,
        )
        assert panel == IndustryProfitabilityPanel(
            category="Business",
            panel_id="industry-profitability",
            line_title="Industry Turnover Trend",
            bar_title="Industry Turnover Ranking",
            location="France",
            classification_label=("NACE Rev. 2 division (2-digit) — France"),
            contribution_classification_label=(
                "NACE Rev. 2 division (2-digit) — France"
            ),
            source_label="Statistical Office of the European Union",
            contribution_source_label="Statistical Office of the European Union",
            as_of_year=2023,
            available_years=[2023, 2022],
            line_top_n=2,
            bar_top_n=3,
            rank_by="turnover",
            rank_by_options=_RANK_BY_OPTIONS,
            observations=[
                IndustryProfitabilityObservation(
                    industry_code="C10",
                    industry_label="Manufacture of food products",
                    year=2023,
                    turnover=400.0,
                    operating_profit=40.0,
                    gva=120.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C11",
                    industry_label="Manufacture of beverages",
                    year=2023,
                    turnover=100.0,
                    operating_profit=10.0,
                    gva=30.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C12",
                    industry_label="Manufacture of tobacco products",
                    year=2023,
                    turnover=250.0,
                    operating_profit=25.0,
                    gva=200.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C10",
                    industry_label="Manufacture of food products",
                    year=2022,
                    turnover=300.0,
                    operating_profit=30.0,
                    gva=90.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C11",
                    industry_label="Manufacture of beverages",
                    year=2022,
                    turnover=80.0,
                    operating_profit=8.0,
                    gva=24.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C12",
                    industry_label="Manufacture of tobacco products",
                    year=2022,
                    turnover=200.0,
                    operating_profit=20.0,
                    gva=160.0,
                    margin=10.0,
                ),
            ],
            contribution_observations=[
                IndustryProfitabilityObservation(
                    industry_code="C10",
                    industry_label="Manufacture of food products",
                    year=2023,
                    turnover=400.0,
                    operating_profit=40.0,
                    gva=120.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C11",
                    industry_label="Manufacture of beverages",
                    year=2023,
                    turnover=100.0,
                    operating_profit=10.0,
                    gva=30.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C12",
                    industry_label="Manufacture of tobacco products",
                    year=2023,
                    turnover=250.0,
                    operating_profit=25.0,
                    gva=200.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C10",
                    industry_label="Manufacture of food products",
                    year=2022,
                    turnover=300.0,
                    operating_profit=30.0,
                    gva=90.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C11",
                    industry_label="Manufacture of beverages",
                    year=2022,
                    turnover=80.0,
                    operating_profit=8.0,
                    gva=24.0,
                    margin=10.0,
                ),
                IndustryProfitabilityObservation(
                    industry_code="C12",
                    industry_label="Manufacture of tobacco products",
                    year=2022,
                    turnover=200.0,
                    operating_profit=20.0,
                    gva=160.0,
                    margin=10.0,
                ),
            ],
            line_data=[
                IndustryProfitabilityPoint(
                    period="2023",
                    data_value=250.0,
                    indicator_name="Manufacture of tobacco products",
                    unit_label="m€",
                ),
                IndustryProfitabilityPoint(
                    period="2023",
                    data_value=400.0,
                    indicator_name="Manufacture of food products",
                    unit_label="m€",
                ),
                IndustryProfitabilityPoint(
                    period="2022",
                    data_value=200.0,
                    indicator_name="Manufacture of tobacco products",
                    unit_label="m€",
                ),
                IndustryProfitabilityPoint(
                    period="2022",
                    data_value=300.0,
                    indicator_name="Manufacture of food products",
                    unit_label="m€",
                ),
            ],
            bar_data=[
                IndustryProfitabilityPoint(
                    period="2023",
                    data_value=400.0,
                    indicator_name="Manufacture of food products",
                    unit_label="m€",
                ),
                IndustryProfitabilityPoint(
                    period="2023",
                    data_value=250.0,
                    indicator_name="Manufacture of tobacco products",
                    unit_label="m€",
                ),
                IndustryProfitabilityPoint(
                    period="2023",
                    data_value=100.0,
                    indicator_name="Manufacture of beverages",
                    unit_label="m€",
                ),
            ],
            value_axis_label="m€",
            description=(
                "Rank industries by Turnover, Operating Profit, Margin "
                "(operating profit ÷ turnover), or GVA. "
                "Survey map: NACE Rev. 2 division (2-digit) — France "
                "(Statistical Office of the European Union). "
                "Contribution map: NACE Rev. 2 division (2-digit) — France "
                "(Statistical Office of the European Union). "
                "Single-region only — levels are not cross-country comparable."
            ),
            comparability_warning="",
        )

    def test_get_industry_profitability_panel_ranks_by_gva(self):
        """
        GIVEN FR industry rows with GVA
        WHEN deriving the panel ranked by GVA
        THEN industries are ordered by GVA
        """
        panel = _get_industry_profitability_panel(
            EconomicDataLocationChoices.FR,
            line_top_n=1,
            bar_top_n=2,
            rank_by=IndustryProfitabilityRankBy.GVA,
        )
        assert panel is not None
        assert panel["rank_by"] == "gva"
        assert panel["bar_data"] == [
            IndustryProfitabilityPoint(
                period="2023",
                data_value=200.0,
                indicator_name="Manufacture of tobacco products",
                unit_label="m€",
            ),
            IndustryProfitabilityPoint(
                period="2023",
                data_value=120.0,
                indicator_name="Manufacture of food products",
                unit_label="m€",
            ),
        ]

    def test_get_industry_profitability_panel_line_respects_period_window(self):
        """
        GIVEN FR industry rows spanning 2018–2023
        WHEN deriving the panel with a 3Y chart period and as-of 2023
        THEN line history starts at 2020 (as-of minus 3 years)
        """
        for year, turnover in (
            (2018, 180.0),
            (2019, 190.0),
            (2020, 200.0),
            (2021, 210.0),
        ):
            _create_fr_industry_row(
                industry_code="C10",
                industry_label="Manufacture of food products",
                year=year,
                turnover=turnover,
                operating_profit=turnover / 10.0,
                gva=turnover / 4.0,
            )
        panel = _get_industry_profitability_panel(
            EconomicDataLocationChoices.FR,
            period_window=ChartPeriodWindow.THREE_YEARS,
            as_of_year=2023,
            line_top_n=1,
            bar_top_n=1,
        )
        assert panel is not None
        assert [point["period"] for point in panel["line_data"]] == [
            "2023",
            "2022",
            "2021",
            "2020",
        ]

    def test_get_industry_profitability_panels_skips_cross_region(self):
        """
        GIVEN Cross-Region mode
        WHEN requesting industry profitability panels
        THEN an empty list is returned
        """
        assert (
            get_industry_profitability_panels(
                EconomicDataLocationChoices.FR,
                cross_region=True,
            )
            == []
        )

    def test_get_industry_profitability_panels_empty_without_rows(self):
        """
        GIVEN a location with no industry profitability figures
        WHEN requesting panels
        THEN an empty list is returned
        """
        assert (
            get_industry_profitability_panels(
                EconomicDataLocationChoices.US,
                cross_region=False,
            )
            == []
        )
