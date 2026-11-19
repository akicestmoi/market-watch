"""Scrape Japan Ministry of Finance BoP tables and corporate-survey industry data."""

import csv
import io
import logging
from datetime import date, datetime
from typing import TypedDict

import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    INDUSTRY_PROFITABILITY_START_YEAR,
    MOF_BOP_COLUMN_INDEX_BY_TICKER,
    MOF_BOP_OKUYEN_PER_BILLION_YEN,
    MOF_BOP_QUARTER_START_MONTH_BY_LABEL,
    MOF_BOP_SA_QUARTERLY_CSV_URL,
    MOF_CORPORATE_AGGREGATE_INDUSTRY_CODES,
    MOF_CORPORATE_ALL_SIZES_CODE,
    MOF_CORPORATE_OPERATING_PROFIT_ITEM_CODE,
    MOF_CORPORATE_STATS_DATA_ID,
    MOF_CORPORATE_TURNOVER_ITEM_CODE,
)
from economic_overview.services.scrapers.boj import get_publication_dates_from_boj
from economic_overview.services.scrapers.common import (
    ScrapedIndustryProfitability,
    ScrapingResult,
    filter_scraping_results_by_target_period,
)
from economic_overview.services.scrapers.stat_of_jp import (
    EstatJsonObject,
    EstatJsonValue,
    fetch_estat_stats_data,
    list_estat_dict_entries,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (balance of payments)
# __________________________________________________________


def _decode_mof_csv_bytes(raw_content: bytes) -> str:
    """Decode MOF CSV bytes (Shift_JIS / cp932 on the live file)."""
    for encoding in ("cp932", "shift_jis", "utf-8-sig", "utf-8"):
        try:
            return raw_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_content.decode("cp932", errors="replace")


def _parse_mof_okuyen_cell(raw_cell: str) -> float | None:
    """Parse one MOF amount cell in 100 million yen into a float."""
    cleaned_cell = (
        raw_cell.strip()
        .replace(",", "")
        .replace(" ", "")
        .replace("(P)", "")
        .replace("Ｐ", "")
    )
    if not cleaned_cell or cleaned_cell in {"…", "...", "-", "―", "－"}:
        return None
    try:
        return float(cleaned_cell)
    except ValueError:
        return None


def _parse_mof_bop_sa_quarterly_csv(
    csv_text: str, column_index: int
) -> list[ScrapingResult]:
    """Parse MOF 6s-a-1 seasonally adjusted quarterly BoP CSV for one column."""
    reader = csv.reader(io.StringIO(csv_text))
    economic_data: list[ScrapingResult] = []
    calendar_year: int | None = None
    for row in reader:
        if len(row) <= column_index:
            continue
        year_label = row[2].strip() if len(row) > 2 else ""
        quarter_label = row[3].strip() if len(row) > 3 else ""
        if year_label.isdigit():
            calendar_year = int(year_label)
        quarter_start_month = MOF_BOP_QUARTER_START_MONTH_BY_LABEL.get(quarter_label)
        if calendar_year is None or quarter_start_month is None:
            continue
        okuyen_value = _parse_mof_okuyen_cell(row[column_index])
        if okuyen_value is None:
            continue
        economic_data.append(
            ScrapingResult(
                period=date(calendar_year, quarter_start_month, 1),
                data_value=okuyen_value / MOF_BOP_OKUYEN_PER_BILLION_YEN,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_mof(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.QUARTERLY,
) -> list[ScrapingResult]:
    """Get Japan BoP values from MOF table 6s-a-1 (seasonally adjusted quarterly).

    Source page: MOF 'bpnet.htm' balance-of-payments historical tables.
    Stored Abs values are billion yen (source 億円 ÷ 10).
    """
    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for MOF scrape: {frequency}",
            )
        ]
    column_index = MOF_BOP_COLUMN_INDEX_BY_TICKER.get(ticker)
    if column_index is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported MOF ticker: {ticker}",
            )
        ]

    response = requests.get(
        MOF_BOP_SA_QUARTERLY_CSV_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping MOF data: {response.text[:500]}")
        return [
            ScrapingResult(period=None, data_value=None, comment=response.text[:500])
        ]

    csv_text = _decode_mof_csv_bytes(response.content)
    economic_data = _parse_mof_bop_sa_quarterly_csv(csv_text, column_index)
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No MOF BoP series values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (MOF schedule)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_mof(name: str) -> list[datetime]:
    """Get upcoming BoP dates from the BoJ statistics release workbook.

    MOF publishes the CSV; BoJ lists the shared Balance of Payments slots.
    """
    return get_publication_dates_from_boj(name)


# __________________________________________________________
# Industry profitability (corporate survey turnover and operating profit)
# __________________________________________________________


class _EstatValueCell(TypedDict):
    """One metric cell after normalizing e-Stat VALUE attributes."""

    industry_code: str
    time_code: str
    amount_text: str


class _MofMergedIndustryMetrics(TypedDict):
    """Merged turnover / operating profit for one MOF industry-year."""

    industry_code: str
    industry_label: str
    year: int
    turnover: float | None
    operating_profit: float | None


def _parse_estat_time_code(time_code: str) -> int | None:
    """Parse e-Stat codes such as '20100' into the fiscal-year start calendar year."""
    if len(time_code) < 4 or not time_code[:4].isdigit():
        return None
    return int(time_code[:4])


def _should_skip_industry_label(industry_label: str) -> bool:
    """True for discontinued footnote industries or explicit aggregate labels."""
    return "まで" in industry_label or "集約" in industry_label


def _build_industry_labels_by_code(class_objs: EstatJsonValue) -> dict[str, str]:
    """Map industry codes → labels from CLASS_INF cat02."""
    # Usage of dict: MOF industry code → Japanese industry label.
    labels_by_code: dict[str, str] = {}
    for class_obj in list_estat_dict_entries(class_objs):
        if class_obj.get("@id") != "cat02":
            continue
        for class_entry in list_estat_dict_entries(class_obj.get("CLASS")):
            industry_code = str(class_entry.get("@code") or "").strip()
            industry_label = str(class_entry.get("@name") or "").strip()
            if industry_code and industry_label:
                labels_by_code[industry_code] = industry_label
    return labels_by_code


def _build_value_cells(raw_values: list[EstatJsonObject]) -> list[_EstatValueCell]:
    """Map e-Stat VALUE rows into typed industry/time/amount cells."""
    value_cells: list[_EstatValueCell] = []
    for raw_value in raw_values:
        industry_code = str(raw_value.get("@cat02") or "").strip()
        time_code = str(raw_value.get("@time") or "").strip()
        amount_text = str(raw_value.get("$") or "").strip().replace(",", "")
        if not industry_code or not time_code or not amount_text:
            continue
        value_cells.append(
            _EstatValueCell(
                industry_code=industry_code,
                time_code=time_code,
                amount_text=amount_text,
            )
        )
    return value_cells


def _format_industry_year_key(industry_code: str, year: int) -> str:
    """Stable string key for one MOF industry-year merge bucket."""
    return f"{industry_code}|{year}"


# Usage of tuple: industry labels by code and parsed e-Stat value cells for one item.
def _fetch_mof_item_cells(
    item_code: str,
) -> tuple[dict[str, str], list[_EstatValueCell]]:
    """Fetch one MOF item code and return industry labels plus value cells."""
    time_from = f"{INDUSTRY_PROFITABILITY_START_YEAR}0"
    payload = fetch_estat_stats_data(
        stats_data_id=MOF_CORPORATE_STATS_DATA_ID,
        query_params={
            "cdCat01": item_code,
            "cdCat03": MOF_CORPORATE_ALL_SIZES_CODE,
            "cdTimeFrom": time_from,
        },
        log_label=f"MOF corporate item {item_code}",
    )
    if payload is None:
        return {}, []
    return (
        _build_industry_labels_by_code(payload["class_objs"]),
        _build_value_cells(payload["values"]),
    )


def _apply_mof_value_cells_to_metrics(
    value_cells: list[_EstatValueCell],
    *,
    industry_labels_by_code: dict[str, str],
    metrics_by_key: dict[str, _MofMergedIndustryMetrics],
    is_turnover: bool,
) -> None:
    """Merge one MOF metric column into industry-year turnover / profit buckets."""
    for value_cell in value_cells:
        industry_code = value_cell["industry_code"]
        if industry_code in MOF_CORPORATE_AGGREGATE_INDUSTRY_CODES:
            continue
        industry_label = industry_labels_by_code.get(industry_code, industry_code)
        if _should_skip_industry_label(industry_label):
            continue
        period_year = _parse_estat_time_code(value_cell["time_code"])
        if period_year is None or period_year < INDUSTRY_PROFITABILITY_START_YEAR:
            continue
        try:
            amount = float(value_cell["amount_text"])
        except ValueError:
            continue
        merge_key = _format_industry_year_key(industry_code, period_year)
        existing = metrics_by_key.get(merge_key)
        if existing is None:
            existing = _MofMergedIndustryMetrics(
                industry_code=industry_code,
                industry_label=industry_label,
                year=period_year,
                turnover=None,
                operating_profit=None,
            )
            metrics_by_key[merge_key] = existing
        if is_turnover:
            existing["turnover"] = amount
        else:
            existing["operating_profit"] = amount


def _format_mof_scraped_industry_profitabilities(
    metrics_by_key: dict[str, _MofMergedIndustryMetrics],
) -> list[ScrapedIndustryProfitability]:
    """Format merged MOF industry metrics into scraped industry profitabilities."""
    return [
        ScrapedIndustryProfitability(
            industry_code=merged["industry_code"],
            industry_label=merged["industry_label"],
            period=date(merged["year"], 1, 1),
            turnover=merged["turnover"],
            operating_profit=merged["operating_profit"],
            gva=None,
        )
        for merged in metrics_by_key.values()
    ]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_industry_profitability_from_mof() -> list[ScrapedIndustryProfitability]:
    """Scrape JP MOF corporate-survey sales and operating profit (million yen)."""
    turnover_labels, turnover_cells = _fetch_mof_item_cells(
        MOF_CORPORATE_TURNOVER_ITEM_CODE
    )
    profit_labels, profit_cells = _fetch_mof_item_cells(
        MOF_CORPORATE_OPERATING_PROFIT_ITEM_CODE
    )
    # Usage of dict: MOF industry code → Japanese industry label.
    industry_labels_by_code: dict[str, str] = {**turnover_labels, **profit_labels}
    # Usage of dict: industry|year → merged turnover / operating profit.
    metrics_by_key: dict[str, _MofMergedIndustryMetrics] = {}
    _apply_mof_value_cells_to_metrics(
        turnover_cells,
        industry_labels_by_code=industry_labels_by_code,
        metrics_by_key=metrics_by_key,
        is_turnover=True,
    )
    _apply_mof_value_cells_to_metrics(
        profit_cells,
        industry_labels_by_code=industry_labels_by_code,
        metrics_by_key=metrics_by_key,
        is_turnover=False,
    )
    return _format_mof_scraped_industry_profitabilities(metrics_by_key)
