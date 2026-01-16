import re
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import List, Optional, Tuple, TypedDict

import pandas as pd
import pdfplumber  # type: ignore[reportMissingImports]
import requests
from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import BDay, MonthBegin, MonthEnd

import core.services as core_services
from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesModel,
    StirFuturesNameChoices,
    StirFuturesPriceUpdateLogModel,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.cb_meetings_services import (
    MONTH_ABBREVIATIONS,
    get_central_bank_next_meeting_date,
)
from core.services import CACHE_MAXSIZE, CACHE_TTL_SECONDS, logger
from market_overview.services.price_ingestion_services import (
    get_yahoo_finance_closing_prices,
)

MONTH_CODE = {
    "Jan": "F",
    "Feb": "G",
    "Mar": "H",
    "Apr": "J",
    "May": "K",
    "Jun": "M",
    "Jul": "N",
    "Aug": "Q",
    "Sep": "U",
    "Oct": "V",
    "Nov": "X",
    "Dec": "Z",
}

FF_FUTURES_PREFIX = "ZQ"
FF_FUTURES_SUFFIX = ".CBT"
FED_FUNDS_FUTURES_MONTHS = 15  # Number of months to fetch (1-15)
TFX_HISTORICAL_LOOKBACK_DAYS = 90

STIR_FUTURES_PRICES_MAP = {
    CentralBankChoices.FRB: lambda t: _get_fedfunds_futures_prices(t),
    CentralBankChoices.BOJ: lambda t: _get_mutan_futures_prices(t),
}


class YFinanceTickerInfo(TypedDict):
    """YFinance Ticker Information."""

    ticker: str
    date: datetime


class StirFutures(TypedDict):
    """Stir Futures Information."""

    central_bank: CentralBankChoices
    short_name: StirFuturesNameChoices
    full_name: str
    maturity: str
    first_accrual_date: Optional[date]
    last_accrual_date: Optional[date]
    date: date
    price: Optional[float]
    source: StirFuturesSourceChoices
    comment: Optional[str]


class BulkUpdateFuturesPricesItem(TypedDict):
    """Bulk update futures prices dictionnary."""

    date: date
    short_name: str
    maturity: str
    price: float
    logs: Optional[str]


def _get_ticker_info_from_maturity_month(maturity_month: int) -> YFinanceTickerInfo:
    """Get the YFinance ticker and date from a maturity month."""
    next_meeting_date = get_central_bank_next_meeting_date(CentralBankChoices.FRB)
    now = datetime.now(timezone.utc)
    month_offset = maturity_month + (
        1 if (next_meeting_date and next_meeting_date < now) else 0
    )
    ticker_date = now + relativedelta(months=month_offset)
    ticker_month = MONTH_CODE[ticker_date.strftime("%b")]
    ticker_year = ticker_date.strftime("%y")
    yfinance_ticker = (
        f"{FF_FUTURES_PREFIX}{ticker_month}{ticker_year}{FF_FUTURES_SUFFIX}"
    )
    return YFinanceTickerInfo(ticker=yfinance_ticker, date=ticker_date)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_fedfunds_futures_price(target_date: date, maturity_month: int) -> StirFutures:
    """Get the price of a Fed Funds Futures contract for a given date.

    Yahoo uses CME prices (CBOT).
    """
    month_start = MonthBegin()
    month_end = MonthEnd()
    yfinance_ticker_info = _get_ticker_info_from_maturity_month(maturity_month)
    yfinance_ticker = yfinance_ticker_info["ticker"]
    ticker_date = yfinance_ticker_info["date"]
    maturity = ticker_date.strftime("%y.%m")

    price = get_yahoo_finance_closing_prices(target_date, yfinance_ticker).get("price")
    if price is None:
        return StirFutures(
            central_bank=CentralBankChoices.FRB,
            short_name=StirFuturesNameChoices.FF1M,
            full_name=str(StirFuturesNameChoices.FF1M.label),
            maturity=maturity,
            first_accrual_date=month_start.rollback(ticker_date).date(),
            last_accrual_date=month_end.rollforward(ticker_date).date(),
            date=target_date,
            price=None,
            source=StirFuturesSourceChoices.YAHOO,
            comment="Yahoo Finance: No prices found.",
        )

    return StirFutures(
        central_bank=CentralBankChoices.FRB,
        short_name=StirFuturesNameChoices.FF1M,
        full_name=str(StirFuturesNameChoices.FF1M.label),
        maturity=maturity,
        first_accrual_date=month_start.rollback(ticker_date).date(),
        last_accrual_date=month_end.rollforward(ticker_date).date(),
        date=target_date,
        price=price,
        source=StirFuturesSourceChoices.YAHOO,
        comment="",
    )


