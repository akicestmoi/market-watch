"""Scrape FRED series values and FRED release dates."""

import logging
from datetime import date, datetime
from typing import TypedDict

import requests
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
    BIS_CREDIT_CATEGORY_NAME,
    BIS_EER_CATEGORY_NAME,
    BIS_EER_MONTHLY_RELEASE_TYPE,
    BIS_RELEASE_CALENDAR_API_URL,
    BLS_ECI_EASTERN_RELEASE_DATES,
    BLS_ECI_EASTERN_RELEASE_HOUR,
    BLS_ECI_EASTERN_RELEASE_MINUTE,
    FRED_GOVERNMENT_BREAKDOWN_RESIDUAL_BY_TICKER,
    FRED_GOVERNMENT_DEBT_LOANS_TICKER,
    FRED_GOVERNMENT_DEBT_SECURITIES_TICKER,
    FRED_GOVERNMENT_DEBT_TICKER,
    FRED_GROSS_CAPITAL_SHARE_TICKER,
    FRED_HH_CONSUMPTION_AMOUNT_TICKER,
    FRED_HH_CONSUMPTION_INCOME_TICKER,
    FRED_HH_CONSUMPTION_RATIO_TICKER,
    FRED_HH_DEBT_AMOUNT_TICKER,
    FRED_HH_DEBT_INCOME_TICKER,
    FRED_HH_DEBT_RATIO_TICKER,
    FRED_HH_SAVING_AMOUNT_TICKER,
    FRED_HH_SAVING_INCOME_TICKER,
    FRED_HH_SAVING_RATIO_TICKER,
    FRED_NFC_CAPITAL_SHARE_DENOMINATOR_TICKER,
    FRED_NFC_CFC_TICKER,
    FRED_NFC_NOS_TICKER,
    FRED_OBSERVATION_START,
    FRED_OBSERVATIONS_URL,
    FRED_RELEASE_DATES_URL,
    FRED_RELEASE_EASTERN_TIME_BY_RELEASE_ID,
    FRED_RELEASE_ID_BY_TECHNICAL_NAME,
    FRED_VALUE_SCALE_BY_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    calculate_ratio_scraping_results_as_percent,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
    subtract_scraping_results_by_period,
    sum_scraping_results_by_period,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (FRED series)
# __________________________________________________________


class _FredSeriesValue(TypedDict, total=False):
    """One FRED series value from the API payload (fields we read)."""

    date: str
    value: str


class _FredSeriesValuesPayload(TypedDict, total=False):
    """FRED 'series/observations' JSON root (fields we read)."""

    # API field name is 'observations'; values are series values we parse.
    observations: list[_FredSeriesValue]


_FRED_SERIES_VALUES_ADAPTER = TypeAdapter(_FredSeriesValuesPayload)


def _parse_fred_series_values(
    payload: _FredSeriesValuesPayload,
) -> list[ScrapingResult]:
    """Parse FRED series values into scraping results (newest first)."""
    economic_data: list[ScrapingResult] = []
    for series_value in payload.get("observations", []):
        period_label = series_value.get("date")
        raw_value = series_value.get("value")
        if not period_label or raw_value is None or raw_value == ".":
            continue
        try:
            period = datetime.strptime(period_label, "%Y-%m-%d").date()
            data_value = float(raw_value)
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


