"""Scrape S&P Global PMI levels from Trading Economics public charts."""

import base64
import json
import logging
import re
import zlib
from calendar import monthrange
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from typing import NamedTuple, TypedDict

import requests
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache
from django.utils import timezone
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    SP_GLOBAL_PMI_CALENDAR_LABEL_BY_TYPE,
    SP_GLOBAL_PMI_RELEASE_DATES_URL,
    SP_GLOBAL_PMI_TYPE_BY_TECHNICAL_NAME,
    SP_GLOBAL_PMI_UTC_CLOCK_BY_LOCATION_AND_TYPE,
    SP_GLOBAL_PMI_WEEKDAY_INDEX_BY_TYPE,
    TRADING_ECONOMICS_CHART_OBFUSCATION_KEY,
    TRADING_ECONOMICS_CHART_SPAN,
    TRADING_ECONOMICS_CHARTS_API_ORIGIN,
    TRADING_ECONOMICS_PMI_PATH_BY_TICKER,
    TRADING_ECONOMICS_SITE_ORIGIN,
    SpGlobalPmiType,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# TE and S&P Global block bare Python-requests clients with HTTP 403.
_BROWSER_REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# __________________________________________________________
# Values (S&P Global PMI)
# __________________________________________________________

_MONTH_NUMBER_BY_NAME: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# S&P Global calendar country label used in final PMI titles.
_SP_GLOBAL_COUNTRY_LABEL_BY_LOCATION: dict[str, str] = {
    "US": "US",
    "FR": "France",
    "JP": "Japan",
}


class _TradingEconomicsPageMeta(NamedTuple):
    """Chart auth fields embedded in a Trading Economics indicator page."""

    symbol: str
    api_key: str
    api_token: str
    api_path: str


class _TradingEconomicsSerie(TypedDict):
    """One TE chart series body after decrypt."""

    # Usage of list: TE wire points are [value, unix, optional, YYYY-MM-DD].
    data: list[list[float | int | str | None]]


class _TradingEconomicsSeriesWrap(TypedDict):
    """Wrapper around one TE chart serie."""

    serie: _TradingEconomicsSerie


class _TradingEconomicsChartPayloadItem(TypedDict):
    """Top-level TE charts-api economics payload item."""

    series: list[_TradingEconomicsSeriesWrap]


_CHART_PAYLOAD_ADAPTER = TypeAdapter(list[_TradingEconomicsChartPayloadItem])


def _parse_trading_economics_page_meta(
    page_html: str,
) -> _TradingEconomicsPageMeta | None:
    """Extract chart symbol and auth headers from a TE indicator HTML page."""
    symbol_match = re.search(r"var TESymbol = '([^']+)'", page_html)
    api_key_match = re.search(r"TEChartsKey = '([^']+)'", page_html)
    api_token_match = re.search(r"TEChartsToken = '([^']+)'", page_html)
    api_path_match = re.search(r"TEChartsPath = '([^']+)'", page_html)
    if (
        symbol_match is None
        or api_key_match is None
        or api_token_match is None
        or api_path_match is None
    ):
        return None
    return _TradingEconomicsPageMeta(
        symbol=symbol_match.group(1),
        api_key=api_key_match.group(1),
        api_token=api_token_match.group(1),
        api_path=api_path_match.group(1),
    )


def _decrypt_trading_economics_chart_payload(
    encrypted_payload: str,
) -> list[_TradingEconomicsChartPayloadItem]:
    """Base64-decode, XOR-deobfuscate, gunzip, and validate a TE charts payload."""
    payload_text = (
        json.loads(encrypted_payload)
        if encrypted_payload.startswith('"')
        else encrypted_payload.strip().strip('"')
    )
    if not isinstance(payload_text, str):
        raise ValueError("Trading Economics chart payload is not a string.")
    obfuscation_key = TRADING_ECONOMICS_CHART_OBFUSCATION_KEY.encode()
    encrypted_bytes = bytearray(base64.b64decode(payload_text))
    for byte_index in range(len(encrypted_bytes)):
        encrypted_bytes[byte_index] ^= obfuscation_key[
            byte_index % len(obfuscation_key)
        ]
    # TE charts-api wraps zlib as gzip (wbits=31).
    decrypted_text = zlib.decompress(bytes(encrypted_bytes), 31).decode()
    return _CHART_PAYLOAD_ADAPTER.validate_python(json.loads(decrypted_text))


