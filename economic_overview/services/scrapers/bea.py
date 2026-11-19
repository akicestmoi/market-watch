"""Scrape BEA NIPA government spending and US GDP-by-industry profitability."""

import logging
from datetime import date, datetime
from typing import NamedTuple, TypedDict

import requests
from cachetools.func import ttl_cache
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    BEA_API_DATA_URL,
    BEA_GDP_BY_INDUSTRY_DATASET,
    BEA_GDP_BY_INDUSTRY_EXCLUDED_CODES,
    BEA_GDP_BY_INDUSTRY_GO_TABLE_ID,
    BEA_GDP_BY_INDUSTRY_GOS_COMPONENT,
    BEA_GDP_BY_INDUSTRY_GOS_TABLE_ID,
    BEA_GDP_BY_INDUSTRY_VA_TABLE_ID,
    BEA_GOVERNMENT_EXPENDITURES_BY_FUNCTION_TABLE_NAME,
    BEA_GOVERNMENT_EXPENDITURES_LINE_BY_TICKER,
    BEA_NIPA_ANNUAL_FREQUENCY,
    BEA_NIPA_ANNUAL_YEAR,
    BEA_NIPA_DATASET,
    BEA_NIPA_MILLIONS_TO_BILLIONS,
    INDUSTRY_PROFITABILITY_START_YEAR,
)
from economic_overview.services.scrapers.common import (
    ScrapedIndustryProfitability,
    ScrapingResult,
    filter_scraping_results_by_target_period,
)
from economic_overview.services.scrapers.fred import get_publication_dates_from_fred

logger = logging.getLogger(__name__)

# __________________________________________________________
# Government expenditures by function (BEA national accounts Table 3.16)
# __________________________________________________________


class _BeaNipaObservation(TypedDict, total=False):
    """One BEA NIPA GetData observation."""

    LineNumber: str
    TimePeriod: str
    DataValue: str


class _BeaNipaGetDataResults(TypedDict, total=False):
    """BEA NIPA GetData Results block."""

    Data: list[_BeaNipaObservation]


class _BeaNipaApiEnvelope(TypedDict, total=False):
    """Outer BEAAPI JSON envelope for NIPA tables."""

    Results: _BeaNipaGetDataResults | list[_BeaNipaGetDataResults]


class _BeaNipaApiPayload(TypedDict, total=False):
    """Top-level BEA NIPA JSON response."""

    BEAAPI: _BeaNipaApiEnvelope


_BEA_NIPA_API_PAYLOAD_ADAPTER = TypeAdapter(_BeaNipaApiPayload)


def _unwrap_bea_nipa_results_block(
    results: _BeaNipaGetDataResults | list[_BeaNipaGetDataResults],
) -> _BeaNipaGetDataResults:
    """Normalize BEA NIPA Results that may arrive as a one-element list."""
    if isinstance(results, list):
        # BEA sometimes wraps Results in a single-element list.
        return results[0] if results else _BeaNipaGetDataResults()
    return results


