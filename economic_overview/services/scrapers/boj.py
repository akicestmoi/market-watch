"""Scrape Bank of Japan Tankan DI, Flow of Funds, and CGPI / SPPI series."""

import csv
import io
import logging
import re
import zipfile
from datetime import date, datetime
from typing import NamedTuple, TypedDict

import openpyxl
import requests
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    BOJ_FOF_FLAT_FILE_ZIP_URL,
    BOJ_FOF_GG_DEBT_SECURITIES_TICKER,
    BOJ_FOF_GG_FINANCIAL_SURPLUS_SERIES_ID,
    BOJ_FOF_GG_LOANS_TICKER,
    BOJ_FOF_GG_NET_LIABILITIES_TICKER,
    BOJ_FOF_GG_OTHER_LIABILITIES_TICKER,
    BOJ_FOF_GG_TOTAL_LIABILITIES_SERIES_ID,
    BOJ_FOF_OKU_YEN_TO_BILLION_YEN,
    BOJ_FOF_QUARTERLY_CSV_NAME,
    BOJ_FOF_SERIES_ID_BY_TICKER,
    BOJ_HH_DEBT_RATIO_TICKER,
    BOJ_HH_LOANS_STOCK_TICKER,
    BOJ_RELEASE_SCHEDULE_XLSX_URL,
    BOJ_RELEASE_TOKYO_HOUR,
    BOJ_RELEASE_TOKYO_MINUTE,
    BOJ_SCHEDULE_SERIES_TITLE_BY_TECHNICAL_NAME,
    BOJ_TIME_SERIES_API_URL,
    BOJ_TIME_SERIES_BY_TICKER,
    JP_CAO_HH_DEBT_INCOME_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    calculate_ratio_scraping_results_as_percent,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
    subtract_scraping_results_by_period,
)
from economic_overview.services.scrapers.jp_cabinet_office import (
    get_data_from_japan_cabinet_office,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (Tankan, Flow of Funds, and price indexes)
# __________________________________________________________


def _parse_boj_fof_yyyyq_label(period_label: str) -> date | None:
    """Parse BoJ FOF flat-file period labels ('YYYY0Q' → first day of quarter)."""
    match = re.fullmatch(r"(\d{4})0([1-4])", period_label.strip())
    if match is None:
        return None
    year = int(match.group(1))
    quarter = int(match.group(2))
    return date(year, (quarter - 1) * 3 + 1, 1)


def _parse_boj_fof_series_csv(csv_text: str, series_id: str) -> list[ScrapingResult]:
    """Parse one series from the BoJ FOF quarterly flat file (億円 → billion yen)."""
    reader = csv.reader(io.StringIO(csv_text))
    try:
        header_row = next(reader)
    except StopIteration:
        return []
    # Usage of dict: keys are CSV column indexes; values are quarter-start dates.
    period_by_column: dict[int, date] = {}
    for column_index, period_label in enumerate(header_row):
        period = _parse_boj_fof_yyyyq_label(period_label)
        if period is not None:
            period_by_column[column_index] = period

    economic_data: list[ScrapingResult] = []
    for row in reader:
        if not row:
            continue
        if row[0].strip() != series_id:
            continue
        for column_index, period in period_by_column.items():
            if column_index >= len(row):
                continue
            raw_value = row[column_index].strip()
            if not raw_value:
                continue
            try:
                # Flat file is 億円; convert to billion yen for ESRI alignment.
                data_value = float(raw_value) * BOJ_FOF_OKU_YEN_TO_BILLION_YEN
            except ValueError:
                continue
            economic_data.append(
                ScrapingResult(period=period, data_value=data_value, comment="")
            )
        break
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


class _BojFofQuarterlyCsvDownload(NamedTuple):
    """Decoded FOF quarterly CSV text, or the error comment when download failed."""

    csv_text: str
    error_comment: str


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _download_boj_fof_quarterly_csv() -> _BojFofQuarterlyCsvDownload:
    """Download the BoJ FOF flat-file ZIP once and decode the quarterly CSV."""
    response = requests.get(
        BOJ_FOF_FLAT_FILE_ZIP_URL,
        timeout=120,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping BoJ FOF flat file: {response.text}")
        return _BojFofQuarterlyCsvDownload(csv_text="", error_comment=response.text)
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_archive:
            with zip_archive.open(BOJ_FOF_QUARTERLY_CSV_NAME) as csv_file:
                csv_text = csv_file.read().decode("cp932", errors="replace")
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        return _BojFofQuarterlyCsvDownload(
            csv_text="",
            error_comment=f"Error reading BoJ FOF quarterly CSV: {exc}",
        )
    return _BojFofQuarterlyCsvDownload(csv_text=csv_text, error_comment="")


def _get_boj_fof_series(series_id: str) -> list[ScrapingResult]:
    """Get one FOF flat-file series in billion yen, or a single error result."""
    csv_download = _download_boj_fof_quarterly_csv()
    if csv_download.error_comment:
        return [
            ScrapingResult(
                period=None, data_value=None, comment=csv_download.error_comment
            )
        ]
    economic_data = _parse_boj_fof_series_csv(csv_download.csv_text, series_id)
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No BoJ FOF values found for {series_id}.",
            )
        ]
    return economic_data


