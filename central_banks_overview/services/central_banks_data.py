"""Ingest and query central bank policy-rate / balance-sheet style series."""

import json
from collections.abc import Callable
from datetime import date
from typing import TypedDict

from django.db.models import F, Max, OuterRef, QuerySet, Subquery
from pydantic import TypeAdapter, ValidationError

from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankDataModel,
    CentralBankMeetingModel,
)
from central_banks_overview.services.config import CENTRAL_BANKS_DATA_JSON
from core.services import (
    ValueChangeType,
    calculate_value_change,
    convert_to_display_timezone,
    logger,
)
from market_overview.models import PriceSourceChoices
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.global_rates import scrap_from_global_rates
from market_overview.services.scrapers.webstat import get_webstat_rates

CENTRAL_BANK_DATA_MAP: dict[
    PriceSourceChoices, Callable[[date, str], ScrapingResult]
] = {
    PriceSourceChoices.WEBSTAT: lambda d, t: get_webstat_rates(d, t),
    PriceSourceChoices.GLOBAL_RATES: lambda d, t: scrap_from_global_rates(d, t),
}


def get_cb_data_ingestion_lock_key(
    central_bank: CentralBankChoices, price_date: date
) -> str:
    """Return Redis lock key for central-bank data ingestion."""
    return f"lock:cb_data_ingestion:{central_bank.value}:{price_date.isoformat()}"


class _CentralBankDataBaseInfo(TypedDict):
    """Static series metadata loaded from 'central_banks_data.json'."""

    cb_data_id: int
    central_bank: CentralBankChoices
    short_name: str
    full_name: str
    ticker: str
    source: PriceSourceChoices


class _CentralBankData(TypedDict):
    """Scraped key-rate values ready to upsert for one series and date."""

    cb_data_id: int
    central_bank: CentralBankChoices
    short_name: str
    full_name: str
    date: date
    value: float | None
    comment: str | None


class _CentralBankDataUpsertDefaults(TypedDict):
    """Fields updated on an existing 'CentralBankDataModel' during upsert."""

    value: float | None
    comment: str | None


class _CentralBankDataIngestionResponseItem(TypedDict):
    """One series that was upserted during a key-rate ingest run."""

    data_name: str
    date: date


_CENTRAL_BANK_BASE_INFO_ADAPTER = TypeAdapter(list[_CentralBankDataBaseInfo])


def _get_central_bank_base_info() -> list[_CentralBankDataBaseInfo]:
    """Load and validate series metadata from 'central_banks_data.json'."""
    with open(CENTRAL_BANKS_DATA_JSON) as f:
        raw_payload = json.load(f)
    try:
        return _CENTRAL_BANK_BASE_INFO_ADAPTER.validate_python(raw_payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid central_banks_data.json: {exc}") from exc


def _get_specific_central_bank_data(
    target_date: date, central_bank_series: _CentralBankDataBaseInfo
) -> _CentralBankData:
    """Scrape one central-bank series for 'target_date' and return upsert values."""
    logger.info(
        f"Ingesting central bank data for {central_bank_series['short_name']} "
        f"on {target_date}"
    )
    scraping_function = CENTRAL_BANK_DATA_MAP.get(central_bank_series["source"])
    scraping_result: ScrapingResult = (
        scraping_function(target_date, central_bank_series["ticker"])
        if scraping_function
        else ScrapingResult(price=None, comment="No scraping function found.")
    )

    if not scraping_result.get("price"):
        logger.warning("No price found.")

    return _CentralBankData(
        cb_data_id=central_bank_series["cb_data_id"],
        central_bank=central_bank_series["central_bank"],
        short_name=central_bank_series["short_name"],
        full_name=central_bank_series["full_name"],
        date=target_date,
        value=scraping_result.get("price"),
        comment=scraping_result.get("comment"),
    )


def ingest_central_bank_data(
    central_bank: CentralBankChoices,
    date_to_ingest: date,
    all_series_info: list[_CentralBankDataBaseInfo] | None = None,
) -> list[_CentralBankDataIngestionResponseItem]:
    """Upsert key-rate series for one central bank on 'date_to_ingest'.

    Pass 'all_series_info' when calling from a multi-bank loop so the JSON file is
    loaded once; otherwise the catalog is loaded here.
    """
    central_bank_data_updated: list[_CentralBankDataIngestionResponseItem] = []
    if all_series_info is None:
        all_series_info = _get_central_bank_base_info()
    for series_info in all_series_info:
        if series_info["central_bank"] != central_bank:
            continue
        scraped_key_rate = _get_specific_central_bank_data(date_to_ingest, series_info)
        upsert_defaults = _CentralBankDataUpsertDefaults(
            value=scraped_key_rate["value"],
            comment=scraped_key_rate["comment"],
        )
        CentralBankDataModel.objects.update_or_create(
            central_bank=scraped_key_rate["central_bank"],
            short_name=scraped_key_rate["short_name"],
            full_name=scraped_key_rate["full_name"],
            date=scraped_key_rate["date"],
            cb_data_id=scraped_key_rate["cb_data_id"],
            defaults=upsert_defaults,
        )
        central_bank_data_updated.append(
            _CentralBankDataIngestionResponseItem(
                data_name=series_info["full_name"], date=date_to_ingest
            )
        )
    return central_bank_data_updated


class CentralBankDataDate(TypedDict):
    """One central bank and the date whose key rates should be ingested."""

    central_bank: CentralBankChoices
    date: date


def ingest_requested_central_bank_data(
    dates_to_ingest_by_central_bank: list[CentralBankDataDate],
) -> list[_CentralBankDataIngestionResponseItem]:
    """Upsert key rates for each requested central-bank / date pair."""
    central_bank_data_updated: list[_CentralBankDataIngestionResponseItem] = []
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
    target_date: date | None = None,
    central_banks: list[CentralBankChoices] | None = None,
    last_value: bool = False,
) -> QuerySet[CentralBankDataModel]:
    """Return stored key-rate series, optionally filtered by date or bank."""
    central_bank_data = CentralBankDataModel.objects.all()

    if central_banks:
        central_bank_data = central_bank_data.filter(central_bank__in=central_banks)

    if last_value and target_date:
        raise ValueError("Last value is not supported when target date is provided.")

    if last_value:
        # This subquery finds the max date for each short_name.
        max_date_subquery = (
            CentralBankDataModel.objects.filter(short_name=OuterRef("short_name"))
            .values("short_name")
            .annotate(max_date=Max("date"))
            .values("max_date")
        )
        # Subquery.values returns one aggregated max date; [:1] keeps that single cell.
        central_bank_data = (
            central_bank_data.annotate(max_date=Subquery(max_date_subquery[:1]))
            .filter(date=F("max_date"))
            .distinct("short_name")
            .order_by("short_name", "-date")
        )
    elif target_date:
        central_bank_data = central_bank_data.filter(date=target_date)

    return central_bank_data


