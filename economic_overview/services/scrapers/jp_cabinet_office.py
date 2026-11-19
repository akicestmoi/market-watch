"""Scrape Japan Cabinet Office (ESRI) SNA and SDDS Plus series.

Supported tickers for 'get_data_from_japan_cabinet_office':
- 'gaku-jk*' real SA expenditure GDP and demand components (quarterly)
- 'gaku-mk' nominal SA GDP (annualized levels; Nominal GDP / vsGDP)
- 'ggd_total' general government gross debt outstanding (billion yen)
- 'ggo_net_lending' / 'ggo_revenue' / 'ggo_taxes' /
  'ggo_social_contributions' / 'ggo_expense' / 'ggo_interest' SDDS Plus
  General Government Operations (quarterly NSA)
- 'ggo_net_acquisition_financial_assets' / 'ggo_net_incurrence_liabilities'
  GGO financial account transactions (quarterly NSA)
- 'ggo_other_revenue' = GGO Revenue − Taxes − Social contributions
- 'ggo_financing_account' = Net incurrence of liabilities − Net acquisition
  of financial assets
- 'esri_cofog_total' / 'esri_cofog_gf01'…'gf10' Supporting Table 7
  general-government total outlays by function (fiscal year, billion yen);
  the workbook URL is resolved from the newest annual-estimates release
- 'kakei_nominal_di' / 'kakei_nominal_consumption' / 'kakei_nominal_saving' /
  'kakei_real_di' (SA sheet cols I / K / L / P)
- 'kakei_saving_ratio' = Saving / DI × 100 (workbook col-N % is truncated)
- 'kakei_consumption_ratio' = Consumption of households / DI × 100
- 'shouhi_cci_sa' Consumer Confidence Index (monthly SA, 0–100)
- 'shouhi_employment_sa' Consumer Perception Index — Employment (monthly SA)
- 'machinery_orders_private_ex_volatile_sa' Machinery Orders private excl.
  volatile (monthly SA, billion yen; e-Stat getStatsData)

Source: https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html
Debt / GGO: https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html
COFOG: https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html
Household income: https://www.esri.cao.go.jp/jp/sna/sonota/kakei/household_top.html
Consumer survey: https://www.esri.cao.go.jp/en/stat/shouhi/shouhi-e.html
Machinery Orders: e-Stat statsDataId 0003355222
Industry GVA: https://www.esri.cao.go.jp/jp/sna/sonota/seisanqna/seisanqna_top.html
"""

import csv
import io
import logging
import re
from datetime import date, datetime
from typing import NamedTuple, TypedDict
from urllib.parse import urljoin

