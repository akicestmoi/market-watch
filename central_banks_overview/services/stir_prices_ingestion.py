"""Ingest, query, and bulk-update STIR futures prices used for rate-path inference."""

from collections.abc import Hashable
from datetime import date, datetime
from io import BytesIO
from typing import Literal, TypedDict

import pandas as pd

import core.services as core_services
from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesPriceUpdateLogModel,
)
from central_banks_overview.services.scrapers.common import StirFutures
from central_banks_overview.services.scrapers.fedfunds_futures import (
    get_fedfunds_futures_prices,
)
from central_banks_overview.services.scrapers.tfx_mutan_futures import (
    get_mutan_futures_prices,
)
from core.services import logger

EXPECTED_CSV_COLUMNS: tuple[
    Literal["date"],
    Literal["short_name"],
    Literal["maturity"],
    Literal["price"],
    Literal["logs"],
] = ("date", "short_name", "maturity", "price", "logs")
# Pandas DtypeArg needs dict[Hashable, ...]; invariance blocks TypedDict/Literal keys.
STIR_FUTURES_CSV_DTYPES: dict[Hashable, type[str]] = {
    column: str for column in EXPECTED_CSV_COLUMNS
}

STIR_FUTURES_PRICES_MAP = {
    CentralBankChoices.FRB: lambda price_date: get_fedfunds_futures_prices(price_date),
    CentralBankChoices.BOJ: lambda price_date: get_mutan_futures_prices(price_date),
}


def get_stir_price_ingestion_lock_key(price_date: date) -> str:
    """Return Redis lock key for STIR price ingestion."""
    return f"lock:stir_price_ingestion:{price_date.isoformat()}"


def extract_all_stir_futures_prices(price_date: date) -> list[StirFutures]:
    """Get all Stir Futures Prices."""
    stir_futures_prices = []
    for central_bank in CentralBankChoices:
        if central_bank not in STIR_FUTURES_PRICES_MAP:
            continue
        logger.info(f"Extracting Stir Futures Prices for {central_bank}")
        stir_futures_prices.extend(STIR_FUTURES_PRICES_MAP[central_bank](price_date))
    return stir_futures_prices


def ingest_stir_futures_prices(
    stir_futures_prices: list[StirFutures],
) -> list[StirFutures]:
    """Ingest Stir Futures Prices."""
    stir_futures_updated: list[StirFutures] = []
    for stir_future_price in stir_futures_prices:
        date = stir_future_price["date"]
        maturity = stir_future_price["maturity"]
        name = stir_future_price["short_name"]
        price = stir_future_price["price"]
        core_services.upsert_with_logs(
            model=StirFuturesModel,
            log_model=StirFuturesPriceUpdateLogModel,
            lookup_kwargs={
                "central_bank": stir_future_price["central_bank"],
                "full_name": stir_future_price["full_name"],
                "date": date,
                "short_name": name,
                "maturity": maturity,
                "first_accrual_date": stir_future_price["first_accrual_date"],
                "last_accrual_date": stir_future_price["last_accrual_date"],
                "source": stir_future_price["source"],
            },
            updates={
                "logs": f"Automated price update on {name} of maturity: {maturity} to price: {price}.",
                "price": price,
                "comment": stir_future_price["comment"],
            },
            logging_on_fields=["price"],
            none_skip_fields=["price"],
        )
        if price:
            stir_futures_updated.append(stir_future_price)
    return stir_futures_updated


def get_futures_prices(
    price_date: date, central_banks: list[CentralBankChoices] = []
) -> list[StirFuturesModel]:
    """Get futures prices for a given date and central banks."""
    query = StirFuturesModel.objects.filter(date=price_date)
    if central_banks:
        query = query.filter(central_bank__in=central_banks)
    return list(query.order_by("central_bank", "maturity"))


def delete_stir_futures_prices(ids: list[int]) -> int:
    """Delete STIR futures prices."""
    futures_queryset = StirFuturesModel.objects.filter(pk__in=ids)
    deleted_count = futures_queryset.count()
    futures_queryset.delete()
    return deleted_count


class BulkUpdateFuturesPricesItem(TypedDict):
    """Bulk update futures prices dictionnary."""

    date: date
    short_name: str
    maturity: str
    price: float
    logs: str | None


def bulk_update_futures_prices(
    updates: list[BulkUpdateFuturesPricesItem],
) -> list[StirFuturesModel]:
    """Bulk update futures prices."""
    updated_futures = []
    for update in updates:
        future = StirFuturesModel.objects.get(
            date=update["date"],
            short_name=update["short_name"],
            maturity=update["maturity"],
        )
        updated_futures.append(
            core_services.update_with_logs(
                model_to_update=future,
                log_model=StirFuturesPriceUpdateLogModel,
                updates={
                    "logs": update["logs"],
                    "price": update["price"],
                    "comment": update["logs"],
                },
                logging_on_fields=["price"],
                none_skip_fields=["price"],
            )
        )
    return updated_futures


def bulk_update_futures_prices_from_csv(
    csv_file: bytes,
) -> list[StirFuturesModel]:
    """Bulk update futures prices from a CSV file."""
    df = pd.read_csv(BytesIO(csv_file), dtype=STIR_FUTURES_CSV_DTYPES)
    df.fillna("", inplace=True)

    missing_columns = [
        column for column in EXPECTED_CSV_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"CSV file must have the following columns: "
            f"{', '.join(sorted(missing_columns))}."
        )

    updates = [
        BulkUpdateFuturesPricesItem(
            date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
            short_name=row["short_name"],
            maturity=row["maturity"],
            price=float(row["price"]),
            logs=(
                row["logs"]
                if row["logs"]
                else (
                    f"Bulk update from CSV file of {row['short_name']} "
                    f"to price: {row['price']}."
                )
            ),
        )
        for row in df.to_dict(orient="records")
    ]
    return bulk_update_futures_prices(updates)


def delete_stir_futures_price_update_logs_before_date(logs_date: date):
    """Delete stir futures price update logs before a given date."""
    StirFuturesPriceUpdateLogModel.objects.filter(date_added__lt=logs_date).delete()


def delete_stir_futures_prices_before_date(
    central_bank: CentralBankChoices, price_date: date
):
    """Delete stir futures prices before a given date and for a given central bank."""
    StirFuturesModel.objects.filter(
        central_bank=central_bank, date__lt=price_date
    ).delete()
