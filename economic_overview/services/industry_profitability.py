"""Ingest industry profitability tables for US / FR / JP charts."""

import logging
from datetime import date
from enum import Enum
from typing import TypedDict

from core.services.calendar import get_local_today
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.industry_profitability import (
    IndustryClassificationChoices,
    IndustryProfitabilityModel,
)
from economic_overview.services.config import (
    INDUSTRY_CLASSIFICATION_BY_LOCATION,
    INDUSTRY_PROFITABILITY_CURRENCY_BY_LOCATION,
    INDUSTRY_PROFITABILITY_LOCATIONS,
    INDUSTRY_PROFITABILITY_START_YEAR,
    INDUSTRY_PROFITABILITY_UNIT_BY_LOCATION,
)
from economic_overview.services.scrapers.bea import get_industry_profitability_from_bea
from economic_overview.services.scrapers.common import ScrapedIndustryProfitability
from economic_overview.services.scrapers.eurostat import (
    get_industry_profitability_from_eurostat_sbs,
)
from economic_overview.services.scrapers.jp_cabinet_office import (
    get_industry_gva_from_esri,
)
from economic_overview.services.scrapers.mof import get_industry_profitability_from_mof

logger = logging.getLogger(__name__)


class _IndustryProfitabilityScrapeBatch(TypedDict):
    """One classification/source scrape batch ready for upsert."""

    classification: IndustryClassificationChoices
    source: EconomicDataSourceChoices
    scraped_industry_profitabilities: list[ScrapedIndustryProfitability]


def _scrape_batches_for_location(
    location: EconomicDataLocationChoices,
) -> list[_IndustryProfitabilityScrapeBatch]:
    """Dispatch to the location's survey scrapers (JP returns MOF + ESRI)."""
    match location:
        case EconomicDataLocationChoices.FR:
            return [
                _IndustryProfitabilityScrapeBatch(
                    classification=INDUSTRY_CLASSIFICATION_BY_LOCATION[location],
                    source=EconomicDataSourceChoices.EUROSTAT,
                    scraped_industry_profitabilities=(
                        get_industry_profitability_from_eurostat_sbs()
                    ),
                )
            ]
        case EconomicDataLocationChoices.US:
            return [
                _IndustryProfitabilityScrapeBatch(
                    classification=INDUSTRY_CLASSIFICATION_BY_LOCATION[location],
                    source=EconomicDataSourceChoices.BEA,
                    scraped_industry_profitabilities=(
                        get_industry_profitability_from_bea()
                    ),
                )
            ]
        case EconomicDataLocationChoices.JP:
            return [
                _IndustryProfitabilityScrapeBatch(
                    classification=IndustryClassificationChoices.MOF_CORPORATE_INDUSTRY,
                    source=EconomicDataSourceChoices.MOF,
                    scraped_industry_profitabilities=(
                        get_industry_profitability_from_mof()
                    ),
                ),
                _IndustryProfitabilityScrapeBatch(
                    classification=(
                        IndustryClassificationChoices.ESRI_ECONOMIC_ACTIVITY
                    ),
                    source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
                    scraped_industry_profitabilities=get_industry_gva_from_esri(),
                ),
            ]
        case _:
            return []


def upsert_industry_profitabilities(
    location: EconomicDataLocationChoices,
    scraped_industry_profitabilities: list[ScrapedIndustryProfitability],
    *,
    classification: IndustryClassificationChoices,
    source: EconomicDataSourceChoices,
) -> int:
    """Upsert scraped industry-year profitabilities for one location × classification."""
    if not scraped_industry_profitabilities:
        return 0
    base_unit = INDUSTRY_PROFITABILITY_UNIT_BY_LOCATION[location]
    base_currency = INDUSTRY_PROFITABILITY_CURRENCY_BY_LOCATION[location]
    upserted_count = 0
    for scraped_industry_profitability in scraped_industry_profitabilities:
        period = scraped_industry_profitability["period"]
        if period.year < INDUSTRY_PROFITABILITY_START_YEAR:
            continue
        IndustryProfitabilityModel.objects.update_or_create(
            location=location.value,
            classification=classification.value,
            industry_code=scraped_industry_profitability["industry_code"],
            period=period,
            defaults={
                "industry_label": scraped_industry_profitability["industry_label"],
                "turnover": scraped_industry_profitability["turnover"],
                "operating_profit": scraped_industry_profitability["operating_profit"],
                "gva": scraped_industry_profitability["gva"],
                "base_unit": base_unit.value,
                "base_currency": base_currency.value,
                "source": source.value,
            },
        )
        upserted_count += 1
    IndustryProfitabilityModel.objects.filter(
        location=location.value,
        classification=classification.value,
        period__year__lt=INDUSTRY_PROFITABILITY_START_YEAR,
    ).delete()
    return upserted_count