import openpyxl
import pandas as pd
import requests
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    ESRI_GVA_TEN_OKU_YEN_TO_MILLION,
    INDUSTRY_PROFITABILITY_START_YEAR,
    JP_CAO_COFOG_FIRST_DATA_ROW,
    JP_CAO_COFOG_FISCAL_YEAR_ROW,
    JP_CAO_COFOG_MIN_XLSX_BYTES,
    JP_CAO_COFOG_OUTLAY_COLUMNS,
    JP_CAO_COFOG_ROW_KEY_BY_TICKER,
    JP_CAO_COFOG_URL_LOOKBACK_YEARS,
    JP_CAO_COFOG_XLSX_URL_TEMPLATE,
    JP_CAO_DEBT_OUTSTANDING_TICKER,
    JP_CAO_GGD_QUARTER_START_MONTH_BY_END_MONTH,
    JP_CAO_GGO_FINANCING_ACCOUNT_TICKER,
    JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER,
    JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER,
    JP_CAO_GGO_OTHER_REVENUE_TICKER,
    JP_CAO_GGO_REVENUE_TICKER,
    JP_CAO_GGO_ROW_LABEL_BY_TICKER,
    JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER,
    JP_CAO_GGO_TAXES_TICKER,
    JP_CAO_GGO_TICKERS,
    JP_CAO_GGO_XLSX_URL,
    JP_CAO_HH_CONSUMPTION_RATIO_TICKER,
    JP_CAO_HH_SAVING_RATIO_TICKER,
    JP_CAO_KAKEI_COLUMN_BY_TICKER,
    JP_CAO_KAKEI_FILES_ORIGIN,
    JP_CAO_KAKEI_FILES_PAGE_URL,
    JP_CAO_KAKEI_SA_SHEET_MARKER,
    JP_CAO_MACHINERY_ORDERS_DEMAND_CODE,
    JP_CAO_MACHINERY_ORDERS_MILLION_YEN_PER_BILLION,
    JP_CAO_MACHINERY_ORDERS_SA_SERIES_CODE,
    JP_CAO_MACHINERY_ORDERS_STATS_DATA_ID,
    JP_CAO_MACHINERY_ORDERS_TICKER,
    JP_CAO_NOMINAL_GDP_TICKER,
    JP_CAO_NOMINAL_HH_CONSUMPTION_TICKER,
    JP_CAO_NOMINAL_HH_DI_TICKER,
    JP_CAO_NOMINAL_HH_SAVING_TICKER,
    JP_CAO_NOMINAL_SA_CSV_FILENAME_PREFIX,
    JP_CAO_REAL_SA_COLUMN_BY_TICKER,
    JP_CAO_REAL_SA_CSV_FILENAME_PREFIX,
    JP_CAO_SDDS_PLUS_PAGE_URL,
    JP_CAO_SEISANQNA_TOP_URL,
    JP_CAO_SHOUHI_COLUMN_BY_TICKER,
    JP_CAO_SHOUHI_SA_XLSX_URL,
    JP_CAO_SITE_ORIGIN,
    JP_CAO_YEAR_ARCHIVE_URL,
)
from economic_overview.services.scrapers.common import (
    ScrapedIndustryProfitability,
    ScrapingResult,
    calculate_ratio_scraping_results_as_percent,
    filter_scraping_results_by_target_period,
    subtract_scraping_results_by_period,
)
from economic_overview.services.scrapers.stat_of_jp import (
    fetch_estat_stats_data,
    get_publication_dates_from_estat_for_technical_name,
    parse_estat_month_time_code,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (SNA and SDDS Plus)
# __________________________________________________________

_SEISANQNA_RELEASE_HREF_RE = re.compile(
    r'href="(/jp/sna/sonota/seisanqna/seisanqna_(\d{4})q([1-4])\.html)"',
    re.IGNORECASE,
)
_NOMINAL_ORIGINAL_GVA_CSV_HREF_RE = re.compile(
    r'href="(/jp/sna/data/data_list/seisanqna/files/tables/[^"]+/gaku-mgf[^"]+\.csv)"',
    re.IGNORECASE,
)

# Finest published economic-activity columns in gaku-mgf*.csv (0-based).
# Skips Manufacturing total (5) and aggregate GDP / sector totals (33+).
# Usage of tuple: fixed (column_index, industry_code) pairs for the CSV layout.
_ESRI_LEAF_INDUSTRY_COLUMNS: tuple[tuple[int, str], ...] = (
    (3, "1"),
    (4, "2"),
    (6, "3.1"),
    (7, "3.2"),
    (8, "3.3"),
    (9, "3.4"),
    (10, "3.5"),
    (11, "3.6"),
    (12, "3.7"),
    (13, "3.8"),
    (14, "3.9"),
    (15, "3.10"),
    (16, "3.11"),
    (17, "3.12"),
    (18, "3.13"),
    (19, "3.14"),
    (20, "4"),
    (21, "5"),
    (22, "6"),
    (23, "7"),
    (24, "8"),
    (25, "9"),
    (26, "10"),
    (27, "11"),
    (28, "12"),
    (29, "13"),
    (30, "14"),
    (31, "15"),
    (32, "16"),
)


def _find_japan_cabinet_office_quarterly_estimates_csv_url(
    csv_filename_prefix: str,
) -> str | None:
    """Return the download URL of one SNA quarterly-estimates CSV.

    Cabinet Office does not publish a stable direct link. This helper:

    1. Opens the year archive page (current year, then previous) and finds the
       latest quarterly-estimates English menu ('…/qe…/gdemenuea.html').
    2. Opens that menu and finds an 'href' whose filename contains
       'csv_filename_prefix' and ends in '.csv'
       (e.g. 'gaku-jk' → '…/gaku-jk2622.csv').

    Returns 'None' if any step fails or no matching link is found.
    """
    years_to_try = [date.today().year, date.today().year - 1]
    release_menu_path: str | None = None
    for year in years_to_try:
        archive_response = requests.get(
            JP_CAO_YEAR_ARCHIVE_URL.format(year=year),
            timeout=60,
        )
        if archive_response.status_code >= 400:
            continue
        release_match = re.search(
            rf'href="(/en/sna/data/sokuhou/files/{year}/qe[^"]+/gdemenuea\.html)"',
            archive_response.text,
        )
        if release_match:
            release_menu_path = release_match.group(1)
            break
    if release_menu_path is None:
        return None

    menu_response = requests.get(
        urljoin(JP_CAO_SITE_ORIGIN, release_menu_path),
        timeout=60,
    )
    if menu_response.status_code >= 400:
        return None
    csv_match = re.search(
        rf'href="([^"]*{re.escape(csv_filename_prefix)}[^"]*\.csv)"',
        menu_response.text,
        flags=re.IGNORECASE,
    )
    if not csv_match:
        return None
    return urljoin(JP_CAO_SITE_ORIGIN, csv_match.group(1))


def _find_japan_cabinet_office_gross_debt_xlsx_url() -> str | None:
    """Return the download URL of the General Government Gross Debt workbook.

    Opens the SDDS Plus top page and finds the 'tables/ggd.xlsx' link
    (outstanding debt by quarter). Returns 'None' if the page or link is
    missing.
    """
    response = requests.get(
        JP_CAO_SDDS_PLUS_PAGE_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        return None
    match = re.search(
        r'href="(tables/ggd\.xlsx)"',
        response.text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return urljoin(JP_CAO_SDDS_PLUS_PAGE_URL, match.group(1))


class _ParsedCabinetOfficeQuarterLabel(NamedTuple):
    """Quarter start date and tracked year from a Cabinet Office period label."""

    period: date | None
    year: int | None


def _parse_japan_cabinet_office_quarter_label(
    period_label: str, current_year: int | None
) -> _ParsedCabinetOfficeQuarterLabel:
    """Parse a Cabinet Office quarter label, tracking year across table lines."""
    with_year = re.fullmatch(r"(\d{4})/\s*(\d{1,2})\s*-\s*(\d{1,2})\.?", period_label)
    if with_year:
        year = int(with_year.group(1))
        start_month = int(with_year.group(2))
        return _ParsedCabinetOfficeQuarterLabel(
            period=date(year, start_month, 1), year=year
        )
    without_year = re.fullmatch(r"(\d{1,2})\s*-\s*(\d{1,2})\.?", period_label)
    if without_year and current_year is not None:
        start_month = int(without_year.group(1))
        return _ParsedCabinetOfficeQuarterLabel(
            period=date(current_year, start_month, 1), year=current_year
        )
    return _ParsedCabinetOfficeQuarterLabel(period=None, year=current_year)


def _parse_japan_cabinet_office_levels_csv(
    csv_bytes: bytes, column_index: int
) -> list[ScrapingResult]:
    """Parse a Cabinet Office SNA levels CSV column into quarterly results."""
    dataframe = pd.read_csv(io.BytesIO(csv_bytes), encoding="cp932", header=None)
    if column_index >= dataframe.shape[1]:
        return []
    economic_data: list[ScrapingResult] = []
    current_year: int | None = None
    for row_index in range(len(dataframe)):
        period_cell = dataframe.iloc[row_index, 0]
        value_cell = dataframe.iloc[row_index, column_index]
        if pd.isna(period_cell) or pd.isna(value_cell):
            continue
        period_label = str(period_cell).strip()
        period, current_year = _parse_japan_cabinet_office_quarter_label(
            period_label, current_year
        )
        if period is None:
            continue
        raw_value = str(value_cell).strip().replace(",", "")
        try:
            data_value = float(raw_value)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min, reverse=True
    )
    return economic_data


def _parse_japan_cabinet_office_ggd_workbook(
    workbook_bytes: bytes,
) -> list[ScrapingResult]:
    """Parse SDDS Plus General Government Gross Debt (Total gross debt) levels."""
    workbook = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True)
    worksheet = workbook.active
    if worksheet is None:
        return []
    year_row = [cell.value for cell in worksheet[4]]
    month_row = [cell.value for cell in worksheet[5]]
    total_row = None
    for worksheet_cells in worksheet.iter_rows(
        min_row=6, max_row=worksheet.max_row, values_only=True
    ):
        label = worksheet_cells[0]
        if isinstance(label, str) and label.strip() == "Total gross debt":
            total_row = list(worksheet_cells)
            break
    if total_row is None:
        return []

    economic_data: list[ScrapingResult] = []
    for column_index in range(1, len(total_row)):
        year_value = year_row[column_index] if column_index < len(year_row) else None
        month_value = month_row[column_index] if column_index < len(month_row) else None
        debt_value = total_row[column_index]
        if not isinstance(year_value, int) or not isinstance(month_value, int):
            continue
        quarter_start_month = JP_CAO_GGD_QUARTER_START_MONTH_BY_END_MONTH.get(
            month_value
        )
        if quarter_start_month is None:
            continue
        if isinstance(debt_value, bool) or not isinstance(debt_value, (int, float)):
            continue
        economic_data.append(
            ScrapingResult(
                period=date(year_value, quarter_start_month, 1),
                data_value=float(debt_value),
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min, reverse=True
    )
    return economic_data


def _parse_japan_cabinet_office_ggo_period_label(period_label: str) -> date | None:
    """Parse an SDDS Plus GGO header like '2015Q1' into the quarter-start date."""
    quarter_match = re.fullmatch(r"(\d{4})Q([1-4])", period_label.strip())
    if quarter_match is None:
        return None
    year = int(quarter_match.group(1))
    quarter = int(quarter_match.group(2))
    return date(year, (quarter - 1) * 3 + 1, 1)


def _parse_japan_cabinet_office_ggo_workbook(
    workbook_bytes: bytes,
    row_label: str,
) -> list[ScrapingResult]:
    """Parse one General Government Operations row, skipping 'NA' cells.

    Period headers sit on row 4; the matching transaction label is in column A.
    Non-financial operations can lag the workbook's newest financial quarters.
    """
    workbook = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True)
    # First sheet is the SDDS Plus General Government Operations table.
    worksheet = workbook[workbook.sheetnames[0]]
    period_headers = list(
        next(worksheet.iter_rows(min_row=4, max_row=4, values_only=True))
    )
    value_row = None
    for worksheet_cells in worksheet.iter_rows(
        min_row=5, max_row=worksheet.max_row, values_only=True
    ):
        label = worksheet_cells[0]
        if isinstance(label, str) and label.strip() == row_label:
            value_row = list(worksheet_cells)
            break
    if value_row is None:
        return []

    economic_data: list[ScrapingResult] = []
    for column_index in range(1, len(value_row)):
        period_label = (
            period_headers[column_index] if column_index < len(period_headers) else None
        )
        if not isinstance(period_label, str):
            continue
        period = _parse_japan_cabinet_office_ggo_period_label(period_label)
        flow_value = value_row[column_index]
        if period is None:
            continue
        if isinstance(flow_value, bool) or not isinstance(flow_value, (int, float)):
            continue
        economic_data.append(
            ScrapingResult(
                period=period,
                data_value=float(flow_value),
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min, reverse=True
    )
    return economic_data


def _is_japan_cabinet_office_error_result(
    economic_data: list[ScrapingResult],
) -> bool:
    """Return True when 'economic_data' is a single unresolved error result."""
    # A failed scrape returns exactly one empty error result at index 0.
    return (
        len(economic_data) == 1
        and economic_data[0]["period"] is None
        and economic_data[0]["data_value"] is None
    )


def _download_japan_cabinet_office_csv(
    csv_filename_prefix: str,
) -> list[ScrapingResult]:
    """Download a quarterly-estimates CSV and parse column 1 (levels)."""
    csv_url = _find_japan_cabinet_office_quarterly_estimates_csv_url(
        csv_filename_prefix
    )
    if csv_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Could not find Japan Cabinet Office quarterly-estimates CSV "
                    f"URL for filename prefix {csv_filename_prefix}."
                ),
            )
        ]
    response = requests.get(
        csv_url,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Japan Cabinet Office CSV: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_levels_csv(response.content, column_index=1)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Error parsing Japan Cabinet Office CSV "
                    f"({csv_filename_prefix}): {exc}"
                ),
            )
        ]