def _get_fred_government_breakdown_residual_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Build a residual by subtracting breakdown components from a total series."""
    breakdown_residual = FRED_GOVERNMENT_BREAKDOWN_RESIDUAL_BY_TICKER[ticker]
    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    f"Unsupported frequency for FRED derived series {ticker}: "
                    f"{frequency}"
                ),
            )
        ]
    residual_series = get_data_from_fred(
        breakdown_residual.total_ticker,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    # Subtract one component at a time so only periods present in every input stay.
    for component_ticker in breakdown_residual.component_tickers:
        residual_series = subtract_scraping_results_by_period(
            residual_series,
            get_data_from_fred(
                component_ticker,
                target_period,
                EconomicPublicationFrequencyChoices.QUARTERLY,
            ),
        )
    if not residual_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No FRED values found for derived series {ticker}.",
            )
        ]
    return filter_scraping_results_by_target_period(
        residual_series, target_period, frequency
    )


def _get_fred_government_debt_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Sum general-government debt securities and loans from Z.1."""
    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for FRED general-government debt: "
                    f"{frequency}"
                ),
            )
        ]
    debt_securities_series = get_data_from_fred(
        FRED_GOVERNMENT_DEBT_SECURITIES_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    debt_loans_series = get_data_from_fred(
        FRED_GOVERNMENT_DEBT_LOANS_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    general_government_debt_series = sum_scraping_results_by_period(
        [debt_securities_series, debt_loans_series]
    )
    if not general_government_debt_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No FRED general-government debt values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        general_government_debt_series, target_period, frequency
    )


def _get_fred_gross_capital_share_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Compute NFC gross capital share as (NOS + CFC) over GVA as a percent."""
    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for FRED gross capital share: "
                    f"{frequency}"
                ),
            )
        ]
    nos_series = get_data_from_fred(
        FRED_NFC_NOS_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    cfc_series = get_data_from_fred(
        FRED_NFC_CFC_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    gva_series = get_data_from_fred(
        FRED_NFC_CAPITAL_SHARE_DENOMINATOR_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    gos_series = sum_scraping_results_by_period([nos_series, cfc_series])
    capital_share_series = calculate_ratio_scraping_results_as_percent(
        gos_series, gva_series
    )
    if not capital_share_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No FRED gross capital share values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        capital_share_series, target_period, frequency
    )


def _get_fred_hh_saving_ratio_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Return the FRED household saving ratio as saving over disposable income."""
    saving_series = get_data_from_fred(
        FRED_HH_SAVING_AMOUNT_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.MONTHLY,
    )
    income_series = get_data_from_fred(
        FRED_HH_SAVING_INCOME_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.MONTHLY,
    )
    saving_ratio_series = calculate_ratio_scraping_results_as_percent(
        saving_series, income_series
    )
    if not saving_ratio_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No FRED household saving-ratio values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        saving_ratio_series, target_period, frequency
    )


