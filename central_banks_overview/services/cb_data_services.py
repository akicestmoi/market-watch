import json
from datetime import date
from typing import List, Optional, TypedDict

from django.db.models import F, Max, OuterRef, QuerySet, Subquery

from central_banks_overview.models import CentralBankChoices, CentralBankDataModel
from core.services import logger
from market_overview.models import PriceSourceChoices
from market_overview.services.price_ingestion_services import (
    ScrapingResult,
    get_webstat_rates,
    scrap_from_global_rates,
)

CENTRAL_BANK_DATA_MAP = {
    PriceSourceChoices.WEBSTAT: lambda d, t: get_webstat_rates(d, t),
    PriceSourceChoices.GLOBAL_RATES: lambda d, t: scrap_from_global_rates(d, t),
}


class CentralBankDataDate(TypedDict):
    """Central Bank Data Dates."""

    central_bank: CentralBankChoices
    date: date


class CentralBankDataBaseInfo(TypedDict):
    """Central Bank Data Information."""

    cb_data_id: int
    central_bank: CentralBankChoices
    short_name: str
    full_name: str
    ticker: str
    source: PriceSourceChoices


class CentralBankData(TypedDict):
    """Central Bank Data."""

    cb_data_id: int
    central_bank: CentralBankChoices
    short_name: str
    full_name: str
    date: date
    value: Optional[float]
    comment: Optional[str]


class CentralBankDataIngestionResponseItem(TypedDict):
    """Central Bank Data Ingestion Response Item."""

    data_name: str
    date: date


def _get_central_bank_base_info() -> List[CentralBankDataBaseInfo]:
    """Get central bank base info."""
    with open("central_banks_overview/data_sources/central_banks_data.json") as f:
        return [CentralBankDataBaseInfo(**data) for data in json.load(f)]


def _get_specific_central_bank_data(
    target_date: date, central_bank_data: CentralBankDataBaseInfo
) -> CentralBankData:
    """Ingest central bank data."""
    logger.info(
        f"Ingesting central bank data for {central_bank_data['short_name']} on {target_date}"
    )
    scraping_function = CENTRAL_BANK_DATA_MAP.get(central_bank_data["source"])
    scraping_result: ScrapingResult = (
        scraping_function(target_date, central_bank_data["ticker"])
        if scraping_function
        else ScrapingResult(price=None, comment="No scraping function found.")
    )

    if not scraping_result.get("price"):
        logger.warning("No price found.")

    return CentralBankData(
        cb_data_id=central_bank_data["cb_data_id"],
        central_bank=central_bank_data["central_bank"],
        short_name=central_bank_data["short_name"],
        full_name=central_bank_data["full_name"],
        date=target_date,
        value=scraping_result.get("price"),
        comment=scraping_result.get("comment"),
    )


def ingest_central_bank_data(
    central_bank: CentralBankChoices,
    date_to_ingest: date,
    all_data_info: List[CentralBankDataBaseInfo] = [],
) -> List[CentralBankDataIngestionResponseItem]:
    """Ingest central bank data.

    The function can act as a standalone function or
    as part of the ingest_all_central_bank_data function.
    """
    central_bank_data_updated = []
    if not all_data_info:
        all_data_info = _get_central_bank_base_info()
    for data_info in all_data_info:
        if data_info["central_bank"] == central_bank:
            data = _get_specific_central_bank_data(date_to_ingest, data_info)
            CentralBankDataModel.objects.update_or_create(
                central_bank=data["central_bank"],
                short_name=data["short_name"],
                full_name=data["full_name"],
                date=data["date"],
                cb_data_id=data["cb_data_id"],
                defaults={
                    "value": data["value"],
                    "comment": data["comment"],
                },
            )
            central_bank_data_updated.append(
                CentralBankDataIngestionResponseItem(
                    data_name=data_info["full_name"], date=date_to_ingest
                )
            )
    return central_bank_data_updated


def ingest_requested_central_bank_data(
    dates_to_ingest_by_central_bank: List[CentralBankDataDate],
) -> List[CentralBankDataIngestionResponseItem]:
    """Ingest central bank data."""
    central_bank_data_updated = []
    central_bank_base_info = _get_central_bank_base_info()

    for central_bank_data_date in dates_to_ingest_by_central_bank:
        central_bank = central_bank_data_date["central_bank"]
        date_to_ingest = central_bank_data_date["date"]
        central_bank_data_updated.extend(
            ingest_central_bank_data(
                central_bank, date_to_ingest, central_bank_base_info
            )
        )
    return central_bank_data_updated


def get_central_bank_data(
    target_date: Optional[date] = None,
    central_banks: List[CentralBankChoices] = [],
    last_value: bool = False,
) -> QuerySet[CentralBankDataModel]:
    """Get central bank data."""
    central_bank_data = CentralBankDataModel.objects.all()

    if central_banks:
        central_bank_data = central_bank_data.filter(central_bank__in=central_banks)

    if last_value and target_date:
        raise ValueError("Last value is not supported when target date is provided.")

    if last_value:
        # This subquery finds the max date for each short_name
        max_date_subquery = (
            CentralBankDataModel.objects.filter(short_name=OuterRef("short_name"))
            .values("short_name")
            .annotate(max_date=Max("date"))
            .values("max_date")
        )
        central_bank_data = (
            central_bank_data.annotate(max_date=Subquery(max_date_subquery[:1]))
            .filter(date=F("max_date"))
            .distinct("short_name")
            .order_by("short_name", "-date")
        )
    elif target_date:
        central_bank_data = central_bank_data.filter(date=target_date)

    return central_bank_data


def delete_central_bank_data(ids: List[int]) -> int:
    """Delete central bank data by IDs."""
    queryset = CentralBankDataModel.objects.filter(pk__in=ids)
    deleted_count = queryset.count()
    queryset.delete()
    return deleted_count