def _download_japan_cabinet_office_real_sa_column(
    column_index: int,
) -> list[ScrapingResult]:
    """Download real SA expenditure CSV and parse one component column."""
    csv_url = _find_japan_cabinet_office_quarterly_estimates_csv_url(
        JP_CAO_REAL_SA_CSV_FILENAME_PREFIX
    )
    if csv_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Could not find Japan Cabinet Office real SA expenditure "
                    "CSV URL."
                ),
            )
        ]
    response = requests.get(
        csv_url,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Japan Cabinet Office GDP: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_levels_csv(
            response.content, column_index=column_index
        )
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing Japan Cabinet Office GDP CSV: {exc}",
            )
        ]


def _download_japan_cabinet_office_ggd_outstanding() -> list[ScrapingResult]:
    """Download SDDS Plus gross-debt Excel and parse Total gross debt."""
    xlsx_url = _find_japan_cabinet_office_gross_debt_xlsx_url()
    if xlsx_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Could not find Japan Cabinet Office General Government "
                    "Gross Debt Excel URL."
                ),
            )
        ]
    response = requests.get(
        xlsx_url,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Japan Cabinet Office GGD: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_ggd_workbook(response.content)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing Japan Cabinet Office GGD Excel: {exc}",
            )
        ]


def _download_japan_cabinet_office_ggo_row(row_label: str) -> list[ScrapingResult]:
    """Download the SDDS Plus GGO workbook and parse one transaction row."""
    response = requests.get(JP_CAO_GGO_XLSX_URL, timeout=60)
    if response.status_code >= 400:
        logger.warning(f"Error scraping Japan Cabinet Office GGO: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_ggo_workbook(response.content, row_label)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing Japan Cabinet Office GGO Excel: {exc}",
            )
        ]


