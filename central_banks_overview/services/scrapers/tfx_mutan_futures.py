"""Scrape Mutan (TONA 3M) STIR futures prices and accrual dates from TFX."""

import re
from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag
from cachetools.func import ttl_cache

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.config import (
    TFX_HISTORICAL_FUTURES_DATA_URL,
    TFX_HISTORICAL_FUTURES_TRADING_CALENDAR_URL,
    TFX_HISTORICAL_LOOKBACK_DAYS,
)
from central_banks_overview.services.scrapers.common import StirFutures
from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_mutan_futures_prices_from_tfx(target_date: date) -> pd.DataFrame:
    """Get prices of Mutan STIR Futures from TFX.

    Source: https://www.tfx.co.jp/
    """
    period_start = target_date - timedelta(days=TFX_HISTORICAL_LOOKBACK_DAYS)

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


def _parse_jp_date(date_str: str) -> date | None:
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
        tds = [td for td in tr.find_all("td") if isinstance(td, Tag)]
        ths = [th for th in tr.find_all("th") if isinstance(th, Tag)]

        if not tds:
            continue

        if ths and "rowspan" in ths[0].attrs:
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


def get_mutan_futures_prices(target_date: date) -> list[StirFutures]:
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