def delete_central_bank_data(ids: list[int]) -> int:
    """Delete central-bank key-rate series by primary key and return how many matched."""
    queryset = CentralBankDataModel.objects.filter(pk__in=ids)
    deleted_count = queryset.count()
    queryset.delete()
    return deleted_count


def get_previous_central_bank_rate(
    short_name: str, event_date: date
) -> CentralBankDataModel | None:
    """Return the latest key rate strictly before a given date."""
    return (
        CentralBankDataModel.objects.filter(
            short_name=short_name,
            date__lt=event_date,
        )
        .order_by("-date")
        .first()
    )


def list_central_banks_with_meetings_at_date(
    event_date: date,
) -> list[CentralBankChoices]:
    """Return central banks with a meeting at the display calendar date."""
    central_banks: list[CentralBankChoices] = []
    seen_central_banks: set[CentralBankChoices] = set()
    for meeting in CentralBankMeetingModel.objects.all().order_by(
        "central_bank", "date"
    ):
        if convert_to_display_timezone(meeting.date).date() != event_date:
            continue
        central_bank = CentralBankChoices(meeting.central_bank)
        if central_bank in seen_central_banks:
            continue
        seen_central_banks.add(central_bank)
        central_banks.append(central_bank)
    return central_banks


class _DecisionDayKeyRate(TypedDict):
    """One key policy rate on a monetary-policy decision day."""

    central_bank: CentralBankChoices
    short_name: str
    full_name: str
    current_value: float | None
    previous_value: float | None
    change_value: float | None


def get_decision_day_key_rates(event_date: date) -> list[_DecisionDayKeyRate]:
    """Return key rates for CB meetings whose display calendar date is 'event_date'.

    Returns one key rate per series on that date, with current, previous, and
    absolute change. Returns an empty list when there is no meeting that day or
    rates are not ingested yet.
    """
    decision_day_key_rates: list[_DecisionDayKeyRate] = []
    for central_bank in list_central_banks_with_meetings_at_date(event_date):
        key_rates = list(
            get_central_bank_data(
                target_date=event_date,
                central_banks=[central_bank],
            ).order_by("cb_data_id", "short_name")
        )
        for key_rate in key_rates:
            previous_key_rate = get_previous_central_bank_rate(
                key_rate.short_name, event_date
            )
            previous_value = previous_key_rate.value if previous_key_rate else None
            decision_day_key_rates.append(
                _DecisionDayKeyRate(
                    central_bank=central_bank,
                    short_name=key_rate.short_name,
                    full_name=key_rate.full_name,
                    current_value=key_rate.value,
                    previous_value=previous_value,
                    change_value=calculate_value_change(
                        key_rate.value,
                        previous_value,
                        ValueChangeType.ABSOLUTE,
                    ),
                )
            )
    return decision_day_key_rates