def _parse_japan_cabinet_office_cofog_row_key(row_label: str) -> str | None:
    """Return 'Total' or the one-digit COFOG code for a top-level Table 7 label.

    Sub-function labels ('1.  1 Executive ...') keep a second code after the
    first dot, so only labels like '1.  General public services' match.
    """
    label = row_label.strip()
    if label == "Total":
        return label
    function_match = re.match(r"(\d{1,2})\.\s+[A-Za-z]", label)
    if function_match is None:
        return None
    return function_match.group(1)


def _parse_japan_cabinet_office_cofog_workbook(
    workbook_bytes: bytes,
    row_key: str,
) -> list[ScrapingResult]:
    """Parse one COFOG function's total outlays across every fiscal-year sheet.

    Total outlays sum final consumption, subsidies, social benefits, other
    current transfers, GFCF, changes in inventories, and capital transfers;
    the individual / collective consumption split is not added again. Fiscal
    years are stored on January 1 of the fiscal year's starting calendar year.
    """
    workbook = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True)
    economic_data: list[ScrapingResult] = []
    for worksheet in workbook.worksheets:
        fiscal_year = worksheet.cell(row=JP_CAO_COFOG_FISCAL_YEAR_ROW, column=2).value
        if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
            continue
        for worksheet_cells in worksheet.iter_rows(
            min_row=JP_CAO_COFOG_FIRST_DATA_ROW,
            max_row=worksheet.max_row,
            values_only=True,
        ):
            row_label = worksheet_cells[0]
            if not isinstance(row_label, str):
                continue
            if _parse_japan_cabinet_office_cofog_row_key(row_label) != row_key:
                continue
            outlay_values = [
                worksheet_cells[column_index]
                for column_index in JP_CAO_COFOG_OUTLAY_COLUMNS
                if column_index < len(worksheet_cells)
            ]
            numeric_outlay_values = [
                float(outlay_value)
                for outlay_value in outlay_values
                if isinstance(outlay_value, (int, float))
                and not isinstance(outlay_value, bool)
            ]
            if not numeric_outlay_values:
                break
            economic_data.append(
                ScrapingResult(
                    period=date(fiscal_year, 1, 1),
                    data_value=sum(numeric_outlay_values),
                    comment="",
                )
            )
            break
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min, reverse=True
    )
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _find_japan_cabinet_office_cofog_xlsx_url() -> str | None:
    """Return the newest Supporting Table 7 (COFOG) workbook URL that downloads.

    ESRI files each annual-estimates release under its release year, so this
    tries the current calendar year first and walks back through the lookback
    window. A GET is used because the server does not answer HEAD reliably.
    """
    current_year = date.today().year
    for release_year in range(
        current_year, current_year - JP_CAO_COFOG_URL_LOOKBACK_YEARS - 1, -1
    ):
        cofog_xlsx_url = JP_CAO_COFOG_XLSX_URL_TEMPLATE.format(year=release_year)
        try:
            response = requests.get(cofog_xlsx_url, timeout=60)
        except requests.RequestException as exc:
            logger.warning(f"Error probing Japan Cabinet Office COFOG URL: {exc}")
            continue
        if response.status_code != 200:
            continue
        content_type = response.headers.get("Content-Type", "")
        if (
            "spreadsheet" in content_type
            or len(response.content) >= JP_CAO_COFOG_MIN_XLSX_BYTES
        ):
            return cofog_xlsx_url
    return None


def _download_japan_cabinet_office_cofog(row_key: str) -> list[ScrapingResult]:
    """Download Supporting Table 7 (COFOG) and parse one function's outlays."""
    cofog_xlsx_url = _find_japan_cabinet_office_cofog_xlsx_url()
    if cofog_xlsx_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "No Japan Cabinet Office COFOG workbook found in the last "
                    f"{JP_CAO_COFOG_URL_LOOKBACK_YEARS} annual-estimates releases."
                ),
            )
        ]
    response = requests.get(cofog_xlsx_url, timeout=60)
    if response.status_code >= 400:
        logger.warning(f"Error scraping Japan Cabinet Office COFOG: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_cofog_workbook(response.content, row_key)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing Japan Cabinet Office COFOG Excel: {exc}",
            )
        ]