def _is_boj_error_result(economic_data: list[ScrapingResult]) -> bool:
    """Return True when 'economic_data' is a single unresolved error result."""
    # A failed scrape returns exactly one empty error result at index 0.
    return (
        len(economic_data) == 1
        and economic_data[0]["period"] is None
        and economic_data[0]["data_value"] is None
    )


class _BojTimeSeriesValues(TypedDict, total=False):
    """BoJ getDataCode VALUES block (survey dates + observation list)."""

    SURVEY_DATES: list[int]
    VALUES: list[float | int | None]


class _BojTimeSeriesResult(TypedDict, total=False):
    """One series object inside a BoJ getDataCode RESULTSET."""

    SERIES_CODE: str
    VALUES: _BojTimeSeriesValues


class _BojTimeSeriesPayload(TypedDict, total=False):
    """BoJ Time-Series getDataCode JSON envelope fields we read."""

    STATUS: int
    MESSAGE: str
    RESULTSET: list[_BojTimeSeriesResult]


_BOJ_TIME_SERIES_PAYLOAD_ADAPTER = TypeAdapter(_BojTimeSeriesPayload)


def _parse_boj_yyyymm_label(period_label: int | str) -> date | None:
    """Parse BoJ monthly survey labels ('YYYYMM' → first day of month)."""
    match = re.fullmatch(r"(\d{4})(\d{2})", str(period_label).strip())
    if match is None:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def _parse_boj_yyyyq_label(period_label: int | str) -> date | None:
    """Parse BoJ quarterly Tankan labels ('YYYYQ' with Q in 1..4 → quarter start)."""
    match = re.fullmatch(r"(\d{4})0?([1-4])", str(period_label).strip())
    if match is None:
        return None
    year = int(match.group(1))
    quarter = int(match.group(2))
    return date(year, (quarter - 1) * 3 + 1, 1)


