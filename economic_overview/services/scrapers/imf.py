"""Scrape IMF DataMapper fiscal indicators and SDMX international-liquidity series."""

import logging
import re
from datetime import date, datetime
from typing import NamedTuple, TypedDict

import requests
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    IMF_AREA_CODE_BY_LOCATION,
    IMF_DATAMAPPER_INDICATOR_URL_TEMPLATE,
    IMF_FX_RESERVES_TICKER,
    IMF_PRIMARY_BALANCE_TICKER,
    IMF_SDMX_IL_DATA_URL_TEMPLATE,
    IMF_SDMX_IL_START_PERIOD,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
)
from economic_overview.services.scrapers.fred import get_publication_dates_from_fred

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (DataMapper and international liquidity)
# __________________________________________________________


class _ImfDatamapperPayload(TypedDict, total=False):
    """IMF DataMapper indicator JSON root (fields we read)."""

    # Usage of dict: outer keys are indicator codes; inner keys are area codes;
    # innermost keys are year strings; values are floats.
    values: dict[str, dict[str, dict[str, float | int]]]


class _ImfSdmxDimensionValue(TypedDict, total=False):
    """One coded or labeled value inside an IMF SDMX dimension."""

    id: str
    value: str
    name: str


class _ImfSdmxDimension(TypedDict, total=False):
    """One IMF SDMX series or observation dimension."""

    id: str
    values: list[_ImfSdmxDimensionValue]


class _ImfSdmxAttribute(TypedDict, total=False):
    """One IMF SDMX series attribute (e.g. SCALE)."""

    id: str
    values: list[_ImfSdmxDimensionValue]


class _ImfSdmxAttributes(TypedDict, total=False):
    """IMF SDMX structure.attributes block."""

    series: list[_ImfSdmxAttribute]


class _ImfSdmxStructureDimensions(TypedDict, total=False):
    """IMF SDMX structure.dimensions block."""

    series: list[_ImfSdmxDimension]
    observation: list[_ImfSdmxDimension]


class _ImfSdmxStructure(TypedDict, total=False):
    """One IMF SDMX-JSON structure entry."""

    dimensions: _ImfSdmxStructureDimensions
    attributes: _ImfSdmxAttributes


class _ImfSdmxSeries(TypedDict, total=False):
    """One IMF SDMX series payload (attributes + time-indexed observations)."""

    attributes: list[int | str | None]
    # Usage of dict: keys are observation indexes into TIME_PERIOD values;
    # values are observation arrays whose first element is the measure.
    observations: dict[str, list[float | int | str | None]]


class _ImfSdmxDataSet(TypedDict, total=False):
    """One IMF SDMX-JSON dataSet entry."""

    # Usage of dict: keys are colon-joined series coordinates; values are series.
    series: dict[str, _ImfSdmxSeries]


class _ImfSdmxDataBlock(TypedDict, total=False):
    """IMF SDMX-JSON data block."""

    dataSets: list[_ImfSdmxDataSet]
    structures: list[_ImfSdmxStructure]


class _ImfSdmxPayload(TypedDict, total=False):
    """IMF SDMX-JSON data message root (fields we read)."""

    data: _ImfSdmxDataBlock


_IMF_DATAMAPPER_ADAPTER = TypeAdapter(_ImfDatamapperPayload)
_IMF_SDMX_ADAPTER = TypeAdapter(_ImfSdmxPayload)

_IMF_DATAMAPPER_TICKERS: frozenset[str] = frozenset({IMF_PRIMARY_BALANCE_TICKER})
_IMF_SDMX_IL_TICKERS: frozenset[str] = frozenset({IMF_FX_RESERVES_TICKER})


def _parse_imf_area_series(
    # Usage of dict: year labels → IMF DataMapper observation values.
    area_series: dict[str, float | int],
) -> list[ScrapingResult]:
    """Parse one IMF area's year→value map into annual scraping results.

    Drops outer WEO projection years after the current calendar year.
    """
    current_year = date.today().year
    economic_data: list[ScrapingResult] = []
    for year_label, raw_value in area_series.items():
        try:
            year = int(year_label)
            data_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if year > current_year:
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


def _parse_imf_sdmx_month_label(period_label: str) -> date | None:
    """Parse IMF SDMX monthly TIME_PERIOD labels ('YYYY-Mmm')."""
    monthly_match = re.fullmatch(r"(\d{4})-M(\d{2})", period_label.strip())
    if monthly_match is None:
        return None
    return date(int(monthly_match.group(1)), int(monthly_match.group(2)), 1)