# Usage of tuple: fixed (release-folder year, workbook year, quarter) sort key.
def _get_kakei_workbook_path_sort_key(workbook_path: str) -> tuple[int, int, int]:
    """Return release-folder year, workbook year, and quarter for newest-first order."""
    match = re.fullmatch(
        r"(\d+)/tables/kakei_(\d+)q([1-4])\.xlsx",
        workbook_path,
        flags=re.IGNORECASE,
    )
    if match is None:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _find_japan_cabinet_office_kakei_xlsx_url() -> str | None:
    """Return the download URL of the latest household disposable-income workbook.

    Lists 'kakei_YYqN.xlsx' links on the Japanese files index and picks the
    newest year/quarter. Returns 'None' when the page or links are missing.
    """
    response = requests.get(
        JP_CAO_KAKEI_FILES_PAGE_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        return None
    workbook_paths = re.findall(
        r'href="(\d+/tables/kakei_\d+q[1-4]\.xlsx)"',
        response.text,
        flags=re.IGNORECASE,
    )
    if not workbook_paths:
        return None

    newest_path = max(workbook_paths, key=_get_kakei_workbook_path_sort_key)
    return urljoin(JP_CAO_KAKEI_FILES_ORIGIN, newest_path)


def _parse_japan_cabinet_office_kakei_workbook(
    workbook_bytes: bytes,
    column_index: int,
) -> list[ScrapingResult]:
    """Parse one SA column from the household disposable-income workbook."""
    workbook = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True)
    worksheet = next(
        (
            workbook[sheet_name]
            for sheet_name in workbook.sheetnames
            if JP_CAO_KAKEI_SA_SHEET_MARKER in sheet_name
        ),
        None,
    )
    if worksheet is None:
        return []

    economic_data: list[ScrapingResult] = []
    current_year: int | None = None
    for worksheet_cells in worksheet.iter_rows(
        min_row=9, max_row=worksheet.max_row, values_only=True
    ):
        period_label = worksheet_cells[0]
        if period_label is None:
            continue
        period, current_year = _parse_japan_cabinet_office_quarter_label(
            str(period_label).strip(), current_year
        )
        if period is None:
            continue
        # openpyxl rows are 0-based; config columns are 1-based Excel indexes.
        value_offset = column_index - 1
        if value_offset >= len(worksheet_cells):
            continue
        raw_value = worksheet_cells[value_offset]
        if not isinstance(raw_value, (int, float)):
            continue
        economic_data.append(
            ScrapingResult(
                period=period,
                data_value=float(raw_value),
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _download_japan_cabinet_office_kakei_column(
    column_index: int,
) -> list[ScrapingResult]:
    """Download the latest kakei workbook and parse one SA column."""
    xlsx_url = _find_japan_cabinet_office_kakei_xlsx_url()
    if xlsx_url is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Could not find Japan Cabinet Office household disposable "
                    "income Excel URL."
                ),
            )
        ]
    response = requests.get(
        xlsx_url,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Japan Cabinet Office kakei: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_kakei_workbook(
            response.content, column_index=column_index
        )
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Error parsing Japan Cabinet Office household disposable "
                    f"income Excel: {exc}"
                ),
            )
        ]


def _parse_japan_cabinet_office_shouhi_period(period_code: int | float) -> date | None:
    """Parse a Consumer Confidence Survey Excel period code into a month start."""
    period_digits = str(int(period_code))
    if len(period_digits) < 6:
        return None
    try:
        year = int(period_digits[:4])
        # Codes look like '2026101010' / '1982000606'; month is the last two digits.
        month = int(period_digits[-2:])
    except ValueError:
        return None
    if month < 1 or month > 12:
        return None
    return date(year, month, 1)


def _parse_japan_cabinet_office_shouhi_workbook(
    workbook_bytes: bytes,
    column_index: int,
) -> list[ScrapingResult]:
    """Parse one nationwide SA Consumer Confidence Survey column from shouhi2."""
    workbook = openpyxl.load_workbook(
        io.BytesIO(workbook_bytes), data_only=True, read_only=True
    )
    # First sheet is the seasonally adjusted Consumer Confidence Survey table.
    worksheet = workbook[workbook.sheetnames[0]]
    economic_data: list[ScrapingResult] = []
    for worksheet_cells in worksheet.iter_rows(
        min_row=7, max_col=column_index, values_only=True
    ):
        period_code = worksheet_cells[0]
        if isinstance(period_code, bool) or not isinstance(period_code, (int, float)):
            continue
        period = _parse_japan_cabinet_office_shouhi_period(period_code)
        value_cell = worksheet_cells[column_index - 1]
        if period is None or value_cell is None:
            continue
        if isinstance(value_cell, bool) or not isinstance(value_cell, (int, float)):
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=float(value_cell), comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _download_japan_cabinet_office_shouhi_column(
    column_index: int,
) -> list[ScrapingResult]:
    """Download the SA Consumer Confidence Survey Excel and parse one column."""
    response = requests.get(JP_CAO_SHOUHI_SA_XLSX_URL, timeout=60)
    if response.status_code >= 400:
        logger.warning(
            f"Error scraping Japan Cabinet Office shouhi survey: {response.text}"
        )
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]
    try:
        return _parse_japan_cabinet_office_shouhi_workbook(
            response.content, column_index
        )
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Error parsing Japan Cabinet Office shouhi survey Excel: " f"{exc}"
                ),
            )
        ]


def _scrape_japan_cabinet_office_machinery_orders_from_estat() -> list[ScrapingResult]:
    """Scrape private excl. volatile machinery orders (billion yen SA) from e-Stat."""
    payload = fetch_estat_stats_data(
        stats_data_id=JP_CAO_MACHINERY_ORDERS_STATS_DATA_ID,
        query_params={
            "cdCat01": JP_CAO_MACHINERY_ORDERS_DEMAND_CODE,
            "cdCat02": JP_CAO_MACHINERY_ORDERS_SA_SERIES_CODE,
        },
        log_label="CAO machinery orders",
    )
    if payload is None:
        return []
    economic_data: list[ScrapingResult] = []
    for raw_value in payload["values"]:
        time_code = str(raw_value.get("@time") or "").strip()
        amount_text = str(raw_value.get("$") or "").strip().replace(",", "")
        if not time_code or not amount_text:
            continue
        period = parse_estat_month_time_code(time_code)
        if period is None:
            continue
        try:
            million_yen = float(amount_text)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(
                period=period,
                data_value=million_yen
                / JP_CAO_MACHINERY_ORDERS_MILLION_YEN_PER_BILLION,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _filter_japan_cabinet_office_download_results(
    parsed: list[ScrapingResult],
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    empty_comment: str,
) -> list[ScrapingResult]:
    """Return filtered download scrape results or one error/empty result."""
    if _is_japan_cabinet_office_error_result(parsed):
        return parsed
    if not parsed:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=empty_comment,
            )
        ]
    return filter_scraping_results_by_target_period(parsed, target_period, frequency)


