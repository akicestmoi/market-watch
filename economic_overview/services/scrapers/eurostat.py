"""Scrape Eurostat series, release calendar, and SBS industry profitability."""

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import NamedTuple, TypedDict

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.utils import timezone
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    EUROSTAT_API_DEFAULT_PARAMS,
    EUROSTAT_CALENDAR_TITLE_BY_TECHNICAL_NAME,
    EUROSTAT_CORPORATE_GFCF_SECTOR_TICKERS,
    EUROSTAT_CORPORATE_GFCF_TICKER,
    EUROSTAT_GEO_FOR_EU_LOCATION,
    EUROSTAT_GG_ASSET_TRANSACTIONS_TICKER,
    EUROSTAT_GG_DEBT_SECURITY_TRANSACTIONS_TICKER,
    EUROSTAT_GG_FINANCING_ACCOUNT_TICKER,
    EUROSTAT_GG_LOAN_TRANSACTIONS_TICKER,
    EUROSTAT_GG_OTHER_LIABILITY_TRANSACTIONS_TICKER,
    EUROSTAT_GG_OTHER_REVENUE_TICKER,
    EUROSTAT_GG_REVENUE_SCA_TICKER,
    EUROSTAT_GG_SOCIAL_CONTRIBUTIONS_TICKER,
    EUROSTAT_GG_TAX_REVENUE_COMPONENT_TICKERS,
    EUROSTAT_GG_TAX_REVENUE_TICKER,
    EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
    EUROSTAT_HH_CONSUMPTION_RATIO_TICKER,
    EUROSTAT_HH_FCE_DEFLATOR_TICKER,
    EUROSTAT_HH_PENSION_ADJ_TICKER,
    EUROSTAT_HH_SAVING_RATIO_TICKER,
    EUROSTAT_NET_EXPORTS_EXPORT_TICKER,
    EUROSTAT_NET_EXPORTS_IMPORT_TICKER,
    EUROSTAT_NET_EXPORTS_TICKER,
    EUROSTAT_NET_OPERATING_SURPLUS_CFC_TICKER,
    EUROSTAT_NET_OPERATING_SURPLUS_GROSS_TICKER,
    EUROSTAT_NET_OPERATING_SURPLUS_TICKER,
    EUROSTAT_NOMINAL_HH_CONSUMPTION_TICKER,
    EUROSTAT_NOMINAL_HH_GDHI_TICKER,
    EUROSTAT_NOMINAL_HH_SAVING_TICKER,
    EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS,
    EUROSTAT_PALMA_TICKER,
    EUROSTAT_PALMA_TOP_DECILE_TICKER,
    EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS,
    EUROSTAT_PUBLICATION_SCHEDULE_URL,
    EUROSTAT_REAL_HH_GDHI_TICKER,
    EUROSTAT_SBS_HISTORICAL_DATASETS,
    EUROSTAT_SBS_HISTORICAL_END_YEAR,
    EUROSTAT_SBS_HISTORICAL_GOS_INDICATOR,
    EUROSTAT_SBS_HISTORICAL_GVA_INDICATOR,
    EUROSTAT_SBS_HISTORICAL_START_YEAR,
    EUROSTAT_SBS_HISTORICAL_TURNOVER_INDICATOR,
    EUROSTAT_SBS_OVERVIEW_DATASET,
    EUROSTAT_SBS_OVERVIEW_GOS_INDICATOR,
    EUROSTAT_SBS_OVERVIEW_GVA_INDICATOR,
    EUROSTAT_SBS_OVERVIEW_START_YEAR,
    EUROSTAT_SBS_OVERVIEW_TURNOVER_INDICATOR,
    EUROSTAT_SERIES_TEMPLATES,
    EUROSTAT_STATISTICS_API_BASE_URL,
    EurostatQueryParams,
    EurostatTickerParams,
)
from economic_overview.services.scrapers.common import (
    ScrapedIndustryProfitability,
    ScrapingResult,
    calculate_ratio_scraping_results_as_percent,
    deflate_scraping_results_by_period,
    divide_scraping_results_by_period,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
    subtract_scraping_results_by_period,
    sum_scraping_results_by_period,
)