# Usage of tuple: validated payload and an error message when the fetch failed.
def _fetch_imf_datamapper_validated_payload(
    ticker: str,
) -> tuple[_ImfDatamapperPayload | None, str | None]:
    """HTTP GET one IMF DataMapper indicator and return a validated payload."""
    response = requests.get(
        IMF_DATAMAPPER_INDICATOR_URL_TEMPLATE.format(indicator=ticker),
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping IMF DataMapper: {response.text}")
        return None, response.text
    try:
        raw_payload = response.json()
    except ValueError as exc:
        return None, f"Invalid IMF DataMapper JSON: {exc}"
    # Drop junk '' indicator keys before TypeAdapter validation.
    if isinstance(raw_payload, dict):
        raw_values = raw_payload.get("values")
        if isinstance(raw_values, dict):
            raw_payload["values"] = {
                indicator_code: area_map
                for indicator_code, area_map in raw_values.items()
                if indicator_code and isinstance(area_map, dict)
            }
    try:
        return _IMF_DATAMAPPER_ADAPTER.validate_python(raw_payload), None
    except ValidationError as exc:
        return None, f"Invalid IMF DataMapper JSON: {exc}"


def _get_imf_sdmx_scale_divisor(
    structure: _ImfSdmxStructure, series_attributes: list[int | str | None]
) -> float:
    """Return 10^SCALE so observation values convert into millions of USD.

    IMF IL stores reserves in USD with series attribute SCALE='6'; dividing by
    10^6 yields millions of dollars (same Abs unit as the former FRED series).
    """
    series_attribute_defs = (structure.get("attributes") or {}).get("series") or []
    for attribute_index, attribute_def in enumerate(series_attribute_defs):
        if attribute_def.get("id") != "SCALE":
            continue
        if attribute_index >= len(series_attributes):
            break
        scale_value_index = series_attributes[attribute_index]
        if not isinstance(scale_value_index, int):
            break
        scale_values = attribute_def.get("values") or []
        if scale_value_index < 0 or scale_value_index >= len(scale_values):
            break
        scale_code = scale_values[scale_value_index].get("id") or ""
        try:
            return 10.0 ** int(scale_code)
        except ValueError:
            break
    return 1_000_000.0


class _ImfSdmxIlSeriesContext(NamedTuple):
    """TIME_PERIOD values plus one IL series observation map and scale."""

    time_values: list[_ImfSdmxDimensionValue]
    observations: dict[str, list[float | int | str | None]]
    scale_divisor: float


def _get_imf_sdmx_il_series_context(
    payload: _ImfSdmxPayload,
) -> _ImfSdmxIlSeriesContext | None:
    """Read the single IL series block and TIME_PERIOD axis from an SDMX payload."""
    data_block = payload.get("data") or {}
    data_sets = data_block.get("dataSets") or []
    structures = data_block.get("structures") or []
    if not data_sets or not structures:
        return None
    # One series key is requested, so structures / dataSets each have one entry.
    structure = structures[0]
    series_map = data_sets[0].get("series") or {}
    if not series_map:
        return None
    # Single COUNTRY.INDICATOR.UNIT.FREQUENCY key → one series payload.
    series_payload = next(iter(series_map.values()))
    observations = series_payload.get("observations") or {}
    observation_dimensions = (structure.get("dimensions") or {}).get(
        "observation"
    ) or []
    time_dimension = next(
        (
            dimension
            for dimension in observation_dimensions
            if dimension.get("id") == "TIME_PERIOD"
        ),
        None,
    )
    if time_dimension is None:
        return None
    time_values = time_dimension.get("values") or []
    scale_divisor = _get_imf_sdmx_scale_divisor(
        structure, series_payload.get("attributes") or []
    )
    return _ImfSdmxIlSeriesContext(
        time_values=time_values,
        observations=observations,
        scale_divisor=scale_divisor,
    )


def _parse_imf_sdmx_il_observation_entry(
    observation_index_label: str,
    observation_values: list[float | int | str | None],
    *,
    time_values: list[_ImfSdmxDimensionValue],
    scale_divisor: float,
) -> ScrapingResult | None:
    """Parse one IL SDMX observation index into a monthly scraping result."""
    if not observation_values:
        return None
    # SDMX stores one scalar per observation coordinate.
    raw_value = observation_values[0]
    if raw_value is None:
        return None
    try:
        time_entry = time_values[int(observation_index_label)]
        period_label = (
            time_entry.get("value")
            or time_entry.get("id")
            or time_entry.get("name")
            or ""
        )
        period = _parse_imf_sdmx_month_label(period_label)
        if period is None:
            return None
        data_value = float(raw_value) / scale_divisor
    except (IndexError, TypeError, ValueError):
        return None
    return ScrapingResult(period=period, data_value=data_value, comment="")


def _parse_imf_sdmx_il_observations(
    payload: _ImfSdmxPayload,
) -> list[ScrapingResult]:
    """Parse IMF IL SDMX series observations into monthly scraping results."""
    series_context = _get_imf_sdmx_il_series_context(payload)
    if series_context is None:
        return []

    economic_data: list[ScrapingResult] = []
    for (
        observation_index_label,
        observation_values,
    ) in series_context.observations.items():
        parsed = _parse_imf_sdmx_il_observation_entry(
            observation_index_label,
            observation_values,
            time_values=series_context.time_values,
            scale_divisor=series_context.scale_divisor,
        )
        if parsed is not None:
            economic_data.append(parsed)
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


# Usage of tuple: validated SDMX payload and an error message when the fetch failed.
def _fetch_imf_sdmx_il_validated_payload(
    ref_area: str,
    ticker: str,
) -> tuple[_ImfSdmxPayload | None, str | None]:
    """HTTP GET one IMF International Liquidity SDMX series and validate JSON."""
    response = requests.get(
        IMF_SDMX_IL_DATA_URL_TEMPLATE.format(ref_area=ref_area, indicator=ticker),
        params={"startPeriod": IMF_SDMX_IL_START_PERIOD},
        headers={"Accept": "application/vnd.sdmx.data+json"},
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping IMF IL SDMX: {response.text[:500]}")
        return None, response.text[:500]
    try:
        return _IMF_SDMX_ADAPTER.validate_python(response.json()), None
    except (ValueError, ValidationError) as exc:
        return None, f"Invalid IMF IL SDMX JSON: {exc}"


def _get_imf_datamapper_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Fetch one IMF DataMapper annual indicator for a location."""
    if frequency != EconomicPublicationFrequencyChoices.ANNUAL:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for IMF DataMapper scrape: {frequency}",
            )
        ]
    area_code = IMF_AREA_CODE_BY_LOCATION.get(location)
    if area_code is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported IMF location: {location}",
            )
        ]

    payload, error_comment = _fetch_imf_datamapper_validated_payload(ticker)
    if error_comment is not None or payload is None:
        return [
            ScrapingResult(period=None, data_value=None, comment=error_comment or "")
        ]

    indicator_values = (payload.get("values") or {}).get(ticker) or {}
    area_series = indicator_values.get(area_code)
    if area_series is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(f"No IMF values for indicator {ticker} and area {area_code}."),
            )
        ]

    economic_data = _parse_imf_area_series(area_series)
    if not economic_data:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="No IMF series values found."
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


def _get_imf_sdmx_il_data(
    ticker: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
    location: str,
) -> list[ScrapingResult]:
    """Fetch one IMF International Liquidity SDMX monthly series for a location."""
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for IMF IL scrape: {frequency}",
            )
        ]
    ref_area = IMF_AREA_CODE_BY_LOCATION.get(location)
    if ref_area is None or location == EconomicDataLocationChoices.EU:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported IMF location: {location}",
            )
        ]

    payload, error_comment = _fetch_imf_sdmx_il_validated_payload(ref_area, ticker)
    if error_comment is not None or payload is None:
        return [
            ScrapingResult(period=None, data_value=None, comment=error_comment or "")
        ]

    economic_data = _parse_imf_sdmx_il_observations(payload)
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No IMF IL series values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_imf(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.ANNUAL,
    location: str = EconomicDataLocationChoices.US,
) -> list[ScrapingResult]:
    """Get IMF values for one indicator and location (DataMapper or IL SDMX).

    DataMapper: https://www.imf.org/external/datamapper/api/v1/
    IL SDMX: https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IL/
    """
    if ticker in _IMF_DATAMAPPER_TICKERS:
        return _get_imf_datamapper_data(ticker, target_period, frequency, location)
    if ticker in _IMF_SDMX_IL_TICKERS:
        return _get_imf_sdmx_il_data(ticker, target_period, frequency, location)
    return [
        ScrapingResult(
            period=None,
            data_value=None,
            comment=f"Unsupported IMF ticker: {ticker}",
        )
    ]


# __________________________________________________________
# Publication dates (IMF calendars)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_imf(name: str) -> list[datetime]:
    """Get upcoming IMF dates for wired technical names.

    International Liquidity follows the FRED International Reserves release
    calendar (shared monthly reserves release). Fiscal Monitor has no dated next
    slot after the October 2026 edition (April 2027 day not announced yet).
    """
    if name == "International Liquidity":
        return get_publication_dates_from_fred("International Reserves")
    logger.warning(
        f"IMF publication schedule has no dated next slot for technical_name={name}."
    )
    return []