def _scrape_japan_cabinet_office_cofog_outlays_for_ticker(
    ticker: str,
    cofog_row_key: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape Supporting Table 7 COFOG outlays for one mapped ticker."""
    if frequency != EconomicPublicationFrequencyChoices.ANNUAL:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for Japan Cabinet Office COFOG "
                    f"scrape: {frequency}"
                ),
            )
        ]
    parsed = _download_japan_cabinet_office_cofog(cofog_row_key)
    return _filter_japan_cabinet_office_download_results(
        parsed,
        target_period,
        frequency,
        ("No Japan Cabinet Office COFOG outlay values found for " f"{ticker}."),
    )


def _scrape_japan_cabinet_office_shouhi_survey_for_ticker(
    shouhi_column: int,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape one Consumer Confidence Survey SA column for a mapped ticker."""
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for Japan Cabinet Office scrape: "
                    f"{frequency}"
                ),
            )
        ]
    parsed = _download_japan_cabinet_office_shouhi_column(shouhi_column)
    return _filter_japan_cabinet_office_download_results(
        parsed,
        target_period,
        frequency,
        "No Japan Cabinet Office Consumer Confidence Survey values found.",
    )


def _scrape_japan_cabinet_office_machinery_orders_for_ticker(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape private machinery orders (excl. volatile) from e-Stat."""
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for Japan Cabinet Office scrape: "
                    f"{frequency}"
                ),
            )
        ]
    parsed = _scrape_japan_cabinet_office_machinery_orders_from_estat()
    if not parsed:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Japan Cabinet Office Machinery Orders values found.",
            )
        ]
    return filter_scraping_results_by_target_period(parsed, target_period, frequency)


def _scrape_japan_cabinet_office_household_saving_ratio_for_ticker(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Compute household saving ratio from kakei saving and disposable income."""
    saving_amount_series = get_data_from_japan_cabinet_office(
        JP_CAO_NOMINAL_HH_SAVING_TICKER, target_period, frequency
    )
    disposable_income_series = get_data_from_japan_cabinet_office(
        JP_CAO_NOMINAL_HH_DI_TICKER, target_period, frequency
    )
    saving_ratio_series = calculate_ratio_scraping_results_as_percent(
        saving_amount_series, disposable_income_series
    )
    if not saving_ratio_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Japan Cabinet Office household saving-ratio values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        saving_ratio_series, target_period, frequency
    )


def _scrape_japan_cabinet_office_ggo_other_revenue_for_ticker(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Compute GGO other revenue as total revenue minus taxes and contributions."""
    other_revenue_series = get_data_from_japan_cabinet_office(
        JP_CAO_GGO_REVENUE_TICKER, target_period, frequency
    )
    # Subtract one input at a time so only periods present in every input stay.
    for revenue_component_ticker in [
        JP_CAO_GGO_TAXES_TICKER,
        JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER,
    ]:
        other_revenue_series = subtract_scraping_results_by_period(
            other_revenue_series,
            get_data_from_japan_cabinet_office(
                revenue_component_ticker, target_period, frequency
            ),
        )
    if not other_revenue_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Japan Cabinet Office GGO other-revenue values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        other_revenue_series, target_period, frequency
    )


def _scrape_japan_cabinet_office_ggo_financing_account_for_ticker(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Compute GGO financing account as net liabilities minus net financial assets."""
    financing_account_series = subtract_scraping_results_by_period(
        get_data_from_japan_cabinet_office(
            JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER,
            target_period,
            frequency,
        ),
        get_data_from_japan_cabinet_office(
            JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER,
            target_period,
            frequency,
        ),
    )
    if not financing_account_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Japan Cabinet Office GGO financing-account values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        financing_account_series, target_period, frequency
    )