logger = logging.getLogger(__name__)


class _SbsMetricIndicators(NamedTuple):
    """Turnover / GOS / GVA indicator codes for one SBS dataset family."""

    turnover: str
    gos: str
    gva: str


_OVERVIEW_INDICATORS = _SbsMetricIndicators(
    turnover=EUROSTAT_SBS_OVERVIEW_TURNOVER_INDICATOR,
    gos=EUROSTAT_SBS_OVERVIEW_GOS_INDICATOR,
    gva=EUROSTAT_SBS_OVERVIEW_GVA_INDICATOR,
)
_HISTORICAL_INDICATORS = _SbsMetricIndicators(
    turnover=EUROSTAT_SBS_HISTORICAL_TURNOVER_INDICATOR,
    gos=EUROSTAT_SBS_HISTORICAL_GOS_INDICATOR,
    gva=EUROSTAT_SBS_HISTORICAL_GVA_INDICATOR,
)

# __________________________________________________________
# Values (Eurostat series)
# __________________________________________________________


class _EurostatJsonStatCategory(TypedDict, total=False):
    """JSON-stat category block (period labels → flat positions)."""

    # Usage of dict: keys are dynamic JSON-stat category labels (e.g. time periods).
    index: dict[str, int]
    # Usage of dict: keys are category codes; values are display labels.
    label: dict[str, str]


class _EurostatJsonStatDimension(TypedDict, total=False):
    """JSON-stat dimension block."""

    category: _EurostatJsonStatCategory


class _EurostatJsonStatPayload(TypedDict):
    """Eurostat Statistics API JSON-stat subset used for scraping."""

    id: list[str]
    size: list[int]
    # Usage of dict: keys are JSON-stat flat indexes; values are numbers.
    value: dict[str, float | int | None]
    # Usage of dict: keys are dynamic dimension ids (freq, unit, time, …).
    dimension: dict[str, _EurostatJsonStatDimension]


_EUROSTAT_JSONSTAT_ADAPTER = TypeAdapter(_EurostatJsonStatPayload)


def _decode_eurostat_flat_index(flat_index: int, sizes: list[int]) -> list[int]:
    """Decode a JSON-stat flat index into per-dimension coordinates."""
    coordinates: list[int] = []
    remaining = flat_index
    for size in reversed(sizes):
        coordinates.append(remaining % size)
        remaining //= size
    return list(reversed(coordinates))


