"""Scrape Statistics Bureau / e-Stat series, getStatsData API, and release calendar."""

import io
import logging
import re
import zipfile
from datetime import date, datetime, timedelta
from typing import TypedDict

import openpyxl
import requests
import xlrd
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache
from django.conf import settings
from django.utils import timezone
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    ESTAT_API_BASE_URL,
    ESTAT_RELEASE_CALENDAR_LOOKAHEAD_MONTHS,
    ESTAT_RELEASE_CALENDAR_URL,
    ESTAT_SCHEDULE_MATCH_BY_TECHNICAL_NAME,
    FIES_GINI_TICKER,
    FIES_PALMA_TICKER,
    FIES_TABLE3_FIRST_YEAR,
    FIES_TABLE3_XLS_URL_TEMPLATE,
    FIES_TABLE3_XLSX_URL_TEMPLATE,
    STAT_OF_JP_DATA_URL,
    STAT_OF_JP_DEFAULT_PARAMS,
    STAT_OF_JP_SERIES_BY_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    calculate_equal_group_gini,
    calculate_palma_from_decile_means,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# FIES equal-decile Gini is computed on 0–1; Front stores 0–100 like Eurostat.
_FIES_GINI_TO_FRONT_SCALE = 100.0
_FIES_TOTAL_HOUSEHOLDS_SHEET_NAME = "総"
_FIES_YEARLY_INCOME_LABEL = "年間収入(万円)"
# Decile means sit after Average + five quintile columns (0-based xlrd index 22).
_FIES_FIRST_DECILE_COLUMN_INDEX = 22
_FIES_DECILE_COUNT = 10

# __________________________________________________________
# Values (e-Stat getStatsData API)
# __________________________________________________________

# Usage of dict: e-Stat JSON objects use dynamic '@…' / '$' keys; nested values recurse.
type EstatJsonValue = (
    str
    | int
    | float
    | bool
    | None
    | list["EstatJsonValue"]
    | dict[str, "EstatJsonValue"]
)
# Usage of dict: one e-Stat JSON object after isinstance(dict) narrowing.
type EstatJsonObject = dict[str, EstatJsonValue]


class EstatStatsDataPayload(TypedDict):
    """Validated subset of one getStatsData response used by scrapers."""

    # Usage of dict: e-Stat time '@code' → CLASS '@name' label.
    time_labels_by_code: dict[str, str]
    values: list[EstatJsonObject]
    # CLASS_OBJ node (one object or a list) for callers that need non-time dims.
    class_objs: EstatJsonValue


def list_estat_dict_entries(raw_value: EstatJsonValue) -> list[EstatJsonObject]:
    """Normalize an e-Stat node that may be one object or a list of objects."""
    if isinstance(raw_value, dict):
        return [raw_value]
    if isinstance(raw_value, list):
        return [entry for entry in raw_value if isinstance(entry, dict)]
    return []


def _build_estat_time_labels_by_code(class_objs: EstatJsonValue) -> dict[str, str]:
    """Map time-axis codes → CLASS labels from CLASS_INF."""
    # Usage of dict: e-Stat time '@code' → CLASS '@name' label.
    labels_by_code: dict[str, str] = {}
    for class_obj in list_estat_dict_entries(class_objs):
        if class_obj.get("@id") != "time":
            continue
        for class_entry in list_estat_dict_entries(class_obj.get("CLASS")):
            time_code = str(class_entry.get("@code") or "").strip()
            time_label = str(class_entry.get("@name") or "").strip()
            if time_code and time_label:
                labels_by_code[time_code] = time_label
    return labels_by_code


def parse_estat_month_time_code(time_code: str) -> date | None:
    """Parse codes such as '2026000808' into month-start dates."""
    if len(time_code) != 10 or not time_code.isdigit():
        return None
    year = int(time_code[:4])
    month = int(time_code[6:8])
    if time_code[4:6] != "00" or time_code[8:10] != time_code[6:8]:
        return None
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


