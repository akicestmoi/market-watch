"""Scrape JGB yields from BB (Japan Bond Trading)."""

from datetime import date

import pandas as pd
from bs4 import Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import fetch_html
from market_overview.services.scrapers.common import (
    ScrapingResult,
    YieldCurveScrapResult,
    YieldTermRate,
    get_yield_curve_rate,
)
from market_overview.services.config import BB_YIELD_CURVE_URL


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
        # Must have a date (YYYY/MM/DD)
        if cols and len(cols[0].split("/")) == 3:
            rows.append(cols)

    # Define maturities (according to header order)
    maturities = [
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

    df = pd.DataFrame(rows, columns=["Date"] + maturities)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y/%m/%d")

    for col in maturities:
        df[col] = pd.to_numeric(df[col].replace("", None), errors="coerce")

    df_cleaned = df.sort_values("Date").ffill()
    target_yield_curves_df = df_cleaned[df_cleaned["Date"].dt.date == target_date]
    if target_yield_curves_df.empty or target_yield_curves_df.shape[0] > 1:
        return YieldCurveScrapResult(rates=[], error="Yield curve not found.")
    row = target_yield_curves_df.iloc[0]
    rates: list[YieldTermRate] = []
    for maturity in maturities:
        value = row[maturity]
        if pd.isna(value):
            continue
        rates.append(YieldTermRate(term=maturity, rate=float(value)))
    return YieldCurveScrapResult(rates=rates, error=None)


def get_jgb_yield_from_bb(target_date: date, ticker: str) -> ScrapingResult:
    """Infer JGB yield from BB yield curve."""
    mapping = {
        "TDB3M": "TDB(3M)",
        "TDB6M": "TDB(6M)",
        "TDB1Y": "TDB(1Y)",
        "JGB2Y": "2Y",
        "JGB5Y": "5Y",
        "JGB10Y": "10Y",
        "JGB20Y": "20Y",
    }
    if ticker not in mapping.keys():
        return ScrapingResult(price=None, comment="Ticker not found in mapping.")
    curve = _scrap_jgb_yield_curve_from_bb(target_date)
    if curve["error"]:
        return ScrapingResult(price=None, comment=curve["error"])
    if not curve["rates"]:
        return ScrapingResult(price=None, comment="Yield curve not found.")
    return ScrapingResult(
        price=get_yield_curve_rate(curve, mapping[ticker]), comment=""
    )