def _parse_trading_economics_chart_points(
    chart_payload: list[_TradingEconomicsChartPayloadItem],
) -> list[ScrapingResult]:
    """Turn decrypted TE chart points into newest-first monthly levels."""
    if not chart_payload:
        return []
    # charts-api returns one payload item for a single-symbol request.
    payload_item = chart_payload[0]
    if not payload_item["series"]:
        return []
    # Single-symbol chart payload has one serie wrap.
    serie_data = payload_item["series"][0]["serie"]["data"]
    # Usage of dict: period keys are dynamic month-start observation dates.
    value_by_period: dict[date, float] = {}
    for chart_point in serie_data:
        if len(chart_point) < 4:
            continue
        data_value = chart_point[0]
        period_label = chart_point[3]
        if not isinstance(data_value, (int, float)) or isinstance(data_value, bool):
            continue
        if not isinstance(period_label, str):
            continue
        try:
            period = datetime.strptime(period_label, "%Y-%m-%d").date()
        except ValueError:
            continue
        value_by_period[period] = float(data_value)
    economic_data = [
        ScrapingResult(period=period, data_value=data_value, comment="")
        for period, data_value in value_by_period.items()
    ]
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _scrape_trading_economics_pmi_series(page_path: str) -> list[ScrapingResult]:
    """Fetch one TE PMI page, call charts-api, and parse monthly levels."""
    page_url = f"{TRADING_ECONOMICS_SITE_ORIGIN}{page_path}"
    page_response = requests.get(page_url, headers=_BROWSER_REQUEST_HEADERS, timeout=60)
    if page_response.status_code >= 400:
        logger.warning(
            f"Error scraping Trading Economics page {page_path}: "
            f"{page_response.status_code}"
        )
        return []
    page_meta = _parse_trading_economics_page_meta(page_response.text)
    if page_meta is None:
        logger.warning(f"Missing Trading Economics chart meta on {page_path}")
        return []

    chart_url = (
        f"{TRADING_ECONOMICS_CHARTS_API_ORIGIN}/economics/"
        f"{page_meta.symbol.lower()}?span={TRADING_ECONOMICS_CHART_SPAN}"
    )
    chart_response = requests.get(
        chart_url,
        headers={
            **_BROWSER_REQUEST_HEADERS,
            "Referer": page_url,
            "Origin": TRADING_ECONOMICS_SITE_ORIGIN,
            "x-api-key": page_meta.api_key,
            "x-api-token": page_meta.api_token,
            "x-api-path": page_meta.api_path,
        },
        timeout=60,
    )
    if chart_response.status_code >= 400:
        logger.warning(
            f"Error scraping Trading Economics chart for {page_meta.symbol}: "
            f"{chart_response.status_code}"
        )
        return []

    try:
        chart_payload = _decrypt_trading_economics_chart_payload(chart_response.text)
    except (ValidationError, ValueError, json.JSONDecodeError, zlib.error) as exc:
        logger.warning(
            f"Failed to decode Trading Economics chart for {page_meta.symbol}: {exc}"
        )
        return []
    return _parse_trading_economics_chart_points(chart_payload)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_trading_economics(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get an S&P Global PMI series from Trading Economics.

    Supported tickers map to TE page paths in
    'TRADING_ECONOMICS_PMI_PATH_BY_TICKER' (Composite / Manufacturing / Services
    for US, France, and Japan). Public charts expose roughly three years of
    monthly history.
    """
    page_path = TRADING_ECONOMICS_PMI_PATH_BY_TICKER.get(ticker)
    if page_path is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Trading Economics ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for Trading Economics scrape: "
                    f"{frequency}"
                ),
            )
        ]

    economic_data = _scrape_trading_economics_pmi_series(page_path)
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No Trading Economics values found for ticker {ticker}.",
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (S&P Global and Trading Economics calendars)
# __________________________________________________________


def _build_sp_global_pmi_title(location: str, pmi_type: SpGlobalPmiType) -> str | None:
    """Map location + PMI type to an S&P Global calendar title."""
    country_label = _SP_GLOBAL_COUNTRY_LABEL_BY_LOCATION.get(location)
    if country_label is None:
        return None
    type_label = SP_GLOBAL_PMI_CALENDAR_LABEL_BY_TYPE[pmi_type]
    return f"S&P Global {country_label} {type_label} PMI"


def _get_nth_weekday_of_month(year: int, month: int, weekday_index: int) -> date:
    """Return the Nth Monday–Friday date in a month (1-based weekday_index)."""
    day = date(year, month, 1)
    weekdays_seen = 0
    last_day = monthrange(year, month)[1]
    while day.day <= last_day:
        if day.weekday() < 5:
            weekdays_seen += 1
            if weekdays_seen == weekday_index:
                return day
        day += timedelta(days=1)
    raise ValueError(f"No weekday #{weekday_index} in {year}-{month:02d}")


def _list_sp_global_pmi_dates_from_weekday_rule(
    location: str,
    pmi_type: SpGlobalPmiType,
) -> list[datetime]:
    """Build upcoming finals from S&P's published weekday rule + UTC clocks.

    Manufacturing = 1st weekday, Services/Composite = 3rd weekday. Holiday
    shifts are not modelled when the live HTML calendar is unreachable.
    """
    utc_clock = SP_GLOBAL_PMI_UTC_CLOCK_BY_LOCATION_AND_TYPE.get((location, pmi_type))
    if utc_clock is None:
        return []
    hour, minute = utc_clock
    weekday_index = SP_GLOBAL_PMI_WEEKDAY_INDEX_BY_TYPE[pmi_type]
    today = timezone.now().date()
    publication_datetimes: list[datetime] = []
    year = today.year
    month = today.month
    for _ in range(4):
        release_day = _get_nth_weekday_of_month(year, month, weekday_index)
        publication_datetimes.append(
            datetime(
                release_day.year,
                release_day.month,
                release_day.day,
                hour,
                minute,
                tzinfo=datetime_timezone.utc,
            )
        )
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return filter_upcoming_publication_dates(publication_datetimes)


def _parse_sp_global_pmi_publication_datetime_from_element(
    element,
    *,
    # Usage of tuple: fixed (year, month, day) civil calendar day from the HTML.
    calendar_day: tuple[int, int, int] | None,
    target_title: str,
) -> datetime | None:
    """Return one UTC publication datetime when an element matches the PMI title."""
    label = " ".join(element.get_text().split())
    time_match = re.fullmatch(r"(\d{2}):(\d{2})\s*UTC", label)
    if time_match is None or calendar_day is None or element.parent is None:
        return None
    parent_label = " ".join(element.parent.get_text().split())
    event_title = re.sub(r"^\d{2}:\d{2}\s*UTC\s*", "", parent_label)
    if event_title != target_title:
        return None
    year, month, day = calendar_day
    # Calendar times are already UTC wall clocks on the S&P Global page.
    return datetime(
        year,
        month,
        day,
        int(time_match.group(1)),
        int(time_match.group(2)),
        tzinfo=datetime_timezone.utc,
    )


def _parse_sp_global_calendar_year_from_label(label: str) -> int | None:
    """Parse a four-digit calendar year heading from the S&P PMI HTML."""
    if re.fullmatch(r"20\d{2}", label):
        return int(label)
    return None


# Usage of tuple: fixed (year, month, day) civil calendar day from the HTML.
def _parse_sp_global_calendar_day_from_label(
    label: str,
    calendar_year: int,
) -> tuple[int, int, int] | None:
    """Parse a month-day heading into a year-month-day tuple."""
    day_match = re.fullmatch(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2})",
        label,
    )
    if day_match is None:
        return None
    return (
        calendar_year,
        _MONTH_NUMBER_BY_NAME[day_match.group(1).lower()],
        int(day_match.group(2)),
    )


def _list_sp_global_pmi_dates_from_html_calendar(target_title: str) -> list[datetime]:
    """Parse final PMI slots from the S&P Global public release-dates page."""
    response = requests.get(
        SP_GLOBAL_PMI_RELEASE_DATES_URL,
        headers=_BROWSER_REQUEST_HEADERS,
        timeout=60,
    )
    if response.status_code >= 400 or "S&P Global" not in response.text:
        logger.warning(
            "S&P Global PMI calendar HTML unavailable "
            f"(status={response.status_code}, len={len(response.text)})."
        )
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    calendar_year: int | None = None
    # Usage of tuple: fixed (year, month, day) civil calendar day from the HTML.
    calendar_day: tuple[int, int, int] | None = None
    publication_datetimes: list[datetime] = []
    for element in soup.find_all(["div", "span", "h2", "h3"]):
        label = " ".join(element.get_text().split())
        parsed_year = _parse_sp_global_calendar_year_from_label(label)
        if parsed_year is not None:
            calendar_year = parsed_year
            continue
        if calendar_year is not None:
            parsed_day = _parse_sp_global_calendar_day_from_label(label, calendar_year)
            if parsed_day is not None:
                calendar_day = parsed_day
                continue
        parsed_datetime = _parse_sp_global_pmi_publication_datetime_from_element(
            element,
            calendar_day=calendar_day,
            target_title=target_title,
        )
        if parsed_datetime is not None:
            publication_datetimes.append(parsed_datetime)
    publication_datetimes.sort()
    return filter_upcoming_publication_dates(publication_datetimes)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_trading_economics(
    name: str,
    location: str = "",
) -> list[datetime]:
    """Get S&P Global final PMI dates from the public UTC release calendar.

    Trading Economics chart pages have no embargo clock; S&P Global publishes
    final Manufacturing / Services (and Composite-with-Services) times in UTC.
    When the HTML calendar is blocked, fall back to S&P's published weekday
    rule with the same UTC clocks.
    """
    pmi_type = SP_GLOBAL_PMI_TYPE_BY_TECHNICAL_NAME.get(name)
    if pmi_type is None:
        logger.warning(
            "No S&P Global PMI type for " f"technical_name={name} location={location}."
        )
        return []
    target_title = _build_sp_global_pmi_title(location, pmi_type)
    if target_title is None:
        logger.warning(
            "No S&P Global PMI calendar title for "
            f"technical_name={name} location={location}."
        )
        return []

    publication_datetimes = _list_sp_global_pmi_dates_from_html_calendar(target_title)
    if publication_datetimes:
        return publication_datetimes
    return _list_sp_global_pmi_dates_from_weekday_rule(location, pmi_type)