def _parse_eurostat_period_label(period_label: str) -> date | None:
    """Parse Eurostat time labels ('YYYY-MM', 'YYYY-Qn', or annual 'YYYY')."""
    monthly_match = re.fullmatch(r"(\d{4})-(\d{2})", period_label)
    if monthly_match:
        year = int(monthly_match.group(1))
        month = int(monthly_match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
        return None
    quarterly_match = re.fullmatch(r"(\d{4})-Q([1-4])", period_label)
    if quarterly_match:
        year = int(quarterly_match.group(1))
        quarter = int(quarterly_match.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)
    annual_match = re.fullmatch(r"(\d{4})", period_label)
    if annual_match:
        return date(int(annual_match.group(1)), 1, 1)
    return None


def _parse_eurostat_jsonstat_values(
    payload: _EurostatJsonStatPayload,
) -> list[ScrapingResult]:
    """Parse Eurostat Statistics API JSON-stat 'value' / 'dimension' payload."""
    dimension_ids = payload["id"]
    sizes = payload["size"]
    values = payload["value"]
    dimensions = payload["dimension"]
    if "time" not in dimension_ids:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="Eurostat payload missing time."
            )
        ]

    time_dimension = dimensions.get("time", _EurostatJsonStatDimension())
    time_category = time_dimension.get("category", _EurostatJsonStatCategory())
    time_index = time_category.get("index")
    if time_index is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Eurostat time index is not a mapping.",
            )
        ]
    position_to_period = {
        position: period_label for period_label, position in time_index.items()
    }
    time_dimension_offset = dimension_ids.index("time")

    economic_data: list[ScrapingResult] = []
    for flat_index_str, raw_value in values.items():
        try:
            flat_index = int(flat_index_str)
            coordinates = _decode_eurostat_flat_index(flat_index, sizes)
            time_position = coordinates[time_dimension_offset]
            period_label = position_to_period[time_position]
            period = _parse_eurostat_period_label(period_label)
            if period is None:
                continue
            data_value = float(raw_value) if raw_value is not None else None
            if data_value is None:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )

    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _build_eurostat_request_params(
    series_id: str, location: str
) -> EurostatTickerParams | None:
    """Build Statistics API dataset + filters for a configured Eurostat series."""
    template = next(
        (
            series_template
            for series_template in EUROSTAT_SERIES_TEMPLATES
            if series_template.series_id == series_id
        ),
        None,
    )
    if template is None:
        return None
    if location == EconomicDataLocationChoices.EU:
        geo = template.eu_geo or EUROSTAT_GEO_FOR_EU_LOCATION
        params: EurostatQueryParams = {**template.params, "geo": geo}
        if template.eu_params is not None:
            params = {**params, **template.eu_params}
    else:
        params = {**template.params, "geo": location}
    return EurostatTickerParams(dataset=template.dataset, params=params)


def _get_eurostat_palma_ratio_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Combine Palma-ratio decile series into one percentage series."""
    top_decile_series = get_data_from_eurostat(
        EUROSTAT_PALMA_TOP_DECILE_TICKER,
        target_period,
        frequency,
        location,
    )
    bottom_decile_series_list = [
        get_data_from_eurostat(bottom_decile_ticker, target_period, frequency, location)
        for bottom_decile_ticker in EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS
    ]
    bottom_forty_series = sum_scraping_results_by_period(bottom_decile_series_list)
    palma_series = divide_scraping_results_by_period(
        top_decile_series, bottom_forty_series
    )
    if not palma_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat Palma-ratio values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        palma_series, target_period, frequency
    )


def _get_eurostat_gg_financing_account_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Subtract government asset transactions from total liability transactions."""
    liability_transactions_series = get_data_from_eurostat(
        EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        target_period,
        frequency,
        location,
    )
    asset_transactions_series = get_data_from_eurostat(
        EUROSTAT_GG_ASSET_TRANSACTIONS_TICKER,
        target_period,
        frequency,
        location,
    )
    financing_account_series = subtract_scraping_results_by_period(
        liability_transactions_series, asset_transactions_series
    )
    if not financing_account_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No government financing-account values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        financing_account_series, target_period, frequency
    )


def _get_eurostat_gg_tax_revenue_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Sum configured government tax-revenue component series."""
    tax_component_series_list = [
        get_data_from_eurostat(tax_component_ticker, target_period, frequency, location)
        for tax_component_ticker in EUROSTAT_GG_TAX_REVENUE_COMPONENT_TICKERS
    ]
    tax_revenue_series = sum_scraping_results_by_period(tax_component_series_list)
    if not tax_revenue_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat government tax-revenue values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        tax_revenue_series, target_period, frequency
    )


def _get_eurostat_gg_other_revenue_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Derive government other revenue from total SCA revenue minus taxes and D61."""
    total_revenue_series = get_data_from_eurostat(
        EUROSTAT_GG_REVENUE_SCA_TICKER, target_period, frequency, location
    )
    tax_revenue_series = get_data_from_eurostat(
        EUROSTAT_GG_TAX_REVENUE_TICKER, target_period, frequency, location
    )
    social_contributions_series = get_data_from_eurostat(
        EUROSTAT_GG_SOCIAL_CONTRIBUTIONS_TICKER,
        target_period,
        frequency,
        location,
    )
    taxes_and_social_series = sum_scraping_results_by_period(
        [tax_revenue_series, social_contributions_series]
    )
    other_revenue_series = subtract_scraping_results_by_period(
        total_revenue_series, taxes_and_social_series
    )
    if not other_revenue_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat government other-revenue values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        other_revenue_series, target_period, frequency
    )


