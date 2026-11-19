"""Tests for industry profitability ingestion."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time

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
from economic_overview.services.industry_profitability import (
    IndustryProfitabilityIngestReport,
    IndustryProfitabilityIngestStatus,
    IndustryProfitabilityLocationResult,
    ingest_industry_profitability,
    upsert_industry_profitabilities,
)
from economic_overview.services.scrapers.common import ScrapedIndustryProfitability


class TestUpsertIndustryProfitabilities(TestCase):
    """Tests for upserting scraped industry profitabilities."""

    def test_upsert_industry_profitabilities(self):
        """
        GIVEN scraped FR industry-year turnover / operating profit / GVA figures
        WHEN upserting for France
        THEN IndustryProfitabilityModel figures are written with FR classification
        """
        scraped_industry_profitabilities = [
            ScrapedIndustryProfitability(
                industry_code="C10",
                industry_label="Manufacture of food products",
                period=date(2023, 1, 1),
                turnover=400.0,
                operating_profit=40.0,
                gva=120.0,
            ),
            ScrapedIndustryProfitability(
                industry_code="C12",
                industry_label="Manufacture of tobacco products",
                period=date(2023, 1, 1),
                turnover=200.0,
                operating_profit=25.0,
                gva=80.0,
            ),
        ]
        upserted_count = upsert_industry_profitabilities(
            EconomicDataLocationChoices.FR,
            scraped_industry_profitabilities,
            classification=IndustryClassificationChoices.NACE_REV2_DIVISION,
            source=EconomicDataSourceChoices.EUROSTAT,
        )
        assert upserted_count == 2
        stored = list(
            IndustryProfitabilityModel.objects.filter(
                location=EconomicDataLocationChoices.FR.value
            ).order_by("industry_code")
        )
        assert [
            (
                industry_profitability.industry_code,
                industry_profitability.classification,
                industry_profitability.turnover,
                industry_profitability.operating_profit,
                industry_profitability.gva,
                industry_profitability.base_unit,
                industry_profitability.base_currency,
                industry_profitability.source,
            )
            for industry_profitability in stored
        ] == [
            (
                "C10",
                IndustryClassificationChoices.NACE_REV2_DIVISION.value,
                400.0,
                40.0,
                120.0,
                IndicatorBaseUnitChoices.M.value,
                IndicatorBaseCurrencyChoices.EUR.value,
                EconomicDataSourceChoices.EUROSTAT.value,
            ),
            (
                "C12",
                IndustryClassificationChoices.NACE_REV2_DIVISION.value,
                200.0,
                25.0,
                80.0,
                IndicatorBaseUnitChoices.M.value,
                IndicatorBaseCurrencyChoices.EUR.value,
                EconomicDataSourceChoices.EUROSTAT.value,
            ),
        ]


@freeze_time("2025-11-01")
class TestIngestIndustryProfitability(TestCase):
    """Tests for the monthly industry profitability ingest gate."""

    @patch(
        "economic_overview.services.industry_profitability."
        "ingest_industry_profitability_for_location"
    )
    def test_ingest_industry_profitability_runs_on_first_of_month(
        self, mock_ingest_location
    ):
        """
        GIVEN the first calendar day of the month
        WHEN ingest_industry_profitability runs
        THEN each configured location is ingested
        """
        mock_ingest_location.return_value = IndustryProfitabilityLocationResult(
            location=EconomicDataLocationChoices.FR.value,
            status=IndustryProfitabilityIngestStatus.SUCCESS.value,
            upserted_count=2,
            message="Upserted 2 industry-year profitability figure(s).",
        )
        report = ingest_industry_profitability()
        assert report == IndustryProfitabilityIngestReport(
            as_of="2025-11-01",
            status=IndustryProfitabilityIngestStatus.SUCCESS.value,
            message=("Industry profitability ingest: 3 location(s) updated, 0 failed."),
            results=[
                IndustryProfitabilityLocationResult(
                    location=EconomicDataLocationChoices.FR.value,
                    status=IndustryProfitabilityIngestStatus.SUCCESS.value,
                    upserted_count=2,
                    message="Upserted 2 industry-year profitability figure(s).",
                ),
                IndustryProfitabilityLocationResult(
                    location=EconomicDataLocationChoices.FR.value,
                    status=IndustryProfitabilityIngestStatus.SUCCESS.value,
                    upserted_count=2,
                    message="Upserted 2 industry-year profitability figure(s).",
                ),
                IndustryProfitabilityLocationResult(
                    location=EconomicDataLocationChoices.FR.value,
                    status=IndustryProfitabilityIngestStatus.SUCCESS.value,
                    upserted_count=2,
                    message="Upserted 2 industry-year profitability figure(s).",
                ),
            ],
        )
        assert mock_ingest_location.call_count == 3

    @patch(
        "economic_overview.services.industry_profitability."
        "ingest_industry_profitability_for_location"
    )
    def test_ingest_industry_profitability_skips_outside_first_of_month(
        self, mock_ingest_location
    ):
        """
        GIVEN a date that is not the first calendar day
        WHEN ingest_industry_profitability runs without force
        THEN locations are not scraped
        """
        report = ingest_industry_profitability(as_of=date(2025, 11, 4))
        assert report["status"] == IndustryProfitabilityIngestStatus.SKIPPED.value
        mock_ingest_location.assert_not_called()