def _parse_bea_nipa_annual_line(
    observations: list[_BeaNipaObservation],
    line_number: str,
) -> list[ScrapingResult]:
    """Parse one NIPA table line into newest-first annual billions (Jan 1 periods)."""
    economic_data: list[ScrapingResult] = []
    for observation in observations:
        if (observation.get("LineNumber") or "").strip() != line_number:
            continue
        year_label = (observation.get("TimePeriod") or "").strip()
        raw_value = (observation.get("DataValue") or "").strip().replace(",", "")
        if not year_label.isdigit() or not raw_value:
            continue
        try:
            data_value = float(raw_value) * BEA_NIPA_MILLIONS_TO_BILLIONS
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(
                period=date(int(year_label), 1, 1),
                data_value=data_value,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


class _BeaNipaTableDownload(NamedTuple):
    """Downloaded NIPA table observations, or the error comment when it failed."""

    observations: list[_BeaNipaObservation]
    error_comment: str


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _download_bea_government_expenditures_by_function() -> _BeaNipaTableDownload:
    """Download BEA NIPA Table 3.16 (annual, every line) once per cache window."""
    api_key = (getattr(settings, "BEA_API_KEY", None) or "").strip()
    if not api_key:
        return _BeaNipaTableDownload(
            observations=[], error_comment="BEA_API_KEY is not configured."
        )
    response = requests.get(
        BEA_API_DATA_URL,
        params={
            "UserID": api_key,
            "method": "GetData",
            "datasetname": BEA_NIPA_DATASET,
            "TableName": BEA_GOVERNMENT_EXPENDITURES_BY_FUNCTION_TABLE_NAME,
            "Frequency": BEA_NIPA_ANNUAL_FREQUENCY,
            "Year": BEA_NIPA_ANNUAL_YEAR,
            "ResultFormat": "JSON",
        },
        timeout=90,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping BEA NIPA T31600: {response.text[:500]}")
        return _BeaNipaTableDownload(observations=[], error_comment=response.text)
    try:
        payload = _BEA_NIPA_API_PAYLOAD_ADAPTER.validate_python(response.json())
    except (ValidationError, ValueError) as exc:
        return _BeaNipaTableDownload(
            observations=[], error_comment=f"Error parsing BEA NIPA JSON: {exc}"
        )
    bea_api = payload.get("BEAAPI") or {}
    results_block = _unwrap_bea_nipa_results_block(
        bea_api.get("Results") or _BeaNipaGetDataResults()
    )
    return _BeaNipaTableDownload(
        observations=results_block.get("Data") or [], error_comment=""
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_bea(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.QUARTERLY,
) -> list[ScrapingResult]:
    """Get a BEA series by seed ticker.

    'bea_t31600_*' tickers are NIPA Table 3.16 government current expenditures
    by function (annual, millions stored as billions).
    """
    expenditures_line_number = BEA_GOVERNMENT_EXPENDITURES_LINE_BY_TICKER.get(ticker)
    if expenditures_line_number is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported BEA ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.ANNUAL:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for BEA NIPA scrape: {frequency}",
            )
        ]
    table_download = _download_bea_government_expenditures_by_function()
    if table_download.error_comment:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=table_download.error_comment,
            )
        ]
    economic_data = _parse_bea_nipa_annual_line(
        table_download.observations, expenditures_line_number
    )
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "No BEA NIPA T31600 values for "
                    f"LineNumber={expenditures_line_number}."
                ),
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (government expenditures via FRED GDP calendar)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_bea(name: str) -> list[datetime]:
    """Get BEA publication dates.

    NIPA Table 3.16 shares the BEA quarterly GDP release family; use the FRED
    GDP calendar (release 53), which carries the official 08:30 ET clock.
    """
    if name.startswith("Government current expenditures by function"):
        return get_publication_dates_from_fred("Gross Domestic Product")
    logger.warning(f"No BEA publication calendar mapping for technical_name={name}")
    return []


# __________________________________________________________
# Industry profitability (GDP-by-industry output, surplus, and value added)
# __________________________________________________________


class _BeaGdpByIndustryObservation(TypedDict, total=False):
    """One BEA GDPbyIndustry GetData observation."""

    Industry: str
    IndustrYDescription: str
    Year: str
    DataValue: str


class _BeaGdpByIndustryGetDataResults(TypedDict, total=False):
    """BEA GDPbyIndustry GetData Results block."""

    Data: list[_BeaGdpByIndustryObservation]


class _BeaGdpByIndustryApiEnvelope(TypedDict, total=False):
    """Outer BEAAPI JSON envelope for GDPbyIndustry tables."""

    Results: _BeaGdpByIndustryGetDataResults | list[_BeaGdpByIndustryGetDataResults]


class _BeaGdpByIndustryApiPayload(TypedDict, total=False):
    """Top-level BEA GDPbyIndustry JSON response."""

    BEAAPI: _BeaGdpByIndustryApiEnvelope


class _BeaIndustryParamValue(TypedDict, total=False):
    """One BEA GetParameterValues industry entry."""

    Key: str
    Desc: str


class _BeaIndustryParamResults(TypedDict, total=False):
    """BEA GetParameterValues Results block for Industry."""

    ParamValue: list[_BeaIndustryParamValue]


class _BeaIndustryParamEnvelope(TypedDict, total=False):
    """Outer BEAAPI envelope for Industry parameter values."""

    Results: _BeaIndustryParamResults | list[_BeaIndustryParamResults]


class _BeaIndustryParamPayload(TypedDict, total=False):
    """Top-level BEA Industry parameter-values response."""

    BEAAPI: _BeaIndustryParamEnvelope


class _BeaMergedIndustryMetrics(TypedDict):
    """Merged GO / GOS / VA values for one industry-year."""

    industry_code: str
    industry_label: str
    year: int
    turnover: float | None
    operating_profit: float | None
    gva: float | None


_BEA_GDP_BY_INDUSTRY_ADAPTER = TypeAdapter(_BeaGdpByIndustryApiPayload)
_BEA_INDUSTRY_PARAM_ADAPTER = TypeAdapter(_BeaIndustryParamPayload)


def _unwrap_bea_gdp_by_industry_results_block(
    results: _BeaGdpByIndustryGetDataResults | list[_BeaGdpByIndustryGetDataResults],
) -> _BeaGdpByIndustryGetDataResults:
    """Normalize GDPbyIndustry Results that may arrive as a one-element list."""
    if isinstance(results, list):
        # BEA sometimes wraps Results in a single-element list.
        return results[0] if results else _BeaGdpByIndustryGetDataResults()
    return results


