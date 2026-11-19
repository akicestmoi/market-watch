"""Scrape OECD Economic Outlook and Productivity SDMX series."""

import logging
import re
from datetime import date, datetime
from typing import NamedTuple, TypedDict

import requests
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.common import EconomicDataLocationChoices
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    OECD_ECONOMIC_OUTLOOK_PARIS_RELEASE_DATETIMES,
    OECD_REF_AREA_BY_LOCATION,
    OECD_SERIES_BY_TICKER,
    OecdSeriesConfig,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)
from economic_overview.services.scrapers.stat_of_jp import (
    get_publication_dates_from_estat_for_technical_name,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (Economic Outlook and productivity)
# __________________________________________________________


class _OecdSdmxDimensionValue(TypedDict, total=False):
    """One coded value inside an OECD SDMX observation dimension."""

    id: str
    name: str


class _OecdSdmxDimension(TypedDict, total=False):
    """One observation dimension (REF_AREA, MEASURE, FREQ, TIME_PERIOD)."""

    id: str
    values: list[_OecdSdmxDimensionValue]


class _OecdSdmxStructureDimensions(TypedDict, total=False):
    """OECD SDMX-JSON structure.dimensions block."""

    observation: list[_OecdSdmxDimension]


class _OecdSdmxStructure(TypedDict, total=False):
    """OECD SDMX-JSON structure block."""

    dimensions: _OecdSdmxStructureDimensions


class _OecdSdmxDataSet(TypedDict, total=False):
    """One OECD SDMX-JSON dataSet entry."""

    # Usage of dict: keys are colon-joined observation coordinates; values are
    # observation arrays whose first element is the numeric measure.
    observations: dict[str, list[float | int | None]]


class _OecdSdmxDataBlock(TypedDict, total=False):
    """OECD SDMX-JSON data block."""

    dataSets: list[_OecdSdmxDataSet]
    structure: _OecdSdmxStructure


class _OecdSdmxPayload(TypedDict, total=False):
    """OECD SDMX-JSON data message root (fields we read)."""

    data: _OecdSdmxDataBlock


_OECD_SDMX_ADAPTER = TypeAdapter(_OecdSdmxPayload)

_OECD_REQUEST_HEADERS: dict[str, str] = {
    "Accept": "application/vnd.sdmx.data+json;charset=utf-8;version=1.0",
}


class _DBnomicsSeriesDoc(TypedDict, total=False):
    """One DBnomics series document (fields we read)."""

    period: list[str]
    value: list[float | int | None]


class _DBnomicsSeriesBlock(TypedDict, total=False):
    """DBnomics 'series' block."""

    docs: list[_DBnomicsSeriesDoc]


class _DBnomicsSeriesPayload(TypedDict, total=False):
    """DBnomics series API root (fields we read)."""

    series: _DBnomicsSeriesBlock


_DBNOMICS_SERIES_ADAPTER = TypeAdapter(_DBnomicsSeriesPayload)


def _parse_oecd_time_period(time_label: str) -> date | None:
    """Parse OECD TIME_PERIOD labels ('YYYY' / 'YYYY-Qn' / 'YYYY-MM')."""
    monthly_match = re.fullmatch(r"(\d{4})-(\d{2})", time_label)
    if monthly_match:
        year = int(monthly_match.group(1))
        month = int(monthly_match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
        return None
    quarterly_match = re.fullmatch(r"(\d{4})-Q([1-4])", time_label)
    if quarterly_match:
        year = int(quarterly_match.group(1))
        quarter = int(quarterly_match.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)
    annual_match = re.fullmatch(r"(\d{4})", time_label)
    if annual_match:
        return date(int(annual_match.group(1)), 1, 1)
    return None


def _parse_oecd_sdmx_observations(
    payload: _OecdSdmxPayload,
) -> list[ScrapingResult]:
    """Parse OECD SDMX-JSON observations into scraping results."""
    data_block = payload.get("data") or {}
    data_sets = data_block.get("dataSets") or []
    if not data_sets:
        return []
    # One series key is requested, so dataSets has a single series payload.
    observations = data_sets[0].get("observations") or {}
    structure = data_block.get("structure") or {}
    dimensions = (structure.get("dimensions") or {}).get("observation") or []
    time_dimension_index = next(
        (
            index
            for index, dimension in enumerate(dimensions)
            if dimension.get("id") == "TIME_PERIOD"
        ),
        None,
    )
    if time_dimension_index is None:
        return []

    economic_data: list[ScrapingResult] = []
    today = date.today()
    for coordinate_key, observation_values in observations.items():
        if not observation_values:
            continue
        # OECD SDMX returns one scalar in the first observation slot.
        raw_value = observation_values[0]
        if raw_value is None:
            continue
        try:
            coordinates = [int(part) for part in coordinate_key.split(":")]
            time_dimension_values = dimensions[time_dimension_index].get("values") or []
            time_value = time_dimension_values[coordinates[time_dimension_index]]
            time_label = time_value.get("id") or time_value.get("name") or ""
            period = _parse_oecd_time_period(time_label)
            data_value = float(raw_value)
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        if period is None:
            continue
        # Drop EO / dashboard projections beyond the current calendar period.
        if period > today:
            continue
        economic_data.append(
            ScrapingResult(
                period=period,
                data_value=data_value,
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _parse_dbnomics_series_observations(
    payload: _DBnomicsSeriesPayload,
    *,
    start_period: str,
) -> list[ScrapingResult]:
    """Parse DBnomics series observations into scraping results."""
    series_docs = (payload.get("series") or {}).get("docs") or []
    if not series_docs:
        return []
    # One series_code is requested, so docs has that single series.
    series_doc = series_docs[0]
    period_labels = series_doc.get("period") or []
    observation_values = series_doc.get("value") or []
    start_period_date = _parse_oecd_time_period(start_period)

    economic_data: list[ScrapingResult] = []
    today = date.today()
    for period_label, raw_value in zip(period_labels, observation_values, strict=False):
        if raw_value is None:
            continue
        period = _parse_oecd_time_period(str(period_label))
        if period is None:
            continue
        if start_period_date is not None and period < start_period_date:
            continue
        if period > today:
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


class _OecdUrlFormatBuild(NamedTuple):
    """URL format kwargs, or a scrape error when the location is unsupported."""

    # Usage of dict: SDMX / DBnomics URL format kwargs from optional config fields.
    format_kwargs: dict[str, str] | None
    error: ScrapingResult | None


def _build_oecd_url_format_kwargs(
    series_config: OecdSeriesConfig,
    location: str,
) -> _OecdUrlFormatBuild:
    """Build URL format kwargs for one OECD series config."""
    # Usage of dict: SDMX / DBnomics URL format kwargs from optional config fields.
    url_format_kwargs: dict[str, str] = {}
    if "measure" in series_config:
        ref_area = OECD_REF_AREA_BY_LOCATION.get(location)
        if ref_area is None:
            return _OecdUrlFormatBuild(
                format_kwargs=None,
                error=ScrapingResult(
                    period=None,
                    data_value=None,
                    comment=f"Unsupported OECD location: {location}",
                ),
            )
        url_format_kwargs["ref_area"] = ref_area
        url_format_kwargs["measure"] = series_config["measure"]
    if "series_key_template" in series_config:
        series_key_template = series_config["series_key_template"]
        if "{ref_area}" in series_key_template:
            ref_area = OECD_REF_AREA_BY_LOCATION.get(location)
            if ref_area is None:
                return _OecdUrlFormatBuild(
                    format_kwargs=None,
                    error=ScrapingResult(
                        period=None,
                        data_value=None,
                        comment=f"Unsupported OECD location: {location}",
                    ),
                )
            series_key_template = series_key_template.format(ref_area=ref_area)
        url_format_kwargs["series_key"] = series_key_template
    return _OecdUrlFormatBuild(format_kwargs=url_format_kwargs, error=None)


def _download_oecd_dbnomics_observations(
    url: str,
    *,
    start_period: str,
) -> list[ScrapingResult] | ScrapingResult:
    """Fetch and parse one DBnomics OECD series mirror URL."""
    response = requests.get(
        url,
        headers={"Accept": "application/json"},
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping OECD via DBnomics: {response.text[:500]}")
        return ScrapingResult(period=None, data_value=None, comment=response.text[:500])

    try:
        payload = _DBNOMICS_SERIES_ADAPTER.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        return ScrapingResult(
            period=None,
            data_value=None,
            comment=f"Invalid DBnomics series JSON: {exc}",
        )

    return _parse_dbnomics_series_observations(payload, start_period=start_period)


# Usage of tuple: parsed observations and an error comment when the fetch failed.
def _fetch_oecd_primary_sdmx_observations(
    primary_url: str,
    *,
    start_period: str,
    ticker: str,
) -> tuple[list[ScrapingResult], str]:
    """Fetch one OECD SDMX URL and return parsed observations or an error comment."""
    response = requests.get(
        primary_url,
        params={
            "startPeriod": start_period,
            "dimensionAtObservation": "AllDimensions",
        },
        headers=_OECD_REQUEST_HEADERS,
        timeout=60,
    )
    if response.status_code < 400:
        try:
            payload = _OECD_SDMX_ADAPTER.validate_python(response.json())
            return _parse_oecd_sdmx_observations(payload), ""
        except (ValueError, ValidationError) as exc:
            logger.warning(f"Invalid OECD SDMX JSON for {ticker}: {exc}")
            return [], f"Invalid OECD SDMX JSON: {exc}"
    sdmx_error_comment = response.text[:500]
    logger.warning(f"Error scraping OECD SDMX data for {ticker}: {sdmx_error_comment}")
    return [], sdmx_error_comment


def _get_oecd_observations_with_dbnomics_fallback(
    series_config: OecdSeriesConfig,
    url_format_kwargs: dict[str, str],
    ticker: str,
) -> list[ScrapingResult]:
    """Return SDMX observations, or DBnomics fallback, or a single-error list."""
    primary_url = series_config["url_template"].format(**url_format_kwargs)
    start_period = series_config["start_period"]
    economic_data, sdmx_error_comment = _fetch_oecd_primary_sdmx_observations(
        primary_url, start_period=start_period, ticker=ticker
    )
    if not economic_data and "fallback_url_template" in series_config:
        fallback_url = series_config["fallback_url_template"].format(
            **url_format_kwargs
        )
        fallback_result = _download_oecd_dbnomics_observations(
            fallback_url, start_period=start_period
        )
        if isinstance(fallback_result, list):
            economic_data = fallback_result
        else:
            return [fallback_result]
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=sdmx_error_comment or "No OECD series values found.",
            )
        ]
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_oecd(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.ANNUAL,
    location: str = EconomicDataLocationChoices.US,
) -> list[ScrapingResult]:
    """Get OECD SDMX values for one configured ticker and location.

    Supports Economic Outlook measure keys, Short-Term Economic Statistics
    INDSERV series keys, and Productivity Database labour-compensation indexes.
    When an OECD SDMX dataflow is unavailable (e.g. DF_PDB_GR HTTP 500), a
    configured DBnomics mirror of the same OECD series is tried next.

    Source: https://sdmx.oecd.org/public/rest/data/
    """
    series_config = OECD_SERIES_BY_TICKER.get(ticker)
    if series_config is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported OECD ticker: {ticker}",
            )
        ]
    if frequency != series_config["frequency"]:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    f"Unsupported frequency for OECD ticker {ticker}: {frequency}"
                ),
            )
        ]

    url_format_build = _build_oecd_url_format_kwargs(series_config, location)
    if url_format_build.error is not None:
        return [url_format_build.error]
    # format_kwargs is set whenever error is None.
    url_format_kwargs = url_format_build.format_kwargs or {}

    economic_data = _get_oecd_observations_with_dbnomics_fallback(
        series_config, url_format_kwargs, ticker
    )
    # A failed scrape returns exactly one empty error result at index 0.
    if (
        len(economic_data) == 1
        and economic_data[0]["period"] is None
        and economic_data[0]["data_value"] is None
    ):
        return economic_data
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (OECD calendars)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_oecd(name: str) -> list[datetime]:
    """Get upcoming OECD dates for Economic Outlook and MEI retail.

    Economic Outlook uses the published Paris wall-time slots in config (the
    live media-advisory HTML is often blocked). Japan MEI retail volume follows
    the e-Stat commerce preliminary releases that feed the OECD series.
    """
    if name == "Main Economic Indicators":
        return get_publication_dates_from_estat_for_technical_name(name)
    if name == "Economic Outlook Output Gap":
        publication_datetimes = [
            convert_local_wall_time_to_utc(
                year,
                month,
                day,
                hour,
                minute,
                source_timezone="Europe/Paris",
            )
            for year, month, day, hour, minute in (
                OECD_ECONOMIC_OUTLOOK_PARIS_RELEASE_DATETIMES
            )
        ]
        return filter_upcoming_publication_dates(publication_datetimes)
    logger.warning(
        f"OECD publication schedule has no mapping for technical_name={name}."
    )
    return []
