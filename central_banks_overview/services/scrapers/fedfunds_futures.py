"""Fetch Fed Funds futures prices from Yahoo Finance (CME / CBOT contracts)."""

from datetime import date, datetime, timezone
from typing import TypedDict

from cachetools.func import ttl_cache
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthBegin, MonthEnd

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.central_banks_meetings import (
    get_central_bank_next_meeting_date,
)
from central_banks_overview.services.config import (
    CME_MONTH_CODE_BY_MONTH,
    FED_FUNDS_FUTURES_MONTHS,
    FF_FUTURES_PREFIX,
    FF_FUTURES_SUFFIX,
)
from central_banks_overview.services.scrapers.common import StirFutures
from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from market_overview.services.scrapers.yahoo import get_yahoo_finance_closing_prices


class _YFinanceTickerInfo(TypedDict):
    """YFinance Ticker Information."""

    ticker: str
    date: datetime


def _get_ticker_info_from_maturity_month(maturity_month: int) -> _YFinanceTickerInfo:
    """Get the YFinance ticker and date from a maturity month."""
    next_meeting_date = get_central_bank_next_meeting_date(CentralBankChoices.FRB)
    now = datetime.now(timezone.utc)
    month_offset = maturity_month + (
        1 if (next_meeting_date and next_meeting_date < now) else 0
    )
    ticker_date = now + relativedelta(months=month_offset)
    ticker_month = CME_MONTH_CODE_BY_MONTH[ticker_date.month]
    ticker_year = ticker_date.strftime("%y")
    yfinance_ticker = (
        f"{FF_FUTURES_PREFIX}{ticker_month}{ticker_year}{FF_FUTURES_SUFFIX}"
    )
    return _YFinanceTickerInfo(ticker=yfinance_ticker, date=ticker_date)


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


def get_fedfunds_futures_prices(target_date: date) -> list[StirFutures]:
    """Get the prices of the Fed Funds Futures contracts for a given date."""
    return [
        _get_fedfunds_futures_price(target_date, maturity_month)
        for maturity_month in range(0, FED_FUNDS_FUTURES_MONTHS)
    ]