def _get_fedfunds_futures_prices(target_date: date) -> List[StirFutures]:
    """Get the prices of the Fed Funds Futures contracts for a given date."""
    return [
        _get_fedfunds_futures_price(target_date, maturity_month)
        for maturity_month in range(0, FED_FUNDS_FUTURES_MONTHS)
    ]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_mutan_futures_prices_from_tfx(target_date: date) -> pd.DataFrame:
    """Get prices of Mutan STIR Futures from TFX.

    Source: https://www.tfx.co.jp/
    """
    period_start = target_date - timedelta(days=TFX_HISTORICAL_LOOKBACK_DAYS)

    TFX_HISTORICAL_FUTURES_DATA_URL = "https://www.tfx.co.jp/historical/futures/result"
    params = {
        "HistoricalFuturesData[submit_type]": "csv",
        "HistoricalFuturesData[period_start_type]": "date",
        "HistoricalFuturesData[period_end_type]": "date",
        "HistoricalFuturesData[product_type1]": "",
        "HistoricalFuturesData[product_type1][]": "無担保コールオーバーナイト３ヵ月金利先物",
        "HistoricalFuturesData[product_type3]": "",
        "HistoricalFuturesData[product_type2]": "1",
        "HistoricalFuturesData[get_preference_all]": "",
        "HistoricalFuturesData[get_preference]": "",
        "HistoricalFuturesData[get_preference][]": "official_closing_price",
        "HistoricalFuturesData[period_start][year]": str(period_start.year),
        "HistoricalFuturesData[period_start][month]": str(period_start.month),
        "HistoricalFuturesData[period_start][day]": str(period_start.day),
        "HistoricalFuturesData[period_end][year]": str(target_date.year),
        "HistoricalFuturesData[period_end][month]": str(target_date.month),
        "HistoricalFuturesData[period_end][day]": str(target_date.day),
    }

    try:
        response = requests.get(
            TFX_HISTORICAL_FUTURES_DATA_URL, params=params, timeout=30
        )
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch data from TFX: {e}") from e

    lines = response.text.splitlines()
    start_index = next(
        (i for i, line in enumerate[str](lines) if line.startswith("商品名")), None
    )
    if start_index is None:
        raise ValueError("Could not find data header in TFX response")

    csv_data = "\n".join(lines[start_index:])
    future_prices = pd.read_csv(StringIO(csv_data))
    future_prices["限月"] = future_prices["限月"].astype(str)
    future_prices = future_prices[
        future_prices["取引日"] == target_date.strftime("%Y-%m-%d")
    ].reset_index(drop=True)
    return future_prices


def _parse_jp_date(date_str: str) -> Optional[date]:
    """Convert a Japanese date string like '2025年3月21日（木）' to datetime.date.

    Returns None if the date is missing or invalid ('-').
    """
    if not date_str or date_str.strip() in ("-", ""):
        return
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if match:
        year, month, day = map(int, match.groups())
        return datetime(year, month, day).date()


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_mutan_futures_accrual_dates() -> pd.DataFrame:
    """Get accrual dates of Mutan STIR Futures from TFX.

    Source: https://www.tfx.co.jp/
    """
    TFX_HISTORICAL_FUTURES_TRADING_CALENDAR_URL = (
        "https://www.tfx.co.jp/historical/futures/tradingcalendar.html"
    )
    try:
        response = requests.get(TFX_HISTORICAL_FUTURES_TRADING_CALENDAR_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch trading calendar from TFX: {e}") from e

    html = response.content.decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="snd_table01b")

    if table is None or not isinstance(table, Tag):
        raise ValueError("Could not find trading calendar table in TFX response")

    rows = []
    current_year = None

    for tr in table.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        tds = tr.find_all("td")
        ths = tr.find_all("th")

        if not tds:
            continue

        if ths and hasattr(ths[0], "attrs") and "rowspan" in ths[0].attrs:
            current_year = ths[0].get_text(strip=True).replace("年", "")

        if len(tds) < 5:
            continue

        month_text = tds[0].get_text(strip=True)
        ref_period = tds[3].get_text(strip=True)

        ref_period_split = ref_period.split("～")
        if len(ref_period_split) < 2:
            continue

        first_accrual_date = _parse_jp_date(ref_period_split[0])
        last_accrual_date = _parse_jp_date(ref_period_split[1])

        # Combine year + month into YY.MM
        # month_text like "3月限" -> "03"
        month_number = month_text.replace("月限", "").zfill(2)
        contract_yy_mm = f"{str(current_year)[-2:]}.{month_number}"

        rows.append(
            {
                "限月": str(contract_yy_mm),
                "first_accrual_date": first_accrual_date,
                "last_accrual_date": last_accrual_date,
            }
        )

    return pd.DataFrame(rows)


