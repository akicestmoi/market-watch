"""Scrape closing prices from Yahoo Finance."""

from datetime import date

import yfinance as yf
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_overview.services.scrapers.common import ScrapingResult


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_yahoo_finance_closing_prices(target_date: date, ticker: str) -> ScrapingResult:
    """Get closing prices from Yahoo Finance.

    Using publicly available yahoo scraper module yfiance.
    """
    prices = yf.Ticker(str(ticker)).history(period="1mo").reset_index()
    if prices.empty:
        return ScrapingResult(price=None, comment="Yahoo Finance: No prices found.")
    closing_price = prices[prices["Date"].dt.date == target_date].reset_index()
    if not closing_price.empty:
        return ScrapingResult(
            price=float(str(closing_price.loc[0, "Close"])), comment=""
        )
    return ScrapingResult(price=None, comment="Yahoo Finance: No prices found.")