# Usage of tuple: CLASS_OBJ value metadata and VALUE rows from getStatsData JSON.
def _read_estat_statistical_data_values(
    payload: EstatJsonObject,
    log_label: str,
) -> tuple[EstatJsonValue, list[EstatJsonObject]] | None:
    """Return CLASS_OBJ and VALUE rows from a validated getStatsData JSON object."""
    stats_root = payload.get("GET_STATS_DATA")
    if not isinstance(stats_root, dict):
        logger.warning("e-Stat %s response missing GET_STATS_DATA.", log_label)
        return None
    result = stats_root.get("RESULT")
    if not isinstance(result, dict) or result.get("STATUS") not in (0, "0"):
        error_message = (
            result.get("ERROR_MSG") if isinstance(result, dict) else "unknown error"
        )
        logger.warning("e-Stat %s API error: %s", log_label, error_message)
        return None
    statistical_data = stats_root.get("STATISTICAL_DATA")
    if not isinstance(statistical_data, dict):
        logger.warning("e-Stat %s response missing STATISTICAL_DATA.", log_label)
        return None
    class_inf = statistical_data.get("CLASS_INF")
    data_inf = statistical_data.get("DATA_INF")
    class_objs = class_inf.get("CLASS_OBJ") if isinstance(class_inf, dict) else None
    raw_values = data_inf.get("VALUE") if isinstance(data_inf, dict) else None
    return (
        class_objs if class_objs is not None else [],
        list_estat_dict_entries(raw_values),
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _fetch_estat_stats_data_cached(
    stats_data_id: str,
    # Usage of tuple: sorted query pairs so @ttl_cache keys stay hashable.
    query_params_items: tuple[tuple[str, str], ...],
    log_label: str,
) -> EstatStatsDataPayload | None:
    """GET one e-Stat getStatsData table; return values plus time labels."""
    app_id = (getattr(settings, "ESTAT_APP_ID", None) or "").strip()
    if not app_id:
        logger.warning("ESTAT_APP_ID is empty; skipping %s scrape.", log_label)
        return None
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    request_params: dict[str, str] = {
        "appId": app_id,
        "statsDataId": stats_data_id,
        "lang": "J",
        "metaGetFlg": "Y",
        "cntGetFlg": "N",
        "sectionHeaderFlg": "1",
    }
    request_params.update(query_params_items)
    try:
        response = requests.get(
            f"{ESTAT_API_BASE_URL}/getStatsData",
            params=request_params,
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("e-Stat %s fetch failed: %s", log_label, exc)
        return None

    if not isinstance(payload, dict):
        logger.warning("e-Stat %s response was not a JSON object.", log_label)
        return None
    statistical_blocks = _read_estat_statistical_data_values(payload, log_label)
    if statistical_blocks is None:
        return None
    class_objs, values = statistical_blocks
    return EstatStatsDataPayload(
        time_labels_by_code=_build_estat_time_labels_by_code(class_objs),
        values=values,
        class_objs=class_objs,
    )


def fetch_estat_stats_data(
    *,
    stats_data_id: str,
    # Usage of dict: extra getStatsData query keys (cdCat01, cdTimeFrom, …).
    query_params: dict[str, str] | None = None,
    log_label: str,
) -> EstatStatsDataPayload | None:
    """GET one e-Stat getStatsData table; return values plus time labels."""
    # Usage of tuple: sorted query pairs so the cached helper stays hashable.
    query_params_items = tuple(sorted((query_params or {}).items()))
    return _fetch_estat_stats_data_cached(stats_data_id, query_params_items, log_label)


# __________________________________________________________
# Values (e-Stat Dashboard and FIES)
# __________________________________________________________


class _StatOfJpDataObj(TypedDict, total=False):
    """Wrapper around a single VALUE object ('@time' / '$' keys)."""

    # Open-key map of already-typed attribute / value strings from the API.
    VALUE: dict[str, str]


class _StatOfJpDataInf(TypedDict, total=False):
    """DATA_INF block."""

    DATA_OBJ: list[_StatOfJpDataObj]


class _StatOfJpStatisticalData(TypedDict, total=False):
    """STATISTICAL_DATA block."""

    DATA_INF: _StatOfJpDataInf


class _StatOfJpGetStats(TypedDict, total=False):
    """GET_STATS block."""

    STATISTICAL_DATA: _StatOfJpStatisticalData


class _StatOfJpPayload(TypedDict, total=False):
    """e-Stat Dashboard getData JSON root (fields we read)."""

    GET_STATS: _StatOfJpGetStats


_STAT_OF_JP_PAYLOAD_ADAPTER = TypeAdapter(_StatOfJpPayload)


def _parse_stat_of_jp_time_label(time_label: str) -> date | None:
    """Parse e-Stat Dashboard time codes ('YYYYMM00' / 'YYYY nQ00')."""
    monthly_match = re.fullmatch(r"(\d{4})(\d{2})00", time_label)
    if monthly_match:
        year = int(monthly_match.group(1))
        month = int(monthly_match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
        return None
    quarterly_match = re.fullmatch(r"(\d{4})(\d)Q00", time_label)
    if quarterly_match:
        year = int(quarterly_match.group(1))
        quarter = int(quarterly_match.group(2))
        if 1 <= quarter <= 4:
            return date(year, (quarter - 1) * 3 + 1, 1)
    return None


def _parse_stat_of_jp_values(
    payload: _StatOfJpPayload,
    *,
    value_scale: float = 1.0,
) -> list[ScrapingResult]:
    """Parse e-Stat Dashboard 'DATA_OBJ' values into scraping results."""
    data_objects = (
        payload.get("GET_STATS", {})
        .get("STATISTICAL_DATA", {})
        .get("DATA_INF", {})
        .get("DATA_OBJ", [])
    )
    economic_data: list[ScrapingResult] = []
    for data_object in data_objects:
        value_block = data_object.get("VALUE", {})
        time_label = value_block.get("@time")
        raw_value = value_block.get("$")
        if not time_label or raw_value is None or raw_value == "":
            continue
        period = _parse_stat_of_jp_time_label(time_label)
        if period is None:
            continue
        try:
            data_value = float(raw_value) * value_scale
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _build_fies_table3_url(year: int) -> str:
    """Return the Statistics Bureau Table 3 URL for one FIES calendar year."""
    if year >= 2025:
        return FIES_TABLE3_XLSX_URL_TEMPLATE.format(year=year)
    return FIES_TABLE3_XLS_URL_TEMPLATE.format(year=year)


def _extract_fies_decile_means_from_xls(workbook_bytes: bytes) -> list[float] | None:
    """Read equal-decile yearly-income means from a legacy FIES '.xls' Table 3."""
    workbook = xlrd.open_workbook(file_contents=workbook_bytes)
    worksheet = workbook.sheet_by_name(_FIES_TOTAL_HOUSEHOLDS_SHEET_NAME)
    for row_index in range(worksheet.nrows):
        row_label = str(worksheet.cell_value(row_index, 7))
        if _FIES_YEARLY_INCOME_LABEL not in row_label:
            continue
        decile_means: list[float] = []
        for column_offset in range(_FIES_DECILE_COUNT):
            cell_value = worksheet.cell_value(
                row_index, _FIES_FIRST_DECILE_COLUMN_INDEX + column_offset
            )
            if isinstance(cell_value, bool) or not isinstance(cell_value, (int, float)):
                return None
            decile_means.append(float(cell_value))
        return decile_means
    return None


def _extract_fies_decile_means_from_xlsx(workbook_bytes: bytes) -> list[float] | None:
    """Read equal-decile yearly-income means from an FIES '.xlsx' Table 3."""
    workbook = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True)
    worksheet = workbook[_FIES_TOTAL_HOUSEHOLDS_SHEET_NAME]
    for row_cells in worksheet.iter_rows(min_col=8, max_col=8):
        # openpyxl rows are 1-based; column 8 holds the Japanese item label.
        row_label_cell = row_cells[0]
        row_label = str(row_label_cell.value or "")
        if _FIES_YEARLY_INCOME_LABEL not in row_label:
            continue
        row_index = row_label_cell.row
        if row_index is None:
            continue
        decile_means: list[float] = []
        for column_offset in range(_FIES_DECILE_COUNT):
            # Excel columns are 1-based; deciles start at column 23.
            cell_value = worksheet.cell(
                row=row_index,
                column=_FIES_FIRST_DECILE_COLUMN_INDEX + 1 + column_offset,
            ).value
            if isinstance(cell_value, bool) or not isinstance(cell_value, (int, float)):
                return None
            decile_means.append(float(cell_value))
        return decile_means
    return None


def _extract_fies_decile_means(
    workbook_bytes: bytes, *, year: int
) -> list[float] | None:
    """Dispatch FIES Table 3 parse by workbook format for the given year."""
    if year >= 2025:
        return _extract_fies_decile_means_from_xlsx(workbook_bytes)
    return _extract_fies_decile_means_from_xls(workbook_bytes)


def _fetch_fies_decile_means_for_year(year: int) -> list[float] | None:
    """Download one FIES Table 3 workbook and return its decile yearly-income means."""
    table_url = _build_fies_table3_url(year)
    response = requests.get(table_url, timeout=60)
    if response.status_code >= 400:
        logger.warning(
            f"FIES Table 3 HTTP {response.status_code} for year={year}: {table_url}"
        )
        return None
    try:
        return _extract_fies_decile_means(response.content, year=year)
    except (KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        logger.warning(f"Failed to parse FIES Table 3 for year={year}: {exc}")
        return None


def _list_fies_derived_series(ticker: str) -> list[ScrapingResult]:
    """Build annual FIES-derived Gini (×100) or Palma from Table 3 decile means."""
    economic_data: list[ScrapingResult] = []
    latest_year = date.today().year
    for year in range(FIES_TABLE3_FIRST_YEAR, latest_year + 1):
        decile_means = _fetch_fies_decile_means_for_year(year)
        if decile_means is None:
            continue
        try:
            if ticker == FIES_GINI_TICKER:
                data_value = (
                    calculate_equal_group_gini(decile_means) * _FIES_GINI_TO_FRONT_SCALE
                )
            else:
                data_value = calculate_palma_from_decile_means(decile_means)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(
                period=date(year, 1, 1),
                data_value=data_value,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _get_dashboard_series(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape one e-Stat Dashboard IndicatorCode series."""
    series_config = STAT_OF_JP_SERIES_BY_TICKER.get(ticker)
    if series_config is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported STAT_OF_JP ticker: {ticker}",
            )
        ]

    series_params = series_config["params"]
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    stat_of_jp_request_params: dict[str, str] = {
        "Lang": STAT_OF_JP_DEFAULT_PARAMS["Lang"],
        "RegionCode": STAT_OF_JP_DEFAULT_PARAMS["RegionCode"],
        "TimeFrom": STAT_OF_JP_DEFAULT_PARAMS["TimeFrom"],
        "Cycle": series_params["Cycle"],
        "IsSeasonalAdjustment": series_params["IsSeasonalAdjustment"],
        "IndicatorCode": series_config["indicator_code"],
        "TimeTo": f"{date.today().year}1200",
    }
    response = requests.get(
        STAT_OF_JP_DATA_URL,
        params=stat_of_jp_request_params,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping JP e-Stat data: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        payload = _STAT_OF_JP_PAYLOAD_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Invalid JP e-Stat JSON: {exc}",
            )
        ]

    economic_data = _parse_stat_of_jp_values(
        payload,
        value_scale=series_config.get("value_scale", 1.0),
    )
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No JP e-Stat values found."
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_stat_of_jp(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get Japan series from e-Stat Dashboard or FIES Table 3.

    Dashboard tickers use IndicatorCode maps in 'STAT_OF_JP_SERIES_BY_TICKER'.
    FIES tickers derive annual Gini / Palma from Table 3 yearly-income deciles
    (total households).

    Sources: https://dashboard.e-stat.go.jp/en/static/api ,
    https://www.stat.go.jp/english/data/sousetai/
    """
    if ticker in {FIES_GINI_TICKER, FIES_PALMA_TICKER}:
        if frequency != EconomicPublicationFrequencyChoices.ANNUAL:
            return [
                ScrapingResult(
                    period=None,
                    data_value=None,
                    comment=f"Unsupported frequency for FIES scrape: {frequency}",
                )
            ]
        economic_data = _list_fies_derived_series(ticker)
        if not economic_data:
            return [
                ScrapingResult(
                    period=None,
                    data_value=None,
                    comment="No FIES-derived inequality values found.",
                )
            ]
        return filter_scraping_results_by_target_period(
            economic_data, target_period, frequency
        )
    return _get_dashboard_series(ticker, target_period, frequency)


# __________________________________________________________
# Publication dates (e-Stat release calendar)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _list_estat_release_calendar_events() -> list[tuple[datetime, str]]:
    """Fetch upcoming e-Stat release slots as (Asia/Tokyo local naive → kept local).

    Returns naive datetimes in Japan civil time; callers convert with a known clock
    when the stamp hour/minute is 00:00 (day-only) or keep the stamped clock.
    """
    today = timezone.now().date()
    end_date = today + timedelta(days=31 * ESTAT_RELEASE_CALENDAR_LOOKAHEAD_MONTHS)
    response = requests.get(
        ESTAT_RELEASE_CALENDAR_URL,
        params={
            "startYear": str(today.year),
            "startMonth": str(today.month),
            "startDay": str(today.day),
            "endYear": str(end_date.year),
            "endMonth": str(end_date.month),
            "endDay": str(end_date.day),
        },
        timeout=120,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping e-Stat release calendar: {response.text}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events: list[tuple[datetime, str]] = []
    for anchor in soup.find_all("a", href=True):
        match = re.search(
            r"/release-calendar/detail/\d+/(\d{12})",
            anchor["href"],
        )
        if match is None:
            continue
        stamp = match.group(1)
        try:
            release_local = datetime.strptime(stamp, "%Y%m%d%H%M")
        except ValueError:
            continue
        title = anchor.get_text(" ", strip=True)
        if not title:
            continue
        events.append((release_local, title))
    events.sort(key=lambda event: event[0])
    return events


def _get_publication_dates_from_estat_title_keywords(
    title_keywords: list[str],
    *,
    prefer_keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
) -> list[datetime]:
    """Return upcoming UTC datetimes for e-Stat titles matching keywords.

    Stamped hour/minute from the detail URL are Japan local wall times.
    """
    preferred = prefer_keywords or []
    excluded = exclude_keywords or []
    matched: list[datetime] = []
    preferred_matched: list[datetime] = []
    for release_local, title in _list_estat_release_calendar_events():
        if not any(keyword in title for keyword in title_keywords):
            continue
        if any(keyword in title for keyword in excluded):
            continue
        utc_datetime = convert_local_wall_time_to_utc(
            release_local.year,
            release_local.month,
            release_local.day,
            release_local.hour,
            release_local.minute,
            source_timezone="Asia/Tokyo",
        )
        if preferred and any(keyword in title for keyword in preferred):
            preferred_matched.append(utc_datetime)
        else:
            matched.append(utc_datetime)
    upcoming_source = preferred_matched if preferred_matched else matched
    upcoming_source = sorted(set(upcoming_source))
    return filter_upcoming_publication_dates(upcoming_source)


def get_publication_dates_from_estat_for_technical_name(
    name: str,
) -> list[datetime]:
    """Resolve a seeded 'technical_name' against the e-Stat keyword map."""
    calendar_match = ESTAT_SCHEDULE_MATCH_BY_TECHNICAL_NAME.get(name)
    if calendar_match is None:
        logger.warning(
            f"No e-Stat release-calendar keyword map for technical_name={name}."
        )
        return []
    return _get_publication_dates_from_estat_title_keywords(
        list(calendar_match.title_keywords),
        prefer_keywords=list(calendar_match.prefer_keywords),
        exclude_keywords=list(calendar_match.exclude_keywords),
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_stat_of_jp(name: str) -> list[datetime]:
    """Get upcoming Statistics Bureau dates from the e-Stat release calendar.

    CPI, LFS, and IIP have dated slots. FIES inequality tables are irregular
    annual products and stay empty when no keyword map matches.
    """
    return get_publication_dates_from_estat_for_technical_name(name)