def _unwrap_bea_industry_param_results_block(
    results: _BeaIndustryParamResults | list[_BeaIndustryParamResults],
) -> _BeaIndustryParamResults:
    """Normalize Industry parameter Results that may arrive as a one-element list."""
    if isinstance(results, list):
        # BEA sometimes wraps Results in a single-element list.
        return results[0] if results else _BeaIndustryParamResults()
    return results


def _clean_bea_industry_label(raw_label: str) -> str:
    """Strip BEA frequency suffixes such as '(A,Q)' from industry labels."""
    cleaned_label = raw_label.strip()
    if cleaned_label.endswith(")"):
        open_paren = cleaned_label.rfind(" (")
        if open_paren > 0:
            return cleaned_label[:open_paren].strip()
    return cleaned_label


def _format_industry_year_key(industry_code: str, year: int) -> str:
    """Stable string key for one industry-year merge bucket."""
    return f"{industry_code}|{year}"


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _fetch_bea_industry_labels() -> dict[str, str]:
    """Map BEA industry codes to display labels from GetParameterValues."""
    api_key = (getattr(settings, "BEA_API_KEY", None) or "").strip()
    if not api_key:
        return {}
    try:
        response = requests.get(
            BEA_API_DATA_URL,
            params={
                "UserID": api_key,
                "method": "GetParameterValues",
                "DataSetName": BEA_GDP_BY_INDUSTRY_DATASET,
                "ParameterName": "Industry",
                "ResultFormat": "JSON",
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = _BEA_INDUSTRY_PARAM_ADAPTER.validate_python(response.json())
    except (requests.RequestException, ValidationError, ValueError) as exc:
        logger.warning("BEA industry label fetch failed: %s", exc)
        return {}
    envelope = payload.get("BEAAPI") or _BeaIndustryParamEnvelope()
    results = _unwrap_bea_industry_param_results_block(
        envelope.get("Results") or _BeaIndustryParamResults()
    )
    # Usage of dict: BEA industry code → cleaned display label.
    labels_by_code: dict[str, str] = {}
    for param_value in results.get("ParamValue") or []:
        industry_code = (param_value.get("Key") or "").strip()
        industry_label = _clean_bea_industry_label(param_value.get("Desc") or "")
        if industry_code and industry_label:
            labels_by_code[industry_code] = industry_label
    return labels_by_code


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _fetch_bea_table_observations(table_id: str) -> list[_BeaGdpByIndustryObservation]:
    """Download annual GDPbyIndustry rows for one table across all industries."""
    api_key = (getattr(settings, "BEA_API_KEY", None) or "").strip()
    if not api_key:
        logger.warning("BEA_API_KEY is empty; skipping GDP-by-industry scrape.")
        return []
    try:
        response = requests.get(
            BEA_API_DATA_URL,
            params={
                "UserID": api_key,
                "method": "GetData",
                "DataSetName": BEA_GDP_BY_INDUSTRY_DATASET,
                "TableID": table_id,
                "Frequency": "A",
                "Year": "ALL",
                "Industry": "ALL",
                "ResultFormat": "JSON",
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = _BEA_GDP_BY_INDUSTRY_ADAPTER.validate_python(response.json())
    except (requests.RequestException, ValidationError, ValueError) as exc:
        logger.warning(
            "BEA GDP-by-industry fetch failed table_id=%s: %s", table_id, exc
        )
        return []
    envelope = payload.get("BEAAPI") or _BeaGdpByIndustryApiEnvelope()
    results = _unwrap_bea_gdp_by_industry_results_block(
        envelope.get("Results") or _BeaGdpByIndustryGetDataResults()
    )
    return results.get("Data") or []


class _BeaIndustryObservationAmount(NamedTuple):
    """Parsed industry code, year, and amount from one GDPbyIndustry observation."""

    industry_code: str
    year: int
    amount: float


def _parse_bea_observation_amount(
    observation: _BeaGdpByIndustryObservation,
) -> _BeaIndustryObservationAmount | None:
    """Return industry code, year, and amount when the observation is usable."""
    industry_code = (observation.get("Industry") or "").strip()
    if not industry_code or industry_code in BEA_GDP_BY_INDUSTRY_EXCLUDED_CODES:
        return None
    year_label = (observation.get("Year") or "").strip()
    raw_value = (observation.get("DataValue") or "").strip().replace(",", "")
    if not year_label.isdigit() or not raw_value:
        return None
    year = int(year_label)
    if year < INDUSTRY_PROFITABILITY_START_YEAR:
        return None
    try:
        amount = float(raw_value)
    except ValueError:
        return None
    return _BeaIndustryObservationAmount(
        industry_code=industry_code, year=year, amount=amount
    )


def _ensure_merged_metrics(
    metrics_by_key: dict[str, _BeaMergedIndustryMetrics],
    *,
    industry_code: str,
    year: int,
    industry_label: str,
) -> _BeaMergedIndustryMetrics:
    """Get or create the merge bucket for one industry-year."""
    merge_key = _format_industry_year_key(industry_code, year)
    existing = metrics_by_key.get(merge_key)
    if existing is not None:
        return existing
    created = _BeaMergedIndustryMetrics(
        industry_code=industry_code,
        industry_label=industry_label,
        year=year,
        turnover=None,
        operating_profit=None,
        gva=None,
    )
    metrics_by_key[merge_key] = created
    return created


def _merge_bea_gross_output_observations(
    metrics_by_key: dict[str, _BeaMergedIndustryMetrics],
    labels_by_code: dict[str, str],
) -> None:
    """Merge gross-output observations into industry-year metrics."""
    for observation in _fetch_bea_table_observations(BEA_GDP_BY_INDUSTRY_GO_TABLE_ID):
        parsed = _parse_bea_observation_amount(observation)
        if parsed is None:
            continue
        industry_label = labels_by_code.get(
            parsed.industry_code,
            _clean_bea_industry_label(observation.get("IndustrYDescription") or "")
            or parsed.industry_code,
        )
        merged = _ensure_merged_metrics(
            metrics_by_key,
            industry_code=parsed.industry_code,
            year=parsed.year,
            industry_label=industry_label,
        )
        merged["turnover"] = parsed.amount


def _merge_bea_gos_observations(
    metrics_by_key: dict[str, _BeaMergedIndustryMetrics],
    labels_by_code: dict[str, str],
) -> None:
    """Merge gross operating surplus observations into industry-year metrics."""
    for observation in _fetch_bea_table_observations(BEA_GDP_BY_INDUSTRY_GOS_TABLE_ID):
        if (
            observation.get("IndustrYDescription") or ""
        ).strip() != BEA_GDP_BY_INDUSTRY_GOS_COMPONENT:
            continue
        parsed = _parse_bea_observation_amount(observation)
        if parsed is None:
            continue
        industry_label = labels_by_code.get(parsed.industry_code, parsed.industry_code)
        merged = _ensure_merged_metrics(
            metrics_by_key,
            industry_code=parsed.industry_code,
            year=parsed.year,
            industry_label=industry_label,
        )
        merged["operating_profit"] = parsed.amount


def _merge_bea_value_added_observations(
    metrics_by_key: dict[str, _BeaMergedIndustryMetrics],
    labels_by_code: dict[str, str],
) -> None:
    """Merge value-added observations into industry-year metrics."""
    for observation in _fetch_bea_table_observations(BEA_GDP_BY_INDUSTRY_VA_TABLE_ID):
        parsed = _parse_bea_observation_amount(observation)
        if parsed is None:
            continue
        industry_label = labels_by_code.get(
            parsed.industry_code,
            _clean_bea_industry_label(observation.get("IndustrYDescription") or "")
            or parsed.industry_code,
        )
        merged = _ensure_merged_metrics(
            metrics_by_key,
            industry_code=parsed.industry_code,
            year=parsed.year,
            industry_label=industry_label,
        )
        merged["gva"] = parsed.amount


def _format_bea_scraped_industry_profitabilities(
    metrics_by_key: dict[str, _BeaMergedIndustryMetrics],
) -> list[ScrapedIndustryProfitability]:
    """Format merged BEA industry metrics into scraped industry profitabilities."""
    return [
        ScrapedIndustryProfitability(
            industry_code=merged["industry_code"],
            industry_label=merged["industry_label"],
            period=date(merged["year"], 1, 1),
            turnover=merged["turnover"],
            operating_profit=merged["operating_profit"],
            gva=merged["gva"],
        )
        for merged in metrics_by_key.values()
    ]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_industry_profitability_from_bea() -> list[ScrapedIndustryProfitability]:
    """Scrape US finest published BEA industry GO, GOS, and value added."""
    labels_by_code = _fetch_bea_industry_labels()
    # Usage of dict: industry|year → merged GO / GOS / VA metrics.
    metrics_by_key: dict[str, _BeaMergedIndustryMetrics] = {}
    _merge_bea_gross_output_observations(metrics_by_key, labels_by_code)
    _merge_bea_gos_observations(metrics_by_key, labels_by_code)
    _merge_bea_value_added_observations(metrics_by_key, labels_by_code)
    return _format_bea_scraped_industry_profitabilities(metrics_by_key)
