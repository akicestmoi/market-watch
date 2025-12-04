import json
from datetime import date
from typing import List, Optional, TypedDict

from django.db.models import F, Max, OuterRef, QuerySet, Subquery

from central_banks_overview.models import CentralBankChoices, CentralBankDataModel
from central_banks_overview.services.cb_meetings_services import (
    get_central_bank_next_meeting_date,
)
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


class CentralBankDataDates(TypedDict):
    """Central Bank Data Dates."""

    central_bank: CentralBankChoices
    date: date


class CentralBankBaseInfo(TypedDict):
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


def _get_central_bank_base_info() -> List[CentralBankBaseInfo]:
    """Get central bank base info."""
    with open("central_banks_overview/data_sources/central_banks_data.json") as f:
        return [CentralBankBaseInfo(**data) for data in json.load(f)]


def get_all_central_bank_data_dates(
    requested_central_banks: List[CentralBankDataDates],
) -> List[CentralBankDataDates]:
    """Get all central bank data dates."""
    central_bank_dates: List[CentralBankDataDates] = []
    for central_bank in CentralBankChoices:
        for request in requested_central_banks:
            if request["central_bank"] == central_bank:
                central_bank_dates.append(
                    CentralBankDataDates(
                        central_bank=CentralBankChoices(central_bank),
                        date=request["date"],
                    )
                )
            else:
                next_meeting_date = get_central_bank_next_meeting_date(
                    CentralBankChoices(central_bank)
                )
                if next_meeting_date:
                    central_bank_dates.append(
                        CentralBankDataDates(
                            central_bank=CentralBankChoices(central_bank),
                            date=next_meeting_date.date(),
                        )
                    )
    return central_bank_dates


def get_specific_central_bank_data(
    target_date: date, central_bank_data: CentralBankBaseInfo
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
    central_bank_data_dates: List[CentralBankDataDates],
) -> List[CentralBankDataIngestionResponseItem]:
    """Ingest central bank data."""
    central_bank_data_updated = []
    central_bank_base_info = _get_central_bank_base_info()

    for central_bank_data in central_bank_base_info:
        central_bank_data_date = next(
            (
                central_bank_data_date["date"]
                for central_bank_data_date in central_bank_data_dates
                if central_bank_data_date["central_bank"]
                == central_bank_data["central_bank"]
            ),
            None,
        )
        if not central_bank_data_date:
            logger.warning(
                f"No central bank data date found for {central_bank_data['central_bank']}"
            )
            continue

        data = get_specific_central_bank_data(central_bank_data_date, central_bank_data)
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
                data_name=central_bank_data["full_name"], date=central_bank_data_date
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