def _scrape_japan_cabinet_office_household_consumption_ratio_for_ticker(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Compute household consumption ratio from kakei spend and disposable income."""
    consumption_amount_series = get_data_from_japan_cabinet_office(
        JP_CAO_NOMINAL_HH_CONSUMPTION_TICKER, target_period, frequency
    )
    disposable_income_series = get_data_from_japan_cabinet_office(
        JP_CAO_NOMINAL_HH_DI_TICKER, target_period, frequency
    )
    consumption_ratio_series = calculate_ratio_scraping_results_as_percent(
        consumption_amount_series, disposable_income_series
    )
    if not consumption_ratio_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "No Japan Cabinet Office household consumption-ratio "
                    "values found."
                ),
            )
        ]
    return filter_scraping_results_by_target_period(
        consumption_ratio_series, target_period, frequency
    )


def _scrape_japan_cabinet_office_quarterly_series_for_ticker(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Download and filter one quarterly SNA / SDDS Plus / kakei series."""
    real_sa_column = JP_CAO_REAL_SA_COLUMN_BY_TICKER.get(ticker)
    kakei_column = JP_CAO_KAKEI_COLUMN_BY_TICKER.get(ticker)
    if real_sa_column is not None:
        parsed = _download_japan_cabinet_office_real_sa_column(real_sa_column)
    elif kakei_column is not None:
        parsed = _download_japan_cabinet_office_kakei_column(kakei_column)
    elif ticker == JP_CAO_NOMINAL_GDP_TICKER:
        parsed = _download_japan_cabinet_office_csv(
            JP_CAO_NOMINAL_SA_CSV_FILENAME_PREFIX
        )
    elif ticker == JP_CAO_DEBT_OUTSTANDING_TICKER:
        parsed = _download_japan_cabinet_office_ggd_outstanding()
    elif ticker in JP_CAO_GGO_TICKERS:
        parsed = _download_japan_cabinet_office_ggo_row(
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[ticker]
        )
    else:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported JP_CABINET_OFFICE ticker: {ticker}",
            )
        ]
    return _filter_japan_cabinet_office_download_results(
        parsed,
        target_period,
        frequency,
        "No Japan Cabinet Office values found.",
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_japan_cabinet_office(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.QUARTERLY,
) -> list[ScrapingResult]:
    """Scrape one Cabinet Office ESRI series and optionally filter to 'target_period'."""
    cofog_row_key = JP_CAO_COFOG_ROW_KEY_BY_TICKER.get(ticker)
    if cofog_row_key is not None:
        return _scrape_japan_cabinet_office_cofog_outlays_for_ticker(
            ticker, cofog_row_key, target_period, frequency
        )

    shouhi_column = JP_CAO_SHOUHI_COLUMN_BY_TICKER.get(ticker)
    if shouhi_column is not None:
        return _scrape_japan_cabinet_office_shouhi_survey_for_ticker(
            shouhi_column, target_period, frequency
        )

    if ticker == JP_CAO_MACHINERY_ORDERS_TICKER:
        return _scrape_japan_cabinet_office_machinery_orders_for_ticker(
            target_period, frequency
        )

    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for Japan Cabinet Office scrape: "
                    f"{frequency}"
                ),
            )
        ]

    if ticker == JP_CAO_HH_SAVING_RATIO_TICKER:
        return _scrape_japan_cabinet_office_household_saving_ratio_for_ticker(
            target_period, frequency
        )
    if ticker == JP_CAO_GGO_OTHER_REVENUE_TICKER:
        return _scrape_japan_cabinet_office_ggo_other_revenue_for_ticker(
            target_period, frequency
        )
    if ticker == JP_CAO_GGO_FINANCING_ACCOUNT_TICKER:
        return _scrape_japan_cabinet_office_ggo_financing_account_for_ticker(
            target_period, frequency
        )
    if ticker == JP_CAO_HH_CONSUMPTION_RATIO_TICKER:
        return _scrape_japan_cabinet_office_household_consumption_ratio_for_ticker(
            target_period, frequency
        )

    return _scrape_japan_cabinet_office_quarterly_series_for_ticker(
        ticker, target_period, frequency
    )


# __________________________________________________________
# Publication dates (Cabinet Office calendars)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_japan_cabinet_office(name: str) -> list[datetime]:
    """Get upcoming Cabinet Office dates from the e-Stat release calendar.

    GDP flash, machinery orders, and consumer confidence are listed there.
    SDDS Plus GGO / GGD / COFOG and annual SNA tables have no dated e-Stat
    slots in the lookahead window, so those names still return empty.
    """
    return get_publication_dates_from_estat_for_technical_name(name)


# __________________________________________________________
# Industry profitability (ESRI GVA by economic activity)
# __________________________________________________________


class _EsriIndustryColumn(NamedTuple):
    """One leaf economic-activity column in the ESRI GVA CSV."""

    column_index: int
    industry_code: str
    industry_label: str


class _EsriQuarterAmount(TypedDict):
    """One quarter amount for a leaf industry while annualizing."""

    industry_code: str
    industry_label: str
    year: int
    quarter: int
    amount_million_yen: float


def _strip_esri_industry_label(raw_label: str) -> str:
    """Drop leading '1.' / '(1)' numbering from ESRI English industry labels."""
    cleaned_label = raw_label.strip()
    cleaned_label = re.sub(r"^\(\d+\)\s*", "", cleaned_label)
    cleaned_label = re.sub(r"^\d+\.\s*", "", cleaned_label)
    return cleaned_label.strip()


def _get_latest_seisanqna_release_path(top_html: str) -> str | None:
    """Pick the newest seisanqna_YYYYqN.html path from the top page."""
    newest_path: str | None = None
    newest_sort_key = (-1, -1)
    for match in _SEISANQNA_RELEASE_HREF_RE.finditer(top_html):
        release_path = match.group(1)
        year = int(match.group(2))
        quarter = int(match.group(3))
        sort_key = (year, quarter)
        if sort_key > newest_sort_key:
            newest_sort_key = sort_key
            newest_path = release_path
    return newest_path


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_nominal_original_gva_csv_url() -> str | None:
    """Resolve the latest 名目原系列 value-added levels CSV URL from ESRI."""
    try:
        top_response = requests.get(JP_CAO_SEISANQNA_TOP_URL, timeout=60)
        top_response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("ESRI seisanqna top page fetch failed: %s", exc)
        return None
    release_path = _get_latest_seisanqna_release_path(top_response.text)
    if release_path is None:
        logger.warning("ESRI seisanqna release page link not found on top page.")
        return None
    release_url = f"{JP_CAO_SITE_ORIGIN}{release_path}"
    try:
        release_response = requests.get(release_url, timeout=60)
        release_response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("ESRI seisanqna release page fetch failed: %s", exc)
        return None
    csv_match = _NOMINAL_ORIGINAL_GVA_CSV_HREF_RE.search(release_response.text)
    if csv_match is None:
        logger.warning(
            "ESRI nominal original GVA CSV link not found on %s", release_url
        )
        return None
    return f"{JP_CAO_SITE_ORIGIN}{csv_match.group(1)}"


