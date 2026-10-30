"""Orchestrate economic data scraping and ingestion into the database."""

from collections.abc import Callable
from datetime import date
from typing import TypedDict

from django.db.models import QuerySet

import core.services as core_services
from core.services import logger
from economic_overview.models import (
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.boj import get_data_from_boj
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.eurostat import get_data_from_eurostat
from economic_overview.services.scrapers.fred import get_data_from_fred
from economic_overview.services.scrapers.insee import get_data_from_insee
from economic_overview.services.scrapers.jp_cabinet_office import (
    get_data_from_japan_cabinet_office,
)
from economic_overview.services.scrapers.mlit import get_data_from_mlit
from economic_overview.services.scrapers.stat_of_jp import get_data_from_stat_of_jp

SOURCE_SCRAP_MAP: dict[
    EconomicDataSourceChoices,
    Callable[
        [str, str | None, EconomicPublicationFrequencyChoices, str],
        list[ScrapingResult],
    ],
] = {
    EconomicDataSourceChoices.INSEE: lambda t, p, f, _location: get_data_from_insee(
        t, p, f
    ),
    EconomicDataSourceChoices.EUROSTAT: lambda t, p, f, location: get_data_from_eurostat(
        t, p, f, location
    ),
    EconomicDataSourceChoices.FRED: lambda t, p, f, _location: get_data_from_fred(
        t, p, f
    ),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda t, p, f, _location: get_data_from_japan_cabinet_office(
        t, p, f
    ),
    EconomicDataSourceChoices.STAT_OF_JP: lambda t, p, f, _location: get_data_from_stat_of_jp(
        t, p, f
    ),
    EconomicDataSourceChoices.MLIT: lambda t, p, f, _location: get_data_from_mlit(
        t, p, f
    ),
    EconomicDataSourceChoices.BOJ: lambda t, p, f, _location: get_data_from_boj(
        t, p, f
    ),
}


def get_economic_data_ingestion_lock_key() -> str:
    """Return Redis lock key for economic data ingestion."""
    return "lock:economic_data_ingestion"


class EconomicData(TypedDict):
    """Economic data dictionnary."""

    indicator: EconomicIndicatorInformationModel
    period: date | None
    data_value: float | None
    comment: str | None


def _get_economic_data(
    indicator: EconomicIndicatorInformationModel, period: str | None = None
) -> EconomicData:
    """Get economic data from scraping function (latest or a specific period)."""
    scraping_function = SOURCE_SCRAP_MAP.get(
        EconomicDataSourceChoices(indicator.source)
    )
    economic_data: list[ScrapingResult] = (
        scraping_function(
            indicator.ticker,
            period,
            EconomicPublicationFrequencyChoices(indicator.frequency),
            indicator.location,
        )
        if scraping_function
        else [
            ScrapingResult(
                period=None, data_value=None, comment="No scraping function found."
            )
        ]
    )
    scraping_result = (
        economic_data[0]
        if economic_data
        else ScrapingResult(period=None, data_value=None, comment="No value found.")
    )
    if not scraping_result.get("data_value"):
        logger.warning("No value found.")
    return EconomicData(
        indicator=indicator,
        period=scraping_result.get("period"),
        data_value=scraping_result.get("data_value"),
        comment=scraping_result.get("comment"),
    )


def _upsert_economic_data_item(
    indicator: EconomicIndicatorInformationModel,
    period: date | None,
    data_value: float | None,
    comment: str | None,
) -> bool:
    """Upsert one economic data item and return whether a value was stored."""
    is_success = data_value is not None
    core_services.upsert_with_logs(
        model=EconomicDataModel,
        log_model=EconomicDataUpdateLogModel,
        lookup_kwargs={"indicator": indicator, "period": period},
        updates={
            "logs": f"Automated data update on {indicator.ticker}.",
            "data_value": data_value,
            "comment": comment,
        },
        logging_on_fields=["data_value"],
        none_skip_fields=["data_value"],
    )
    return is_success


def _ingest_single_economic_data(
    indicator: EconomicIndicatorInformationModel, target_period: str | None = None
) -> bool:
    """Ingest a single (latest or period-specific) economic data item."""
    data = _get_economic_data(indicator, target_period)
    return _upsert_economic_data_item(
        indicator=data["indicator"],
        period=data["period"],
        data_value=data["data_value"],
        comment=data["comment"],
    )


def ingest_latest_economic_data(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
) -> list[str]:
    """Ingest the latest economic data for each indicator."""
    economic_data_not_updated = []
    for indicator in indicators:
        logger.info(f"Ingesting latest economic data for indicator: {indicator.name}")
        is_success = _ingest_single_economic_data(indicator)
        if not is_success:
            economic_data_not_updated.append(indicator.name)
    return economic_data_not_updated


class SpecificEconomicDataNotUpdatedItem(TypedDict):
    """Specific Economic Data Not Updated."""

    indicator: str
    period: str


def ingest_specific_economic_data(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
    periods: list[list[str]],
) -> list[SpecificEconomicDataNotUpdatedItem]:
    """Ingest specific economic data for indicators and target periods."""
    economic_data_not_updated = []
    for indicator, period_list in zip(indicators, periods):
        for target_period in period_list:
            logger.info(
                f"Ingesting economic data for indicator: {indicator.name} and period: {target_period}"
            )
            is_success = _ingest_single_economic_data(indicator, target_period)
            if not is_success:
                economic_data_not_updated.append(
                    SpecificEconomicDataNotUpdatedItem(
                        indicator=indicator.name,
                        period=target_period,
                    )
                )
    return economic_data_not_updated


def ingest_historical_economic_data(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
    start_date: date,
    end_date: date,
) -> list[SpecificEconomicDataNotUpdatedItem]:
    """Ingest all economic data in [start_date, end_date] for each indicator."""
    economic_data_not_updated: list[SpecificEconomicDataNotUpdatedItem] = []
    window_label = f"{start_date.isoformat()}/{end_date.isoformat()}"
    for indicator in indicators:
        logger.info(
            f"Ingesting historical economic data for indicator: {indicator.name} "
            f"from {start_date} to {end_date}"
        )
        scraping_function = SOURCE_SCRAP_MAP.get(
            EconomicDataSourceChoices(indicator.source)
        )
        if not scraping_function:
            economic_data_not_updated.append(
                SpecificEconomicDataNotUpdatedItem(
                    indicator=indicator.name,
                    period=window_label,
                )
            )
            continue

        economic_data = scraping_function(
            indicator.ticker,
            None,
            EconomicPublicationFrequencyChoices(indicator.frequency),
            indicator.location,
        )
        has_been_upserted = False
        for economic_data_item in economic_data:
            period = economic_data_item.get("period")
            data_value = economic_data_item.get("data_value")
            if period is None or data_value is None:
                continue
            if not (start_date <= period <= end_date):
                continue
            _upsert_economic_data_item(
                indicator=indicator,
                period=period,
                data_value=data_value,
                comment=economic_data_item.get("comment"),
            )
            has_been_upserted = True

        if not has_been_upserted:
            economic_data_not_updated.append(
                SpecificEconomicDataNotUpdatedItem(
                    indicator=indicator.name,
                    period=window_label,
                )
            )
    return economic_data_not_updated