def _parse_boj_time_series_payload(
    payload: _BojTimeSeriesPayload,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Parse BoJ getDataCode JSON into newest-first scraping results."""
    result_set = payload.get("RESULTSET") or []
    if not result_set:
        return []
    # GetDataCode was called for one series code, so RESULTSET has that series row.
    series_result = result_set[0]
    values_block = series_result.get("VALUES") or {}
    survey_dates = values_block.get("SURVEY_DATES") or []
    observation_values = values_block.get("VALUES") or []
    economic_data: list[ScrapingResult] = []
    for survey_date, raw_value in zip(survey_dates, observation_values, strict=False):
        if raw_value is None:
            continue
        if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
            period = _parse_boj_yyyyq_label(survey_date)
        else:
            period = _parse_boj_yyyymm_label(survey_date)
        if period is None:
            continue
        try:
            data_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _download_boj_time_series(ticker: str) -> list[ScrapingResult]:
    """Download one configured BoJ Time-Series getDataCode series."""
    series = BOJ_TIME_SERIES_BY_TICKER[ticker]
    response = requests.get(
        BOJ_TIME_SERIES_API_URL,
        params={
            "db": series.db,
            "code": series.code,
            "lang": "en",
            "format": "json",
            "startDate": series.start_date,
        },
        timeout=90,
    )
    if response.status_code >= 400:
        logger.warning(
            f"Error scraping BoJ time series {ticker}: {response.text[:500]}"
        )
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        payload = _BOJ_TIME_SERIES_PAYLOAD_ADAPTER.validate_python(response.json())
    except (ValidationError, ValueError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing BoJ time-series JSON ({ticker}): {exc}",
            )
        ]
    status_code = payload.get("STATUS")
    if status_code != 200:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    payload.get("MESSAGE")
                    or f"BoJ time-series STATUS={status_code} ({ticker})"
                ),
            )
        ]
    economic_data = _parse_boj_time_series_payload(payload, series.frequency)
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No BoJ time-series values found for {ticker}.",
            )
        ]
    return economic_data


def _get_boj_unsupported_frequency_result(
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Return a scrape error when quarterly-only BoJ paths receive another frequency."""
    return [
        ScrapingResult(
            period=None,
            data_value=None,
            comment=f"Unsupported frequency for BOJ scrape: {frequency}",
        )
    ]


def _get_boj_configured_time_series_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape and filter one BoJ Time-Series API ticker."""
    series = BOJ_TIME_SERIES_BY_TICKER[ticker]
    if frequency != series.frequency:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    f"Unsupported frequency for BOJ time-series scrape: {frequency}"
                ),
            )
        ]
    economic_data = _download_boj_time_series(ticker)
    # Error results use period=None at index 0.
    if (
        economic_data
        and economic_data[0]["period"] is None
        and economic_data[0]["data_value"] is None
    ):
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


def _get_boj_household_debt_ratio_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Derive household loan stock over disposable income as a percent series."""
    debt_series = get_data_from_boj(BOJ_HH_LOANS_STOCK_TICKER, target_period, frequency)
    income_series = get_data_from_japan_cabinet_office(
        JP_CAO_HH_DEBT_INCOME_TICKER, target_period, frequency
    )
    debt_ratio_series = calculate_ratio_scraping_results_as_percent(
        debt_series, income_series
    )
    if not debt_ratio_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No BoJ household debt-ratio values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        debt_ratio_series, target_period, frequency
    )


def _get_boj_fof_ticker_data(
    fof_series_id: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape and filter one BoJ Flow-of-Funds flat-file series."""
    economic_data = _get_boj_fof_series(fof_series_id)
    if _is_boj_error_result(economic_data):
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


def _get_boj_fof_gg_net_liabilities_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Derive general-government net liabilities from total liabilities minus surplus."""
    total_liabilities_series = _get_boj_fof_series(
        BOJ_FOF_GG_TOTAL_LIABILITIES_SERIES_ID
    )
    if _is_boj_error_result(total_liabilities_series):
        return total_liabilities_series
    net_liabilities_series = subtract_scraping_results_by_period(
        total_liabilities_series,
        _get_boj_fof_series(BOJ_FOF_GG_FINANCIAL_SURPLUS_SERIES_ID),
    )
    if not net_liabilities_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No BoJ FOF general-government liability values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        net_liabilities_series, target_period, frequency
    )