def _decode_esri_csv_text(raw_bytes: bytes) -> str:
    """Decode ESRI CSV bytes, preferring Shift_JIS then UTF-8."""
    for encoding in ("cp932", "utf-8-sig", "utf-8"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1")


def _build_esri_industry_columns(rows: list[list[str]]) -> list[_EsriIndustryColumn]:
    """Build leaf industry columns from the English label header rows."""
    if len(rows) < 10:
        return []
    # Row 7 holds top-level English labels; row 9 holds manufacturing sub-labels.
    # Data body columns sit to the right of those label cells (year/quarter stubs),
    # so label lookup uses a smaller index than the amount column.
    top_level_labels = rows[7]
    manufacturing_labels = rows[9]
    industry_columns: list[_EsriIndustryColumn] = []
    for column_index, industry_code in _ESRI_LEAF_INDUSTRY_COLUMNS:
        raw_label = ""
        if industry_code.startswith("3."):
            label_column_index = column_index - 2
            if 0 <= label_column_index < len(manufacturing_labels):
                raw_label = manufacturing_labels[label_column_index]
        else:
            label_column_index = column_index - 1
            if 0 <= label_column_index < len(top_level_labels):
                raw_label = top_level_labels[label_column_index]
        industry_label = _strip_esri_industry_label(raw_label) or industry_code
        industry_columns.append(
            _EsriIndustryColumn(
                column_index=column_index,
                industry_code=industry_code,
                industry_label=industry_label,
            )
        )
    return industry_columns


def _parse_quarter_number(quarter_token: str) -> int | None:
    """Parse quarter markers such as '2023Q1', 'Ⅰ', or '1' into 1–4."""
    cleaned = quarter_token.strip().upper()
    match = re.search(r"Q([1-4])$", cleaned)
    if match:
        return int(match.group(1))
    roman_quarters = {
        "Ⅰ": 1,
        "Ⅱ": 2,
        "Ⅲ": 3,
        "Ⅳ": 4,
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
    }
    if cleaned in roman_quarters:
        return roman_quarters[cleaned]
    if cleaned.isdigit() and 1 <= int(cleaned) <= 4:
        return int(cleaned)
    return None


def _parse_quarter_amounts(
    rows: list[list[str]],
    industry_columns: list[_EsriIndustryColumn],
) -> list[_EsriQuarterAmount]:
    """Parse quarterly leaf-industry amounts from the ESRI GVA CSV body."""
    quarter_amounts: list[_EsriQuarterAmount] = []
    for row in rows[10:]:
        if len(row) < 3:
            continue
        year_token = row[0].strip()
        if not year_token.isdigit():
            continue
        year = int(year_token)
        if year < INDUSTRY_PROFITABILITY_START_YEAR:
            continue
        quarter = _parse_quarter_number(row[2]) or _parse_quarter_number(row[1])
        if quarter is None:
            continue
        for industry_column in industry_columns:
            if industry_column.column_index >= len(row):
                continue
            raw_amount = row[industry_column.column_index].strip().replace(",", "")
            if not raw_amount or raw_amount in {"***", "-"}:
                continue
            try:
                amount_ten_oku_yen = float(raw_amount)
            except ValueError:
                continue
            quarter_amounts.append(
                _EsriQuarterAmount(
                    industry_code=industry_column.industry_code,
                    industry_label=industry_column.industry_label,
                    year=year,
                    quarter=quarter,
                    amount_million_yen=(
                        amount_ten_oku_yen * ESRI_GVA_TEN_OKU_YEN_TO_MILLION
                    ),
                )
            )
    return quarter_amounts


def _annualize_quarter_amounts(
    quarter_amounts: list[_EsriQuarterAmount],
) -> list[ScrapedIndustryProfitability]:
    """Sum four complete calendar quarters into annual GVA figures."""
    # Usage of dict: industry|year → quarter → million-yen amount.
    amounts_by_industry_year: dict[str, dict[int, float]] = {}
    # Usage of dict: industry|year → display label.
    labels_by_industry_year: dict[str, str] = {}
    for quarter_amount in quarter_amounts:
        merge_key = f"{quarter_amount['industry_code']}|{quarter_amount['year']}"
        quarter_map = amounts_by_industry_year.setdefault(merge_key, {})
        quarter_map[quarter_amount["quarter"]] = quarter_amount["amount_million_yen"]
        labels_by_industry_year[merge_key] = quarter_amount["industry_label"]

    scraped_industry_profitabilities: list[ScrapedIndustryProfitability] = []
    for merge_key, quarter_map in amounts_by_industry_year.items():
        if set(quarter_map) != {1, 2, 3, 4}:
            continue
        industry_code, year_label = merge_key.split("|", 1)
        annual_gva = sum(quarter_map[quarter] for quarter in (1, 2, 3, 4))
        scraped_industry_profitabilities.append(
            ScrapedIndustryProfitability(
                industry_code=industry_code,
                industry_label=labels_by_industry_year[merge_key],
                period=date(int(year_label), 1, 1),
                turnover=None,
                operating_profit=None,
                gva=annual_gva,
            )
        )
    return scraped_industry_profitabilities


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_industry_gva_from_esri() -> list[ScrapedIndustryProfitability]:
    """Scrape JP ESRI calendar-year nominal GVA by economic activity (million yen)."""
    csv_url = _get_nominal_original_gva_csv_url()
    if csv_url is None:
        return []
    try:
        response = requests.get(csv_url, timeout=120)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("ESRI GVA CSV fetch failed url=%s: %s", csv_url, exc)
        return []
    csv_text = _decode_esri_csv_text(response.content)
    rows = list(csv.reader(csv_text.splitlines()))
    industry_columns = _build_esri_industry_columns(rows)
    if not industry_columns:
        logger.warning("ESRI GVA CSV industry header rows were not parsed.")
        return []
    return _annualize_quarter_amounts(_parse_quarter_amounts(rows, industry_columns))