def _get_eurostat_gg_other_liability_transactions_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Subtract F.3 and F.4 liability flows from total government liability flows."""
    total_liability_series = get_data_from_eurostat(
        EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
        target_period,
        frequency,
        location,
    )
    debt_security_series = get_data_from_eurostat(
        EUROSTAT_GG_DEBT_SECURITY_TRANSACTIONS_TICKER,
        target_period,
        frequency,
        location,
    )
    loan_series = get_data_from_eurostat(
        EUROSTAT_GG_LOAN_TRANSACTIONS_TICKER,
        target_period,
        frequency,
        location,
    )
    f3_and_f4_series = sum_scraping_results_by_period(
        [debt_security_series, loan_series]
    )
    other_liability_series = subtract_scraping_results_by_period(
        total_liability_series, f3_and_f4_series
    )
    if not other_liability_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "No Eurostat government other-liability transaction "
                    "values found."
                ),
            )
        ]
    return filter_scraping_results_by_target_period(
        other_liability_series, target_period, frequency
    )


def _get_eurostat_hh_saving_or_consumption_ratio_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Return household saving or consumption ratio using pension-adjusted income."""
    numerator_ticker = (
        EUROSTAT_NOMINAL_HH_SAVING_TICKER
        if ticker == EUROSTAT_HH_SAVING_RATIO_TICKER
        else EUROSTAT_NOMINAL_HH_CONSUMPTION_TICKER
    )
    numerator_series = get_data_from_eurostat(
        numerator_ticker, target_period, frequency, location
    )
    income_series = get_data_from_eurostat(
        EUROSTAT_NOMINAL_HH_GDHI_TICKER, target_period, frequency, location
    )
    pension_adj_series = get_data_from_eurostat(
        EUROSTAT_HH_PENSION_ADJ_TICKER, target_period, frequency, location
    )
    adjusted_income_series = sum_scraping_results_by_period(
        [income_series, pension_adj_series]
    )
    ratio_series = calculate_ratio_scraping_results_as_percent(
        numerator_series, adjusted_income_series
    )
    if not ratio_series:
        missing_label = (
            "saving-ratio"
            if ticker == EUROSTAT_HH_SAVING_RATIO_TICKER
            else "consumption-ratio"
        )
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No Eurostat household {missing_label} values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        ratio_series, target_period, frequency
    )


def _get_eurostat_real_hh_gdhi_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Deflate nominal household gross disposable income by the HH deflator."""
    nominal_series = get_data_from_eurostat(
        EUROSTAT_NOMINAL_HH_GDHI_TICKER, target_period, frequency, location
    )
    deflator_series = get_data_from_eurostat(
        EUROSTAT_HH_FCE_DEFLATOR_TICKER, target_period, frequency, location
    )
    real_income_series = deflate_scraping_results_by_period(
        nominal_series,
        deflator_series,
        deflator_is_index_base_100=True,
    )
    if not real_income_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat real household GDHI values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        real_income_series, target_period, frequency
    )


def _get_eurostat_net_operating_surplus_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Subtract consumption of fixed capital from gross operating surplus."""
    gross_series = get_data_from_eurostat(
        EUROSTAT_NET_OPERATING_SURPLUS_GROSS_TICKER,
        target_period,
        frequency,
        location,
    )
    cfc_series = get_data_from_eurostat(
        EUROSTAT_NET_OPERATING_SURPLUS_CFC_TICKER,
        target_period,
        frequency,
        location,
    )
    net_series = subtract_scraping_results_by_period(gross_series, cfc_series)
    if not net_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat net operating surplus values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        net_series, target_period, frequency
    )