def _get_boj_fof_gg_other_liabilities_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Derive general-government other liabilities net of debt securities and loans."""
    other_liabilities_series = get_data_from_boj(
        BOJ_FOF_GG_NET_LIABILITIES_TICKER, target_period, frequency
    )
    # Subtract one input at a time so only periods present in every input stay.
    for instrument_ticker in [
        BOJ_FOF_GG_DEBT_SECURITIES_TICKER,
        BOJ_FOF_GG_LOANS_TICKER,
    ]:
        other_liabilities_series = subtract_scraping_results_by_period(
            other_liabilities_series,
            get_data_from_boj(instrument_ticker, target_period, frequency),
        )
    if not other_liabilities_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=("No BoJ FOF general-government other-liability values found."),
            )
        ]
    return filter_scraping_results_by_target_period(
        other_liabilities_series, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_boj(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.QUARTERLY,
) -> list[ScrapingResult]:
    """Get a BoJ Tankan DI, Flow of Funds loans, or CGPI / SPPI series.

    Tankan (quarterly Time-Series API, db=CO):
    - Business Conditions DI — Manufacturing / Nonmanufacturing × Large /
      Medium / Small (`TK99F1000601GCQ0*` / `TK99F2000601GCQ0*`)
    - Employment Conditions DI — All industries × Large / Medium / Small
      (`TK99F0000608GCQ0*`)

    Flow of Funds: 'fof_hh_loans' is household loan liabilities stock
    (FF'FOF_FFAS430L200), stored in billion yen. 'hh_debt_ratio' is that stock
    divided by ESRI / Cabinet Office nominal disposable income (SAAR), so the
    denominator is not multiplied by four. General-government RELATED detail
    under GGO Net Liabilities: 'fof_gg_debt_securities' is L300; 'fof_gg_loans'
    is L200; 'fof_gg_net_liabilities' is L900 − L700 (internal); and
    'fof_gg_other_liabilities' is net liabilities − L300 − L200.

    Producer prices (monthly Time-Series API):
    - 'PRCG20_2200000000' — Corporate Goods Price Index, all commodities
    - 'PRCS20_5200000000' — Services Producer Price Index, all items

    Sources:
    - Tankan / CGPI / SPPI API: https://www.stat-search.boj.or.jp/api/v1/getDataCode
    - FOF flat files: https://www.stat-search.boj.or.jp/info/dload_en.html
    """
    if ticker in BOJ_TIME_SERIES_BY_TICKER:
        return _get_boj_configured_time_series_data(ticker, target_period, frequency)

    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return _get_boj_unsupported_frequency_result(frequency)

    if ticker == BOJ_HH_DEBT_RATIO_TICKER:
        return _get_boj_household_debt_ratio_data(target_period, frequency)

    fof_series_id = BOJ_FOF_SERIES_ID_BY_TICKER.get(ticker)
    if fof_series_id is not None:
        return _get_boj_fof_ticker_data(fof_series_id, target_period, frequency)

    if ticker == BOJ_FOF_GG_NET_LIABILITIES_TICKER:
        return _get_boj_fof_gg_net_liabilities_data(target_period, frequency)

    if ticker == BOJ_FOF_GG_OTHER_LIABILITIES_TICKER:
        return _get_boj_fof_gg_other_liabilities_data(target_period, frequency)

    return [
        ScrapingResult(
            period=None,
            data_value=None,
            comment=f"Unsupported BOJ ticker: {ticker}",
        )
    ]


# __________________________________________________________
# Publication dates (BoJ release schedule)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_boj(name: str) -> list[datetime]:
    """Get upcoming BoJ dates from the official statistics release workbook.

    Source: https://www.boj.or.jp/en/statistics/outline/tkohyos.xlsx
    Clock is 08:50 Asia/Tokyo (BoJ schedule note for time-series releases).
    """
    series_title = BOJ_SCHEDULE_SERIES_TITLE_BY_TECHNICAL_NAME.get(name)
    if series_title is None:
        logger.warning(f"No BoJ schedule series mapping for technical_name={name}")
        return []

    response = requests.get(
        BOJ_RELEASE_SCHEDULE_XLSX_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error downloading BoJ release schedule: {response.text}")
        return []

    workbook = openpyxl.load_workbook(io.BytesIO(response.content), data_only=True)
    worksheet = workbook["Statistics data"]
    publication_datetimes: list[datetime] = []
    for row_cells in worksheet.iter_rows(min_row=1, values_only=True):
        series_name = row_cells[1]
        frequency_label = row_cells[3]
        if not isinstance(series_name, str):
            continue
        stripped_series_name = series_name.strip()
        if (
            stripped_series_name != series_title
            and not stripped_series_name.startswith(series_title)
        ):
            continue
        if not isinstance(frequency_label, str):
            continue
        if "Monthly" not in frequency_label and "Quarterly" not in frequency_label:
            continue
        for cell_value in row_cells[4:]:
            if not isinstance(cell_value, datetime):
                continue
            publication_datetimes.append(
                convert_local_wall_time_to_utc(
                    cell_value.year,
                    cell_value.month,
                    cell_value.day,
                    BOJ_RELEASE_TOKYO_HOUR,
                    BOJ_RELEASE_TOKYO_MINUTE,
                    source_timezone="Asia/Tokyo",
                )
            )
        if publication_datetimes:
            break
    publication_datetimes.sort()
    return filter_upcoming_publication_dates(publication_datetimes)