def _get_fred_hh_consumption_ratio_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Return the FRED household consumption ratio as PCE over disposable income."""
    consumption_series = get_data_from_fred(
        FRED_HH_CONSUMPTION_AMOUNT_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.MONTHLY,
    )
    income_series = get_data_from_fred(
        FRED_HH_CONSUMPTION_INCOME_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.MONTHLY,
    )
    consumption_ratio_series = calculate_ratio_scraping_results_as_percent(
        consumption_series, income_series
    )
    if not consumption_ratio_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No FRED household consumption-ratio values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        consumption_ratio_series, target_period, frequency
    )


def _get_fred_hh_debt_ratio_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Return the FRED household debt ratio as liabilities over disposable income."""
    debt_series = get_data_from_fred(
        FRED_HH_DEBT_AMOUNT_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    income_series = get_data_from_fred(
        FRED_HH_DEBT_INCOME_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    debt_ratio_series = calculate_ratio_scraping_results_as_percent(
        debt_series, income_series
    )
    if not debt_ratio_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No FRED household debt-ratio values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        debt_ratio_series, target_period, frequency
    )


def _scale_fred_scraping_results_by_ticker(
    ticker: str,
    economic_data: list[ScrapingResult],
) -> list[ScrapingResult]:
    """Apply configured unit scaling (e.g. billions) to FRED scraping results."""
    value_scale = FRED_VALUE_SCALE_BY_TICKER.get(ticker)
    if value_scale is None:
        return economic_data
    return [
        ScrapingResult(
            period=scraping_result["period"],
            data_value=(
                None
                if scraping_result["data_value"] is None
                else scraping_result["data_value"] * value_scale
            ),
            comment=scraping_result["comment"],
        )
        for scraping_result in economic_data
    ]


def _fetch_fred_direct_series_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Fetch one FRED series from the observations API."""
    api_key = (getattr(settings, "FRED_API_KEY", None) or "").strip()
    if not api_key:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="FRED_API_KEY is not configured.",
            )
        ]

    response = requests.get(
        FRED_OBSERVATIONS_URL,
        params={
            "series_id": ticker,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": FRED_OBSERVATION_START,
            "sort_order": "desc",
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping FRED data: {response.text}")
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        payload = _FRED_SERIES_VALUES_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Invalid FRED series JSON: {exc}",
            )
        ]

    economic_data = _parse_fred_series_values(payload)
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No FRED series values found."
            )
        ]
    economic_data = _scale_fred_scraping_results_by_ticker(ticker, economic_data)
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_fred(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get FRED series values (all periods, or a single matching period).

    Derived household ratios: 'hh_saving_ratio' is personal saving over monthly
    disposable income; 'hh_consumption_ratio' is nominal PCE over the same
    monthly disposable income (PCECTR is discontinued on FRED); 'hh_debt_ratio'
    is household & NPISH loan liabilities (HNOLL, stored in billions) over
    quarterly disposable personal income (DPI). 'gross_capital_share' is Z.1
    S.11.1.i.q (NOS + CFC) / GVA × 100 from BOGZ1FU* component series.
    'gg_debt_securities_loans' is Z.1 consolidated general-government debt
    securities plus loans (BOGZ1FL374122005Q + BOGZ1FL374123005Q).
    'gg_other_revenue' is GRECPT minus current tax receipts minus social
    insurance contributions. 'z1_gg_other_liability_transactions' is Z.1 S.13
    total liability transactions minus debt securities minus loans, and
    'z1_gg_financing_account' is total liability minus total financial-asset
    transactions (all SAAR billions).

    Source: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
    """
    if ticker in FRED_GOVERNMENT_BREAKDOWN_RESIDUAL_BY_TICKER:
        return _get_fred_government_breakdown_residual_data(
            ticker, target_period, frequency
        )
    if ticker == FRED_GOVERNMENT_DEBT_TICKER:
        return _get_fred_government_debt_data(target_period, frequency)
    if ticker == FRED_GROSS_CAPITAL_SHARE_TICKER:
        return _get_fred_gross_capital_share_data(target_period, frequency)
    if ticker == FRED_HH_SAVING_RATIO_TICKER:
        return _get_fred_hh_saving_ratio_data(target_period, frequency)
    if ticker == FRED_HH_CONSUMPTION_RATIO_TICKER:
        return _get_fred_hh_consumption_ratio_data(target_period, frequency)
    if ticker == FRED_HH_DEBT_RATIO_TICKER:
        return _get_fred_hh_debt_ratio_data(target_period, frequency)
    return _fetch_fred_direct_series_data(ticker, target_period, frequency)


# __________________________________________________________
# Publication dates (FRED release calendar)
# __________________________________________________________


class _FredReleaseDate(TypedDict, total=False):
    """One FRED release date from the API payload (fields we read)."""

    date: str


class _FredReleaseDatesPayload(TypedDict, total=False):
    """FRED 'release/dates' JSON root (fields we read)."""

    release_dates: list[_FredReleaseDate]


_FRED_RELEASE_DATES_ADAPTER = TypeAdapter(_FredReleaseDatesPayload)


class _BisReleaseCalendarEntry(TypedDict, total=False):
    """One BIS release-calendar row (fields we read)."""

    category_name: str
    release_type: str
    release_date: str


_BIS_RELEASE_CALENDAR_ADAPTER = TypeAdapter(list[_BisReleaseCalendarEntry])


def _get_publication_dates_from_bis_calendar(
    *,
    category_name: str,
    release_type: str | None = None,
) -> list[datetime]:
    """Read upcoming BIS statistics calendar dates (date-only, Europe/Zurich)."""
    response = requests.get(
        BIS_RELEASE_CALENDAR_API_URL,
        headers={"Accept": "application/json"},
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping BIS release calendar: {response.text}")
        return []
    try:
        calendar_entries = _BIS_RELEASE_CALENDAR_ADAPTER.validate_python(
            response.json()
        )
    except (ValueError, ValidationError) as exc:
        logger.warning(f"Invalid BIS release calendar JSON: {exc}")
        return []

    publication_datetimes: list[datetime] = []
    for calendar_entry in calendar_entries:
        if calendar_entry.get("category_name") != category_name:
            continue
        if (
            release_type is not None
            and calendar_entry.get("release_type") != release_type
        ):
            continue
        release_date_label = calendar_entry.get("release_date")
        if not release_date_label:
            continue
        try:
            release_date = datetime.strptime(release_date_label, "%Y/%m/%d").date()
        except ValueError:
            continue
        # BIS publishes a calendar day only (no intraday clock) — Zurich midnight.
        publication_datetimes.append(
            convert_local_wall_time_to_utc(
                release_date.year,
                release_date.month,
                release_date.day,
                0,
                0,
                source_timezone="Europe/Zurich",
            )
        )
    publication_datetimes.sort()
    return filter_upcoming_publication_dates(publication_datetimes)


def _get_publication_dates_from_bls_eci_schedule() -> list[datetime]:
    """Return upcoming BLS Employment Cost Index slots at the official 08:30 ET."""
    publication_datetimes = [
        convert_local_wall_time_to_utc(
            year,
            month,
            day,
            BLS_ECI_EASTERN_RELEASE_HOUR,
            BLS_ECI_EASTERN_RELEASE_MINUTE,
            source_timezone="America/New_York",
        )
        for year, month, day in BLS_ECI_EASTERN_RELEASE_DATES
    ]
    return filter_upcoming_publication_dates(publication_datetimes)


def _get_fred_schedule_fallback_dates(name: str) -> list[datetime]:
    """Fill FRED gaps from the upstream publisher calendar when FRED has none."""
    if name == "BIS Effective Exchange Rate Indices":
        return _get_publication_dates_from_bis_calendar(
            category_name=BIS_EER_CATEGORY_NAME,
            release_type=BIS_EER_MONTHLY_RELEASE_TYPE,
        )
    if name == "Credit to Non-Financial Sector":
        return _get_publication_dates_from_bis_calendar(
            category_name=BIS_CREDIT_CATEGORY_NAME,
        )
    if name == "Employment Cost Index":
        return _get_publication_dates_from_bls_eci_schedule()
    return []


def _get_fred_release_dates_payload_from_api(
    release_id: int,
    api_key: str,
    today: date,
) -> _FredReleaseDatesPayload | None:
    """Fetch and validate the FRED release-dates JSON for upcoming schedules."""
    # 'realtime_start=today' is required: without it, 'sort_order=asc' +
    # 'limit' returns the oldest historical dates and long-history releases
    # (e.g. G.17 / release 13) never reach upcoming schedule dates.
    response = requests.get(
        FRED_RELEASE_DATES_URL,
        params={
            "release_id": release_id,
            "api_key": api_key,
            "file_type": "json",
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": 100,
            "realtime_start": today.isoformat(),
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping FRED release dates: {response.text}")
        return None

    try:
        return _FRED_RELEASE_DATES_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        logger.warning(f"Invalid FRED release dates JSON: {exc}")
        return None


def _list_upcoming_fred_release_datetimes_from_payload(
    payload: _FredReleaseDatesPayload,
    release_id: int,
    today: date,
) -> list[datetime]:
    """Turn validated FRED release-date schedules into up to two UTC datetimes."""
    eastern_clock = FRED_RELEASE_EASTERN_TIME_BY_RELEASE_ID.get(release_id)
    upcoming: list[datetime] = []
    for release_date_entry in payload.get("release_dates", []):
        date_label = release_date_entry.get("date")
        if not date_label:
            continue
        try:
            release_date = datetime.strptime(date_label, "%Y-%m-%d").date()
        except ValueError:
            continue
        if release_date < today:
            continue
        if eastern_clock is not None:
            hour, minute = eastern_clock
            upcoming.append(
                convert_local_wall_time_to_utc(
                    release_date.year,
                    release_date.month,
                    release_date.day,
                    hour,
                    minute,
                    source_timezone="America/New_York",
                )
            )
        else:
            # Date-only FRED calendars: start of US Eastern day (no invented clock).
            upcoming.append(
                convert_local_wall_time_to_utc(
                    release_date.year,
                    release_date.month,
                    release_date.day,
                    0,
                    0,
                    source_timezone="America/New_York",
                )
            )
        if len(upcoming) >= 2:
            break
    return upcoming


def _list_upcoming_fred_release_datetimes_from_api(
    release_id: int,
    api_key: str,
) -> list[datetime]:
    """Return up to two upcoming FRED release datetimes with Eastern-wall clocks."""
    today = timezone.now().date()
    payload = _get_fred_release_dates_payload_from_api(release_id, api_key, today)
    if payload is None:
        return []
    return _list_upcoming_fred_release_datetimes_from_payload(
        payload, release_id, today
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_fred(name: str) -> list[datetime]:
    """Get upcoming FRED release dates for a seeded technical release name.

    Source: https://fred.stlouisfed.org/docs/api/fred/release_dates.html
    When FRED has no future schedules (BIS / Credit / ECI), fall back to the
    publisher calendar so we still feed a real date and clock.
    """
    release_id = FRED_RELEASE_ID_BY_TECHNICAL_NAME.get(name)
    if release_id is None:
        logger.warning(f"No FRED release_id mapping for technical_name: {name}")
        return []

    api_key = (getattr(settings, "FRED_API_KEY", None) or "").strip()
    if not api_key:
        logger.warning("FRED_API_KEY is not configured; skipping FRED schedule.")
        return _get_fred_schedule_fallback_dates(name)

    upcoming = _list_upcoming_fred_release_datetimes_from_api(release_id, api_key)
    if upcoming:
        return upcoming
    return _get_fred_schedule_fallback_dates(name)