def _get_eurostat_corporate_gfcf_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Sum corporate gross fixed capital formation across S.11 and S.12 sectors."""
    sector_series_list = [
        get_data_from_eurostat(sector_ticker, target_period, frequency, location)
        for sector_ticker in EUROSTAT_CORPORATE_GFCF_SECTOR_TICKERS
    ]
    summed_series = sum_scraping_results_by_period(sector_series_list)
    if not summed_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat corporate GFCF values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        summed_series, target_period, frequency
    )


def _get_eurostat_net_exports_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Subtract chain-linked imports from chain-linked exports."""
    export_series = get_data_from_eurostat(
        EUROSTAT_NET_EXPORTS_EXPORT_TICKER, target_period, frequency, location
    )
    import_series = get_data_from_eurostat(
        EUROSTAT_NET_EXPORTS_IMPORT_TICKER, target_period, frequency, location
    )
    net_exports_series = subtract_scraping_results_by_period(
        export_series, import_series
    )
    if not net_exports_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Eurostat real net-exports values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        net_exports_series, target_period, frequency
    )


def _fetch_eurostat_direct_series_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Fetch one configured Eurostat series from the Statistics API."""
    ticker_params = _build_eurostat_request_params(ticker, location)
    if ticker_params is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Eurostat ticker: {ticker}",
            )
        ]

    eurostat_url = f"{EUROSTAT_STATISTICS_API_BASE_URL}{ticker_params['dataset']}"
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    eurostat_request_params: dict[str, str] = {
        "format": EUROSTAT_API_DEFAULT_PARAMS["format"],
        "lang": EUROSTAT_API_DEFAULT_PARAMS["lang"],
    }
    for param_key, param_value in ticker_params["params"].items():
        assert isinstance(param_value, str)
        eurostat_request_params[param_key] = param_value
    response = requests.get(
        eurostat_url,
        params=eurostat_request_params,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Eurostat data: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        payload = _EUROSTAT_JSONSTAT_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Invalid Eurostat JSON-stat: {exc}",
            )
        ]

    economic_data = _parse_eurostat_jsonstat_values(payload)
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No Eurostat values found."
            )
        ]
    # Parse may return a single empty error result; index 0 is that result.
    if economic_data[0]["data_value"] is None and economic_data[0]["period"] is None:
        return economic_data

    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_eurostat(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
    location: str = "",
) -> list[ScrapingResult]:
    """Get Eurostat economic data (all periods, or a single matching period).

    Derived tickers are built from sibling helpers; direct series use the
    configured Statistics API dataset and indicator 'location' as geo. Periods
    are 'YYYY-MM', 'YYYY-Qn', or annual 'YYYY'.

    Source: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/
    """
    if frequency not in (
        EconomicPublicationFrequencyChoices.MONTHLY,
        EconomicPublicationFrequencyChoices.QUARTERLY,
        EconomicPublicationFrequencyChoices.ANNUAL,
    ):
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for Eurostat scrape: {frequency}",
            )
        ]
    if ticker == EUROSTAT_PALMA_TICKER:
        return _get_eurostat_palma_ratio_data(target_period, frequency, location)
    if ticker == EUROSTAT_GG_FINANCING_ACCOUNT_TICKER:
        return _get_eurostat_gg_financing_account_data(
            target_period, frequency, location
        )
    if ticker == EUROSTAT_GG_TAX_REVENUE_TICKER:
        return _get_eurostat_gg_tax_revenue_data(target_period, frequency, location)
    if ticker == EUROSTAT_GG_OTHER_REVENUE_TICKER:
        return _get_eurostat_gg_other_revenue_data(target_period, frequency, location)
    if ticker == EUROSTAT_GG_OTHER_LIABILITY_TRANSACTIONS_TICKER:
        return _get_eurostat_gg_other_liability_transactions_data(
            target_period, frequency, location
        )
    if ticker in {
        EUROSTAT_HH_SAVING_RATIO_TICKER,
        EUROSTAT_HH_CONSUMPTION_RATIO_TICKER,
    }:
        return _get_eurostat_hh_saving_or_consumption_ratio_data(
            ticker, target_period, frequency, location
        )
    if ticker == EUROSTAT_REAL_HH_GDHI_TICKER:
        return _get_eurostat_real_hh_gdhi_data(target_period, frequency, location)
    if ticker == EUROSTAT_NET_OPERATING_SURPLUS_TICKER:
        return _get_eurostat_net_operating_surplus_data(
            target_period, frequency, location
        )
    if ticker == EUROSTAT_CORPORATE_GFCF_TICKER:
        return _get_eurostat_corporate_gfcf_data(target_period, frequency, location)
    if ticker == EUROSTAT_NET_EXPORTS_TICKER:
        return _get_eurostat_net_exports_data(target_period, frequency, location)
    return _fetch_eurostat_direct_series_data(
        ticker, target_period, frequency, location
    )


# __________________________________________________________
# Publication dates (Eurostat release calendar)
# __________________________________________________________


class _EurostatCalendarEvent(TypedDict, total=False):
    """One FullCalendar event from Eurostat eventsJson (fields we read)."""

    title: str
    start: str


class _EurostatPublicationScheduleRow(TypedDict):
    """One normalized Eurostat publication schedule entry before DataFrame load."""

    name: str
    publication_date: str | None


_EUROSTAT_CALENDAR_EVENTS_ADAPTER = TypeAdapter(list[_EurostatCalendarEvent])


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_eurostat_publication_schedule() -> pd.DataFrame:
    """Get Eurostat publication schedule.

    Source: https://ec.europa.eu/eurostat/news/release-calendar/
    JSON feed: https://ec.europa.eu/eurostat/o/calendars/eventsJson
    Event 'start' values are UTC ('…Z'); the UI labels Europe/Luxembourg.
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
    range_start = timezone.now()
    range_end = range_start + timedelta(days=EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS)
    response = requests.get(
        EUROSTAT_PUBLICATION_SCHEDULE_URL,
        params={
            "start": range_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": range_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Eurostat publication schedule: {response.text}")
        return default_df

    try:
        raw_payload = json.loads(response.content)
        events = _EUROSTAT_CALENDAR_EVENTS_ADAPTER.validate_python(raw_payload)
    except (TypeError, json.JSONDecodeError, ValidationError):
        logger.warning("Invalid Eurostat publication schedule JSON")
        return default_df

    records: list[_EurostatPublicationScheduleRow] = []
    for event in events:
        records.append(
            _EurostatPublicationScheduleRow(
                name=event.get("title", ""),
                publication_date=event.get("start"),
            )
        )

    df = pd.DataFrame(records)
    if df.empty:
        return default_df
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_eurostat(name: str) -> list[datetime]:
    """Get upcoming publication dates from Eurostat."""
    calendar_title = EUROSTAT_CALENDAR_TITLE_BY_TECHNICAL_NAME.get(name, name)
    publication_schedule = _get_eurostat_publication_schedule()
    publication_dates = publication_schedule[
        publication_schedule["name"] == calendar_title
    ]["publication_date"]
    publication_datetimes = [
        pd_timestamp.to_pydatetime() for pd_timestamp in publication_dates.tolist()
    ]
    return filter_upcoming_publication_dates(publication_datetimes)


# __________________________________________________________
# Industry profitability (Eurostat SBS turnover, surplus, and value added)
# __________________________________________________________


def _is_nace_rev2_division_code(nace_code: str) -> bool:
    """True for NACE Rev. 2 division codes such as 'C10' or 'B08'."""
    return len(nace_code) == 3 and nace_code[0].isalpha() and nace_code[1:].isdigit()


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _fetch_eurostat_sbs_payload(
    *,
    dataset: str,
    geo: str,
    year: int,
    indicator_dimension: str,
    indicator: str,
) -> _EurostatJsonStatPayload | None:
    """GET one FR year × indicator slice from a Eurostat SBS dataset."""
    # Usage of dict: built for requests.get(params=...); keys are API query names.
    query_params: dict[str, str] = {
        "format": EUROSTAT_API_DEFAULT_PARAMS["format"],
        "lang": EUROSTAT_API_DEFAULT_PARAMS["lang"],
        "geo": geo,
        "time": str(year),
        indicator_dimension: indicator,
    }
    url = f"{EUROSTAT_STATISTICS_API_BASE_URL}{dataset}"
    try:
        response = requests.get(url, params=query_params, timeout=120)
        response.raise_for_status()
        return _EUROSTAT_JSONSTAT_ADAPTER.validate_python(response.json())
    except (requests.RequestException, ValidationError, ValueError) as exc:
        logger.warning(
            "Eurostat SBS fetch failed dataset=%s geo=%s year=%s indicator=%s: %s",
            dataset,
            geo,
            year,
            indicator,
            exc,
        )
        return None


def _extract_division_values_by_code(
    payload: _EurostatJsonStatPayload,
) -> dict[str, tuple[str, float]]:
    """Map NACE division code → (label, value) from one indicator payload."""
    dimension_ids = payload["id"]
    sizes = payload["size"]
    if "nace_r2" not in dimension_ids:
        return {}
    nace_offset = dimension_ids.index("nace_r2")
    nace_dimension = payload["dimension"].get("nace_r2", _EurostatJsonStatDimension())
    nace_category = nace_dimension.get("category", _EurostatJsonStatCategory())
    nace_index = nace_category.get("index") or {}
    nace_labels = nace_category.get("label") or {}
    position_to_nace = {
        position: nace_code for nace_code, position in nace_index.items()
    }
    # Usage of dict: NACE division code → (label, printed value).
    values_by_code: dict[str, tuple[str, float]] = {}
    for flat_index_str, raw_value in payload["value"].items():
        if raw_value is None:
            continue
        try:
            coordinates = _decode_eurostat_flat_index(int(flat_index_str), sizes)
            nace_code = position_to_nace[coordinates[nace_offset]]
        except (KeyError, TypeError, ValueError):
            continue
        if not _is_nace_rev2_division_code(nace_code):
            continue
        values_by_code[nace_code] = (
            nace_labels.get(nace_code, nace_code),
            float(raw_value),
        )
    return values_by_code


def _merge_metric_maps_into_scraped_industry_profitabilities(
    *,
    period: date,
    turnover_by_code: dict[str, tuple[str, float]],
    gos_by_code: dict[str, tuple[str, float]],
    gva_by_code: dict[str, tuple[str, float]],
) -> list[ScrapedIndustryProfitability]:
    """Build scraped industry profitabilities for every NACE code in any metric map."""
    industry_codes = set(turnover_by_code) | set(gos_by_code) | set(gva_by_code)
    scraped_industry_profitabilities: list[ScrapedIndustryProfitability] = []
    for industry_code in sorted(industry_codes):
        turnover_entry = turnover_by_code.get(industry_code)
        gos_entry = gos_by_code.get(industry_code)
        gva_entry = gva_by_code.get(industry_code)
        industry_label = (
            turnover_entry or gos_entry or gva_entry or (industry_code, 0.0)
        )[0]
        scraped_industry_profitabilities.append(
            ScrapedIndustryProfitability(
                industry_code=industry_code,
                industry_label=industry_label,
                period=period,
                turnover=None if turnover_entry is None else turnover_entry[1],
                operating_profit=None if gos_entry is None else gos_entry[1],
                gva=None if gva_entry is None else gva_entry[1],
            )
        )
    return scraped_industry_profitabilities


def _fetch_division_metric_map(
    *,
    dataset: str,
    year: int,
    indicator_dimension: str,
    indicator: str,
) -> dict[str, tuple[str, float]]:
    """Fetch one indicator and map NACE division codes to values."""
    payload = _fetch_eurostat_sbs_payload(
        dataset=dataset,
        geo="FR",
        year=year,
        indicator_dimension=indicator_dimension,
        indicator=indicator,
    )
    if payload is None:
        return {}
    return _extract_division_values_by_code(payload)


def _scrape_historical_sbs_year(year: int) -> list[ScrapedIndustryProfitability]:
    """Scrape NACE-division turnover / GOS / GVA for one historical SBS year."""
    # Usage of dict: NACE code → (label, value); later annexes do not overwrite earlier.
    turnover_by_code: dict[str, tuple[str, float]] = {}
    gos_by_code: dict[str, tuple[str, float]] = {}
    gva_by_code: dict[str, tuple[str, float]] = {}
    for dataset in EUROSTAT_SBS_HISTORICAL_DATASETS:
        for target_map, indicator in (
            (turnover_by_code, _HISTORICAL_INDICATORS.turnover),
            (gos_by_code, _HISTORICAL_INDICATORS.gos),
            (gva_by_code, _HISTORICAL_INDICATORS.gva),
        ):
            for industry_code, entry in _fetch_division_metric_map(
                dataset=dataset,
                year=year,
                indicator_dimension="indic_sb",
                indicator=indicator,
            ).items():
                if industry_code not in target_map:
                    target_map[industry_code] = entry
    return _merge_metric_maps_into_scraped_industry_profitabilities(
        period=date(year, 1, 1),
        turnover_by_code=turnover_by_code,
        gos_by_code=gos_by_code,
        gva_by_code=gva_by_code,
    )


def _scrape_overview_sbs_year(year: int) -> list[ScrapedIndustryProfitability]:
    """Scrape NACE-division turnover / GOS / GVA for one SBS overview year."""
    turnover_by_code = _fetch_division_metric_map(
        dataset=EUROSTAT_SBS_OVERVIEW_DATASET,
        year=year,
        indicator_dimension="indic_sbs",
        indicator=_OVERVIEW_INDICATORS.turnover,
    )
    gos_by_code = _fetch_division_metric_map(
        dataset=EUROSTAT_SBS_OVERVIEW_DATASET,
        year=year,
        indicator_dimension="indic_sbs",
        indicator=_OVERVIEW_INDICATORS.gos,
    )
    gva_by_code = _fetch_division_metric_map(
        dataset=EUROSTAT_SBS_OVERVIEW_DATASET,
        year=year,
        indicator_dimension="indic_sbs",
        indicator=_OVERVIEW_INDICATORS.gva,
    )
    return _merge_metric_maps_into_scraped_industry_profitabilities(
        period=date(year, 1, 1),
        turnover_by_code=turnover_by_code,
        gos_by_code=gos_by_code,
        gva_by_code=gva_by_code,
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_industry_profitability_from_eurostat_sbs() -> (
    list[ScrapedIndustryProfitability]
):
    """Scrape FR NACE Rev. 2 division turnover, GOS, and GVA from SBS."""
    scraped_industry_profitabilities: list[ScrapedIndustryProfitability] = []
    for year in range(
        EUROSTAT_SBS_HISTORICAL_START_YEAR,
        EUROSTAT_SBS_HISTORICAL_END_YEAR + 1,
    ):
        scraped_industry_profitabilities.extend(_scrape_historical_sbs_year(year))
    latest_year = date.today().year
    for year in range(EUROSTAT_SBS_OVERVIEW_START_YEAR, latest_year + 1):
        scraped_industry_profitabilities.extend(_scrape_overview_sbs_year(year))
    return scraped_industry_profitabilities
