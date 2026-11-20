"""Scrape closing prices, day returns, and earnings details from Yahoo Finance."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import NamedTuple, TypedDict

import pandas as pd
import yfinance as yf
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
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


def _list_daily_returns_by_date_from_close_series(
    closes_by_date: pd.Series,
    start_date: date,
    end_date: date,
) -> dict[date, float]:
    """Return percent day moves keyed by trading date within the window."""
    # Usage of dict: keys are trading dates; values are percent day returns.
    ordered_closes = closes_by_date.sort_index().dropna()
    if ordered_closes.empty:
        return {}
    percent_changes = ordered_closes.pct_change() * 100.0
    daily_returns: dict[date, float] = {}
    for timestamp, percent_change in percent_changes.items():
        if pd.isna(percent_change) or not isinstance(timestamp, pd.Timestamp):
            continue
        trading_date = timestamp.date()
        if start_date <= trading_date <= end_date:
            daily_returns[trading_date] = float(percent_change)
    return daily_returns


def _get_close_series_for_ticker(
    downloaded: pd.DataFrame,
    ticker: str,
    ticker_count: int,
) -> pd.Series | None:
    """Return one ticker's Close series from a Yahoo batch download."""
    try:
        if ticker_count == 1:
            return downloaded["Close"].dropna()
        return downloaded[ticker]["Close"].dropna()
    except (KeyError, TypeError):
        return None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _list_yahoo_daily_returns_by_date_for_batch(
    tickers: tuple[str, ...],
    start_date: date,
    end_date: date,
) -> dict[date, dict[str, float]]:
    """Download one Yahoo batch and return percent day moves by date then ticker."""
    # Usage of dict: keys are trading dates; values are ticker->percent day return maps.
    # Usage of tuple: tickers must be hashable for '@ttl_cache'.
    download_start = start_date - timedelta(days=10)
    download_end = end_date + timedelta(days=1)
    downloaded = yf.download(
        tickers=list(tickers),
        start=download_start.isoformat(),
        end=download_end.isoformat(),
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    returns_by_date: dict[date, dict[str, float]] = defaultdict(dict)
    if not isinstance(downloaded, pd.DataFrame) or downloaded.empty:
        return {}
    for ticker in tickers:
        closes_by_date = _get_close_series_for_ticker(downloaded, ticker, len(tickers))
        if closes_by_date is None:
            continue
        for trading_date, daily_return in _list_daily_returns_by_date_from_close_series(
            closes_by_date,
            start_date,
            end_date,
        ).items():
            returns_by_date[trading_date][ticker] = daily_return
    return dict(returns_by_date)


# Yahoo download calls stay reliable when tickers are fetched in batches of this size.
_YAHOO_DAILY_RETURN_BATCH_SIZE = 80


def get_yahoo_finance_daily_returns_for_date_range(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> dict[date, dict[str, float]]:
    """
    Return percent day moves for 'tickers' for each trading day in the window.

    Missing tickers are omitted on each day; callers decide whether that is OK.
    """
    if end_date < start_date:
        raise ValueError(
            "end_date must be greater than or equal to start_date "
            f"(got {start_date.isoformat()} .. {end_date.isoformat()})."
        )
    # Usage of dict: keys are trading dates; values are ticker->percent day return maps.
    returns_by_date: dict[date, dict[str, float]] = {}
    for start_index in range(0, len(tickers), _YAHOO_DAILY_RETURN_BATCH_SIZE):
        batch = tickers[start_index : start_index + _YAHOO_DAILY_RETURN_BATCH_SIZE]
        batch_returns = _list_yahoo_daily_returns_by_date_for_batch(
            tuple(batch),
            start_date,
            end_date,
        )
        for trading_date, returns_by_ticker in batch_returns.items():
            returns_by_date.setdefault(trading_date, {}).update(returns_by_ticker)
    return returns_by_date


class YahooEarningsInformation(NamedTuple):
    """One earnings release scraped from Yahoo Finance."""

    announcement_datetime: datetime | None
    reporting_period_end: date | None
    is_reported: bool
    eps_actual: float | None
    eps_expected: float | None
    revenue_expected: float | None
    revenue: float | None
    operating_income: float | None
    gross_profit: float | None
    ebitda: float | None


class YahooEarningsSnapshot(NamedTuple):
    """Upcoming schedule plus the latest and previous reported results for one ticker."""

    upcoming: YahooEarningsInformation | None
    current: YahooEarningsInformation | None
    previous: YahooEarningsInformation | None


_INCOME_STMT_REVENUE_LABEL = "Total Revenue"
_INCOME_STMT_OPERATING_INCOME_LABEL = "Operating Income"
_INCOME_STMT_GROSS_PROFIT_LABEL = "Gross Profit"
_INCOME_STMT_EBITDA_LABEL = "EBITDA"

# Earnings calls usually land within about two months after the fiscal period end.
_MAX_DAYS_AFTER_PERIOD_END_FOR_CALL = 75

_YahooScrapedScalar = str | int | float | datetime | date | pd.Timestamp | None


def _to_optional_float(value: _YahooScrapedScalar) -> float | None:
    """Convert a scraped scalar to float, or None when it is missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool) or isinstance(value, pd.Timestamp):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _to_utc_datetime(value: _YahooScrapedScalar) -> datetime | None:
    """Normalize a Yahoo date or datetime to an aware UTC datetime."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time(21, 0), tzinfo=timezone.utc)
    return None


def _to_optional_date(value: _YahooScrapedScalar) -> date | None:
    """Convert a scraped period label to a calendar date."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


class _IncomeStatementMetrics(NamedTuple):
    """Revenue, operating income, gross profit, and EBITDA for one fiscal period."""

    revenue: float | None
    operating_income: float | None
    gross_profit: float | None
    ebitda: float | None


def _get_income_statement_line(
    quarterly_income_stmt: pd.DataFrame,
    label: str,
    period_column: datetime | date | str,
) -> float | None:
    """Return one income-statement line for a fiscal period column."""
    if label not in quarterly_income_stmt.index:
        return None
    income_statement_line = quarterly_income_stmt.loc[label]
    if not isinstance(income_statement_line, pd.Series):
        return None
    return _to_optional_float(income_statement_line.get(period_column))


def _get_income_stmt_metrics_for_period(
    quarterly_income_stmt: pd.DataFrame,
    reporting_period_end: date | None,
) -> _IncomeStatementMetrics:
    """Return revenue, operating income, gross profit, and EBITDA for one period."""
    empty_metrics = _IncomeStatementMetrics(
        revenue=None,
        operating_income=None,
        gross_profit=None,
        ebitda=None,
    )
    if quarterly_income_stmt.empty or reporting_period_end is None:
        return empty_metrics
    matching_columns: list[datetime | date | str] = []
    for column in quarterly_income_stmt.columns:
        if isinstance(column, (datetime, date, str)) and (
            _to_optional_date(column) == reporting_period_end
        ):
            matching_columns.append(column)
    if not matching_columns:
        return empty_metrics
    # Yahoo returns one column per fiscal period end, so the first match is that period.
    period_column = matching_columns[0]
    return _IncomeStatementMetrics(
        revenue=_get_income_statement_line(
            quarterly_income_stmt, _INCOME_STMT_REVENUE_LABEL, period_column
        ),
        operating_income=_get_income_statement_line(
            quarterly_income_stmt,
            _INCOME_STMT_OPERATING_INCOME_LABEL,
            period_column,
        ),
        gross_profit=_get_income_statement_line(
            quarterly_income_stmt, _INCOME_STMT_GROSS_PROFIT_LABEL, period_column
        ),
        ebitda=_get_income_statement_line(
            quarterly_income_stmt, _INCOME_STMT_EBITDA_LABEL, period_column
        ),
    )


def _get_reported_information_from_history_row(
    history_row: pd.Series,
    period_end: date,
    quarterly_income_stmt: pd.DataFrame,
    announcement_datetime: datetime | None,
) -> YahooEarningsInformation:
    """Build one reported earnings release from one Yahoo earnings-history entry."""
    income_statement_metrics = _get_income_stmt_metrics_for_period(
        quarterly_income_stmt, period_end
    )
    return YahooEarningsInformation(
        # Do not fake the call date with period end — that makes Prev. Call look
        # monthly vs the next scheduled call.
        announcement_datetime=announcement_datetime,
        reporting_period_end=period_end,
        is_reported=True,
        eps_actual=_to_optional_float(history_row.get("epsActual")),
        eps_expected=_to_optional_float(history_row.get("epsEstimate")),
        revenue_expected=None,
        revenue=income_statement_metrics.revenue,
        operating_income=income_statement_metrics.operating_income,
        gross_profit=income_statement_metrics.gross_profit,
        ebitda=income_statement_metrics.ebitda,
    )


def _get_announcement_datetime_for_period_end(
    period_end: date,
    earnings_dates: pd.DataFrame,
) -> datetime | None:
    """Map a fiscal period end to its earnings-call datetime from Yahoo dates."""
    if earnings_dates.empty:
        return None
    # Prefer an explicit Period End column when yfinance still exposes it.
    for announcement_label, earnings_date_row in earnings_dates.iterrows():
        if not isinstance(announcement_label, (datetime, date, str)):
            continue
        if _to_optional_date(earnings_date_row.get("Period End")) != period_end:
            continue
        announcement_datetime = _to_utc_datetime(announcement_label)
        if announcement_datetime is not None:
            return announcement_datetime
    # Current yfinance earnings_dates often omit Period End. Match the earliest
    # reported call after the period end (within a normal quarterly lag).
    period_end_utc = datetime.combine(period_end, time(0, 0), tzinfo=timezone.utc)
    deadline_utc = period_end_utc + timedelta(days=_MAX_DAYS_AFTER_PERIOD_END_FOR_CALL)
    matched_announcement: datetime | None = None
    for announcement_label, earnings_date_row in earnings_dates.iterrows():
        if not isinstance(announcement_label, (datetime, date, str)):
            continue
        announcement_datetime = _to_utc_datetime(announcement_label)
        if announcement_datetime is None:
            continue
        if (
            announcement_datetime <= period_end_utc
            or announcement_datetime > deadline_utc
        ):
            continue
        if _to_optional_float(earnings_date_row.get("Reported EPS")) is None:
            continue
        if matched_announcement is None or announcement_datetime < matched_announcement:
            matched_announcement = announcement_datetime
    return matched_announcement


def _list_reported_information_from_earnings_history(
    earnings_history: pd.DataFrame,
    quarterly_income_stmt: pd.DataFrame,
    earnings_dates: pd.DataFrame,
) -> list[YahooEarningsInformation]:
    """Return reported earnings releases oldest-first from Yahoo earnings history."""
    if earnings_history.empty:
        return []
    reported_information_list: list[YahooEarningsInformation] = []
    for period_label, history_row in earnings_history.iterrows():
        if not isinstance(period_label, (datetime, date, str)):
            continue
        period_end = _to_optional_date(period_label)
        if period_end is None:
            continue
        reported_information_list.append(
            _get_reported_information_from_history_row(
                history_row,
                period_end,
                quarterly_income_stmt,
                _get_announcement_datetime_for_period_end(period_end, earnings_dates),
            )
        )
    return reported_information_list


_YahooCalendarScalar = str | int | float | datetime | date | None

_YahooEarningsCalendar = TypedDict(
    "_YahooEarningsCalendar",
    {
        "Earnings Date": list[_YahooCalendarScalar] | _YahooCalendarScalar,
        "Earnings Average": _YahooCalendarScalar,
        "Revenue Average": _YahooCalendarScalar,
    },
    total=False,
)
_YahooEarningsCalendar.__doc__ = (
    "Yahoo ticker calendar fields for the next scheduled earnings release."
)

_YAHOO_EARNINGS_CALENDAR_ADAPTER: TypeAdapter[_YahooEarningsCalendar] = TypeAdapter(
    _YahooEarningsCalendar
)


def _get_yahoo_earnings_calendar(
    calendar: dict[str, _YahooCalendarScalar | list[_YahooCalendarScalar]],
) -> _YahooEarningsCalendar | None:
    """Validate Yahoo ticker calendar fields, or return None when unusable."""
    try:
        return _YAHOO_EARNINGS_CALENDAR_ADAPTER.validate_python(calendar)
    except ValidationError:
        return None


def _get_announcement_date_from_calendar(
    calendar: _YahooEarningsCalendar,
) -> date | None:
    """Return the earliest upcoming earnings date from a Yahoo ticker calendar."""
    earnings_dates = calendar.get("Earnings Date")
    if isinstance(earnings_dates, list):
        if not earnings_dates:
            return None
        # Yahoo lists one date or a short window, so the first date is the earliest.
        return _to_optional_date(earnings_dates[0])
    return _to_optional_date(earnings_dates)


def _get_next_scheduled_information_from_calendar(
    calendar: _YahooEarningsCalendar,
    eps_expected_fallback: float | None,
) -> YahooEarningsInformation | None:
    """Build the next scheduled earnings release from Yahoo's ticker calendar."""
    announcement_date = _get_announcement_date_from_calendar(calendar)
    if announcement_date is None:
        return None
    eps_expected = _to_optional_float(calendar.get("Earnings Average"))
    if eps_expected is None:
        eps_expected = eps_expected_fallback
    return YahooEarningsInformation(
        announcement_datetime=datetime.combine(
            announcement_date, time(21, 0), tzinfo=timezone.utc
        ),
        reporting_period_end=None,
        is_reported=False,
        eps_actual=None,
        eps_expected=eps_expected,
        revenue_expected=_to_optional_float(calendar.get("Revenue Average")),
        revenue=None,
        operating_income=None,
        gross_profit=None,
        ebitda=None,
    )


def _get_earnings_dates_frame(ticker_client: yf.Ticker) -> pd.DataFrame:
    """Return Yahoo earnings-call dates, or an empty frame when unavailable."""
    try:
        earnings_dates = ticker_client.get_earnings_dates(limit=24)
    except Exception:
        return pd.DataFrame()
    if earnings_dates is None or earnings_dates.empty:
        return pd.DataFrame()
    return earnings_dates


def _get_current_quarter_eps_estimate(earnings_estimate: pd.DataFrame) -> float | None:
    """Return the consensus EPS for the current quarter when present."""
    if earnings_estimate.empty or "0q" not in earnings_estimate.index:
        return None
    current_quarter_estimate = earnings_estimate.loc["0q"]
    if not isinstance(current_quarter_estimate, pd.Series):
        return None
    return _to_optional_float(current_quarter_estimate.get("avg"))


def _get_scheduled_information_from_ticker(
    ticker_client: yf.Ticker,
    eps_expected_fallback: float | None,
) -> YahooEarningsInformation | None:
    """Read the next scheduled earnings release from one Yahoo ticker client."""
    raw_calendar = ticker_client.calendar
    if not isinstance(raw_calendar, dict):
        return None
    calendar = _get_yahoo_earnings_calendar(raw_calendar)
    if calendar is None:
        return None
    return _get_next_scheduled_information_from_calendar(
        calendar, eps_expected_fallback
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_yahoo_finance_earnings_snapshot(ticker: str) -> YahooEarningsSnapshot:
    """Scrape the upcoming schedule plus the latest and previous reported results."""
    ticker_client = yf.Ticker(str(ticker))
    earnings_history = ticker_client.earnings_history
    if earnings_history is None:
        earnings_history = pd.DataFrame()
    quarterly_income_stmt = ticker_client.quarterly_income_stmt
    if quarterly_income_stmt is None:
        quarterly_income_stmt = pd.DataFrame()
    earnings_estimate = ticker_client.earnings_estimate
    if earnings_estimate is None:
        earnings_estimate = pd.DataFrame()

    reported_information_list = _list_reported_information_from_earnings_history(
        earnings_history,
        quarterly_income_stmt,
        _get_earnings_dates_frame(ticker_client),
    )
    scheduled_information = _get_scheduled_information_from_ticker(
        ticker_client,
        _get_current_quarter_eps_estimate(earnings_estimate),
    )

    # Earnings history is oldest-first, so the last entry is the latest reported release.
    latest_reported = (
        reported_information_list[-1] if reported_information_list else None
    )
    # Earnings history is oldest-first, so the entry before last is the previous release.
    prior_reported = (
        reported_information_list[-2] if len(reported_information_list) >= 2 else None
    )

    upcoming = None
    if scheduled_information is not None and (
        latest_reported is None
        or (
            scheduled_information.announcement_datetime is not None
            and latest_reported.announcement_datetime is not None
            and scheduled_information.announcement_datetime
            > latest_reported.announcement_datetime
        )
        or (
            scheduled_information.announcement_datetime is not None
            and latest_reported.announcement_datetime is None
        )
    ):
        upcoming = scheduled_information
    return YahooEarningsSnapshot(
        upcoming=upcoming,
        current=latest_reported,
        previous=prior_reported,
    )