def _get_mutan_futures_prices(target_date: date) -> List[StirFutures]:
    """Get the prices of Mutan Futures contracts for a given date.

    Note: Price extraction from the TFX dataframe may need to be implemented
    based on the actual column names in the CSV response.
    """
    future_prices = _get_mutan_futures_prices_from_tfx(target_date)
    accrual_dates = _get_mutan_futures_accrual_dates()

    combined_prices = pd.merge(
        future_prices, accrual_dates, on="限月", how="left"
    ).replace({float("nan"): None})

    return [
        StirFutures(
            central_bank=CentralBankChoices.BOJ,
            short_name=StirFuturesNameChoices.MUTAN3M,
            full_name=str(StirFuturesNameChoices.MUTAN3M.label),
            maturity=row.get("限月", "Maturity not found"),
            first_accrual_date=row.get("first_accrual_date"),
            last_accrual_date=row.get("last_accrual_date"),
            date=target_date,
            price=row.get("公式終値"),
            source=StirFuturesSourceChoices.TFX,
            comment="",
        )
        for _, row in combined_prices.iterrows()
    ]


def _parse_maturity_from_estr_pdf(maturity: str) -> str:
    """Parse maturity from ESTR PDF."""
    if len(maturity) < 5:
        raise ValueError(f"Invalid maturity: {maturity}")
    month_str = maturity[:3].lower()
    year_str = maturity[3:]

    if month_str not in MONTH_ABBREVIATIONS or not year_str.isdigit():
        raise ValueError(f"Invalid maturity: {maturity}")

    return f"{year_str}.{MONTH_ABBREVIATIONS[month_str]:02d}"


def _get_third_wednesday_of_month(year: int, month: int) -> date:
    """Get the third Wednesday of a given month."""
    first_day = date(year, month, 1)

    # weekday() returns 0=Monday, 1=Tuesday, 2=Wednesday, etc.
    first_day_weekday = first_day.weekday()

    # Calculate days to add to get to the first Wednesday
    # (2 - weekday) % 7 correctly handles all cases:
    # - If weekday <= 2: gives days to add within the week
    # - If weekday > 2: gives days to add to reach next week's Wednesday
    days_to_first_wednesday = (2 - first_day_weekday) % 7
    first_wednesday = first_day + timedelta(days=days_to_first_wednesday)
    # Third Wednesday is 14 days after the first Wednesday
    third_wednesday = first_wednesday + timedelta(days=14)
    return third_wednesday


def calculate_estr_reference_dates(maturity: str) -> Tuple[date, date]:
    """Calculate ESTR reference start and end dates from maturity.

    Source: https://www.ice.com/products/82908552/Three-Month-ESTR-Indexed-Future
    """
    try:
        # Parse maturity string "YY.MM" to year and month
        parts = maturity.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid maturity format: {maturity}")

        year_str, month_str = parts
        year = 2000 + int(year_str)
        month = int(month_str)

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month in maturity: {maturity}")

        # Calculate First Accrual Date: Third Wednesday of the delivery month
        first_accrual_date = _get_third_wednesday_of_month(year, month)

        # Calculate Last Accrual Date:
        # Business day prior to the third Wednesday of the third calendar month
        # after the First Accrual Date
        third_month_after = first_accrual_date + relativedelta(months=3)
        third_wednesday_third_month = _get_third_wednesday_of_month(
            third_month_after.year, third_month_after.month
        )
        last_accrual_date = third_wednesday_third_month - BDay(1)

        return first_accrual_date, last_accrual_date.date()

    except (ValueError, IndexError) as e:
        raise ValueError(
            f"Failed to calculate reference dates from maturity {maturity}: {e}"
        ) from e