class IndustryProfitabilityIngestStatus(str, Enum):
    """Per-location outcome for one industry profitability ingest run."""

    SUCCESS = "success"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    SKIPPED = "skipped"


class IndustryProfitabilityLocationResult(TypedDict):
    """Ingest result for one charts location."""

    location: str
    status: str
    upserted_count: int
    message: str


class IndustryProfitabilityIngestReport(TypedDict):
    """Summary returned by the industry profitability Celery task."""

    as_of: str
    status: str
    message: str
    results: list[IndustryProfitabilityLocationResult]


def ingest_industry_profitability_for_location(
    location: EconomicDataLocationChoices,
) -> IndustryProfitabilityLocationResult:
    """Scrape and upsert industry profitability for one location."""
    try:
        upserted_count = 0
        for scrape_batch in _scrape_batches_for_location(location):
            upserted_count += upsert_industry_profitabilities(
                location,
                scrape_batch["scraped_industry_profitabilities"],
                classification=scrape_batch["classification"],
                source=scrape_batch["source"],
            )
        if upserted_count == 0:
            return IndustryProfitabilityLocationResult(
                location=location.value,
                status=IndustryProfitabilityIngestStatus.UNCHANGED.value,
                upserted_count=0,
                message="No industry profitability scraped.",
            )
        return IndustryProfitabilityLocationResult(
            location=location.value,
            status=IndustryProfitabilityIngestStatus.SUCCESS.value,
            upserted_count=upserted_count,
            message=(
                f"Upserted {upserted_count} industry-year profitability figure(s)."
            ),
        )
    except Exception as exc:
        logger.exception(
            "Industry profitability ingest failed for %s: %s",
            location.value,
            exc,
        )
        return IndustryProfitabilityLocationResult(
            location=location.value,
            status=IndustryProfitabilityIngestStatus.FAILED.value,
            upserted_count=0,
            message=str(exc),
        )


def ingest_industry_profitability(
    *,
    as_of: date | None = None,
    force: bool = False,
) -> IndustryProfitabilityIngestReport:
    """Ingest US / FR / JP industry profitability tables.

    Normally only runs on calendar day 1. Pass 'force=True' to run on any day
    (manual runs and tests).
    """
    reference_date = as_of if as_of is not None else get_local_today()
    if not force and reference_date.day != 1:
        message = (
            f"Skipped: {reference_date.isoformat()} is not the first calendar day "
            f"of the month."
        )
        logger.info(message)
        return IndustryProfitabilityIngestReport(
            as_of=reference_date.isoformat(),
            status=IndustryProfitabilityIngestStatus.SKIPPED.value,
            message=message,
            results=[],
        )

    results = [
        ingest_industry_profitability_for_location(location)
        for location in INDUSTRY_PROFITABILITY_LOCATIONS
    ]
    failed = [
        result["location"]
        for result in results
        if result["status"] == IndustryProfitabilityIngestStatus.FAILED.value
    ]
    succeeded = [
        result["location"]
        for result in results
        if result["status"] == IndustryProfitabilityIngestStatus.SUCCESS.value
    ]
    message = (
        f"Industry profitability ingest: {len(succeeded)} location(s) updated, "
        f"{len(failed)} failed."
    )
    logger.info(message)
    return IndustryProfitabilityIngestReport(
        as_of=reference_date.isoformat(),
        status=(
            IndustryProfitabilityIngestStatus.FAILED.value
            if failed and not succeeded
            else IndustryProfitabilityIngestStatus.SUCCESS.value
        ),
        message=message,
        results=results,
    )
