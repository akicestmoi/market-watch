"""Scrape JGB yields from BB (Japan Bond Trading)."""

from datetime import date

import pandas as pd
from bs4 import Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import fetch_html
from market_overview.services.config import BB_YIELD_CURVE_URL
from market_overview.services.scrapers.common import (
    ScrapingResult,
    YieldCurveScrapResult,
    YieldTermRate,
    get_yield_from_curve_by_ticker,
)

# Usage of dict: keys are JGB/TDB tickers; values are BB table maturity labels.
_JGB_TICKER_TO_TERM: dict[str, str] = {
    "TDB3M": "TDB(3M)",
    "TDB6M": "TDB(6M)",
    "TDB1Y": "TDB(1Y)",
    "JGB2Y": "2Y",
    "JGB5Y": "5Y",
    "JGB10Y": "10Y",
    "JGB20Y": "20Y",
}

# BB table maturity columns in header order (after the Date column).
_BB_YIELD_CURVE_MATURITIES: list[str] = [
    "40Y",
    "30Y",
    "20Y",
    "10Y",
    "5Y",
    "2Y",
    "TDB(1Y)",
    "TDB(6M)",
    "TDB(3M)",
]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _scrap_jgb_yield_curve_from_bb(target_date: date) -> YieldCurveScrapResult:
    """Scrap entire UST yield curves from Treasury department.

    Source: https://www.bb.jbts.co.jp/en/index.html
    """
    soup = fetch_html(BB_YIELD_CURVE_URL)
    if not soup:
        return YieldCurveScrapResult(
            rates=[], error=f"Failed to fetch HTML from {BB_YIELD_CURVE_URL}"
        )

    rows = []
    for tr in soup.select("table.tbCore tr"):
        if not isinstance(tr, Tag):
            continue
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        # Column 0 is the Date cell; require YYYY/MM/DD before treating the row as data.
        if cols and len(cols[0].split("/")) == 3:
            rows.append(cols)

    df = pd.DataFrame(rows, columns=["Date"] + _BB_YIELD_CURVE_MATURITIES)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y/%m/%d")

    for maturity in _BB_YIELD_CURVE_MATURITIES:
        df[maturity] = pd.to_numeric(df[maturity].replace("", None), errors="coerce")

    df_cleaned = df.sort_values("Date").ffill()
    target_yield_curves_df = df_cleaned[df_cleaned["Date"].dt.date == target_date]
    if target_yield_curves_df.empty or target_yield_curves_df.shape[0] > 1:
        return YieldCurveScrapResult(rates=[], error="Yield curve not found.")
    # Exactly one matching calendar day remains; index 0 is that day's curve row.
    row = target_yield_curves_df.iloc[0]
    rates: list[YieldTermRate] = []
    for maturity in _BB_YIELD_CURVE_MATURITIES:
        value = row[maturity]
        if pd.isna(value):
            continue
        rates.append(YieldTermRate(term=maturity, rate=float(value)))
    return YieldCurveScrapResult(rates=rates, error=None)


def get_jgb_yield_from_bb(target_date: date, ticker: str) -> ScrapingResult:
    """Infer JGB yield from BB yield curve."""
    return get_yield_from_curve_by_ticker(
        ticker,
        _JGB_TICKER_TO_TERM,
        _scrap_jgb_yield_curve_from_bb(target_date),
    )