def extract_estr_prices_from_pdf(
    pdf_file: bytes, price_date: date
) -> List[StirFutures]:
    """Extract ESTR Prices from PDF."""
    try:
        tables = []
        with pdfplumber.open(BytesIO(pdf_file)) as pdf_reader:
            for page in pdf_reader.pages:
                tables.extend(page.extract_tables())
    except Exception as e:
        raise ValueError(f"Failed to parse PDF file: {e}") from e

    stir_futures_prices = []
    for table in tables:
        for row in table:
            if len(row) >= 6 and row[0] == "ER3":
                maturity = row[1]
                parsed_maturity = _parse_maturity_from_estr_pdf(maturity)
                closing_price = row[5]
                volume = int(row[8].replace(",", ""))
                first_accrual_date, last_accrual_date = calculate_estr_reference_dates(
                    parsed_maturity
                )

                if (
                    parsed_maturity
                    and closing_price
                    and volume > 1000
                    and last_accrual_date > date.today()
                ):
                    stir_futures_prices.append(
                        StirFutures(
                            central_bank=CentralBankChoices.ECB,
                            short_name=StirFuturesNameChoices.ESTR3M,
                            full_name=str(StirFuturesNameChoices.ESTR3M.label),
                            maturity=parsed_maturity,
                            first_accrual_date=first_accrual_date,
                            last_accrual_date=last_accrual_date,
                            date=price_date,
                            price=float(closing_price),
                            source=StirFuturesSourceChoices.PDF,
                            comment="Prices extracted from PDF file.",
                        )
                    )
    return stir_futures_prices


def extract_all_stir_futures_prices(price_date: date) -> List[StirFutures]:
    """Get all Stir Futures Prices."""
    stir_futures_prices = []
    for central_bank in CentralBankChoices:
        if central_bank not in STIR_FUTURES_PRICES_MAP:
            continue
        logger.info(f"Extracting Stir Futures Prices for {central_bank}")
        stir_futures_prices.extend(STIR_FUTURES_PRICES_MAP[central_bank](price_date))
    return stir_futures_prices


def ingest_stir_futures_prices(
    stir_futures_prices: List[StirFutures],
) -> List[StirFutures]:
    """Ingest Stir Futures Prices."""
    stir_futures_updated: List[StirFutures] = []
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
    price_date: date, central_banks: List[CentralBankChoices] = []
) -> List[StirFuturesModel]:
    """Get futures prices for a given date and central banks."""
    query = StirFuturesModel.objects.filter(date=price_date)
    if central_banks:
        query = query.filter(central_bank__in=central_banks)
    return list(query.order_by("central_bank", "maturity"))


def delete_stir_futures_prices(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    central_banks: Optional[List[CentralBankChoices]] = None,
) -> int:
    """Delete STIR futures prices based on optional filters."""
    futures_queryset = StirFuturesModel.objects.all()
    if start_date:
        futures_queryset = futures_queryset.filter(date__gte=start_date)
    if end_date:
        futures_queryset = futures_queryset.filter(date__lte=end_date)
    if central_banks:
        futures_queryset = futures_queryset.filter(central_bank__in=central_banks)
    deleted_count = futures_queryset.count()
    futures_queryset.delete()
    return deleted_count


def bulk_update_futures_prices(
    updates: List[BulkUpdateFuturesPricesItem],
) -> List[StirFuturesModel]:
    """Bulk update futures prices."""
    updated_futures = []
    for update in updates:
        future = core_services.get(
            StirFuturesModel,
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


EXPECTED_CSV_FORMAT = {
    "date": str,
    "short_name": str,
    "maturity": str,
    "price": float,
    "logs": str,
}


def bulk_update_futures_prices_from_csv(
    csv_file: bytes,
) -> List[StirFuturesModel]:
    """Bulk update futures prices from a CSV file."""
    df = pd.read_csv(BytesIO(csv_file), dtype=EXPECTED_CSV_FORMAT)  # type: ignore[reportArgumentType]
    df.fillna("", inplace=True)

    missing_columns = sorted(list(set(EXPECTED_CSV_FORMAT.keys()) - set(df.columns)))
    if missing_columns:
        raise ValueError(
            f"CSV file must have the following columns: {', '.join(missing_columns)}."
        )

    updates = [
        BulkUpdateFuturesPricesItem(
            date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
            short_name=row["short_name"],
            maturity=row["maturity"],
            price=row["price"],
            logs=(
                row["logs"]
                if row["logs"]
                else f"Bulk update from CSV file of {row['short_name']} to price: {row['price']}."
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
