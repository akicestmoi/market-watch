"""Scrape INSEE (BDM) economic series and the INSEE publication schedule."""

import io
import json
import logging
import re
import zipfile
from datetime import date, datetime
from typing import NamedTuple, TypedDict

import pandas as pd
import requests
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    INSEE_CALENDAR_TITLE_BY_TECHNICAL_NAME,
    INSEE_CSV_NAME_BY_FREQUENCY,
    INSEE_HH_FCE_CHAINED_VOLUME_TICKER,
    INSEE_HH_FCE_CURRENT_PRICE_TICKER,
    INSEE_PUBLICATION_SCHEDULE_URL,
    INSEE_RDB_NOMINAL_TICKER,
    INSEE_REAL_RDB_TICKER,
    INSEE_SERIES_CSV_URL_TEMPLATE,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    deflate_scraping_results_by_period,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (INSEE BDM series)
# __________________________________________________________


class _InseeValuesLoadResult(NamedTuple):
    """INSEE CSV load outcome."""

    dataframe: pd.DataFrame | None
    error_comment: str


def _parse_insee_period(
    period_str: str, frequency: EconomicPublicationFrequencyChoices
) -> date:
    """Parse an INSEE period label into a date (first day of the period)."""
    period_str = str(period_str).strip()
    if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
        return datetime.strptime(period_str, "%Y-%m").date()
    if frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
        # French CSV uses YYYY-Tn; SDMX uses YYYY-Qn.
        match = re.fullmatch(r"(\d{4})-[TQ]([1-4])", period_str, flags=re.IGNORECASE)
        if not match:
            raise ValueError(f"Invalid quarterly period: {period_str}")
        year = int(match.group(1))
        quarter = int(match.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)
    if frequency == EconomicPublicationFrequencyChoices.ANNUAL:
        return datetime.strptime(period_str, "%Y").date()
    raise ValueError(f"Unsupported frequency: {frequency}")


def _load_insee_values_dataframe(
    ticker: str,
    frequency: EconomicPublicationFrequencyChoices,
    year_start: int,
    year_end: int,
) -> _InseeValuesLoadResult:
    """Download and parse the INSEE values CSV for a ticker."""
    expected_values_csv_name = INSEE_CSV_NAME_BY_FREQUENCY.get(frequency)
    if not expected_values_csv_name:
        return _InseeValuesLoadResult(
            None, f"Unsupported frequency for INSEE scrape: {frequency}"
        )

    params = {
        "lang": "fr",
        "ordre": "antechronologique",
        "anneeDebut": str(year_start),
        "anneeFin": str(year_end),
        "revision": "sansrevisions",
    }
    insee_url = INSEE_SERIES_CSV_URL_TEMPLATE.format(ticker=ticker)
    response = requests.get(insee_url, params=params)
    if response.status_code >= 400:
        logger.warning(f"Error scraping INSEE data: {response.text}")
        return _InseeValuesLoadResult(None, response.text)

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_archive:
            matching_values_csv_files = [
                archive_member_name
                for archive_member_name in zip_archive.namelist()
                if expected_values_csv_name in archive_member_name.lower()
            ]
            if not matching_values_csv_files:
                return _InseeValuesLoadResult(
                    None, f"No '{expected_values_csv_name}' CSV found in archive."
                )
            # The BDM ZIP has one values CSV matching the frequency basename.
            with zip_archive.open(matching_values_csv_files[0]) as values_csv_file:
                dataframe = pd.read_csv(values_csv_file, encoding="utf-8", sep=";")
    except Exception as exc:
        return _InseeValuesLoadResult(None, f"Error reading ZIP content: {exc}")

    if (
        "Libellé" not in dataframe.columns
        or "Période" not in dataframe["Libellé"].values
    ):
        return _InseeValuesLoadResult(None, "Data is not in the expected format.")

    # Index 0 is the first (only) row labeled "Période" in the "Libellé" column.
    header_row = dataframe.index[dataframe["Libellé"] == "Période"][0]
    if len(dataframe) <= header_row + 1:
        return _InseeValuesLoadResult(None, "No data found.")

    return _InseeValuesLoadResult(dataframe, "")


def _parse_economic_data_from_insee_dataframe(
    dataframe: pd.DataFrame, frequency: EconomicPublicationFrequencyChoices
) -> list[ScrapingResult]:
    """Parse all economic data values from an INSEE values dataframe."""
    # Index 0 is the first (only) row labeled "Période" in the "Libellé" column.
    header_row = dataframe.index[dataframe["Libellé"] == "Période"][0]
    economic_data: list[ScrapingResult] = []
    for row_index in range(header_row + 1, len(dataframe)):
        period_label = str(dataframe.iloc[row_index, 0]).strip()
        raw_value = str(dataframe.iloc[row_index, 1]).strip()
        if not period_label or period_label.lower() == "nan":
            continue
        if not raw_value or raw_value.lower() in {"nan", ""}:
            continue
        try:
            period = _parse_insee_period(period_label, frequency)
            data_value = float(raw_value)
        except ValueError:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    return economic_data


def _build_insee_implicit_deflator_series(
    current_price_series: list[ScrapingResult],
    chained_volume_series: list[ScrapingResult],
) -> list[ScrapingResult]:
    """Build a current-price / chained-volume implicit deflator on shared periods."""
    # Usage of dict: keys are observation periods; values are chained volumes.
    chained_volume_by_period: dict[date, float] = {}
    for scraping_result in chained_volume_series:
        period = scraping_result["period"]
        data_value = scraping_result["data_value"]
        if period is None or data_value is None or data_value == 0:
            continue
        chained_volume_by_period[period] = data_value

    deflator_series: list[ScrapingResult] = []
    for scraping_result in current_price_series:
        period = scraping_result["period"]
        current_price_value = scraping_result["data_value"]
        if period is None or current_price_value is None:
            continue
        chained_volume_value = chained_volume_by_period.get(period)
        if chained_volume_value is None:
            continue
        deflator_series.append(
            ScrapingResult(
                period=period,
                data_value=current_price_value / chained_volume_value,
                comment="",
            )
        )
    deflator_series.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return deflator_series


def _get_insee_real_household_disposable_income_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Scrape nominal RDB and deflate it with the household FCE implicit deflator."""
    nominal_series = get_data_from_insee(
        INSEE_RDB_NOMINAL_TICKER, target_period, frequency
    )
    current_price_series = get_data_from_insee(
        INSEE_HH_FCE_CURRENT_PRICE_TICKER, target_period, frequency
    )
    chained_volume_series = get_data_from_insee(
        INSEE_HH_FCE_CHAINED_VOLUME_TICKER, target_period, frequency
    )
    deflator_series = _build_insee_implicit_deflator_series(
        current_price_series, chained_volume_series
    )
    real_income_series = deflate_scraping_results_by_period(
        nominal_series, deflator_series
    )
    if not real_income_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No INSEE real household disposable-income values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        real_income_series, target_period, frequency
    )


def _get_insee_scraping_result_for_target_label(
    dataframe: pd.DataFrame,
    target_period: str,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Return one scraping result for a dataframe row labeled with the target period."""
    target_row_index = dataframe.index[dataframe["Libellé"] == target_period]
    if target_row_index.empty:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="Target period not found."
            )
        ]
    # Index 0 is the first (only) dataframe row whose "Libellé" equals the target period.
    target_row = target_row_index[0]
    period = _parse_insee_period(str(dataframe.iloc[target_row, 0]), frequency)
    data_value = float(str(dataframe.iloc[target_row, 1]))
    return [ScrapingResult(period=period, data_value=data_value, comment="")]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_insee(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get INSEE economic data (all periods, or a single matching period label).

    Note: The data given by INSEE is a zip file containing:
    - caractéristiques.csv
    - valeurs_mensuelles.csv / valeurs_trimestrielles.csv / valeurs_annuelles.csv

    Real household disposable income ('011794746_real') is nominal RDB divided
    by the household final-consumption expenditure implicit deflator
    (current-price / chained-volume P3).

    Source: https://bdm.insee.fr/
    Docs: https://www.insee.fr/fr/statistiques/serie/{ticker}
    """
    if ticker == INSEE_REAL_RDB_TICKER:
        return _get_insee_real_household_disposable_income_data(
            target_period, frequency
        )

    load_result = _load_insee_values_dataframe(
        ticker=ticker,
        frequency=frequency,
        year_start=2010,
        year_end=date.today().year,
    )
    if load_result.error_comment:
        return [
            ScrapingResult(
                period=None, data_value=None, comment=load_result.error_comment
            )
        ]

    assert load_result.dataframe is not None
    if not target_period:
        return _parse_economic_data_from_insee_dataframe(
            load_result.dataframe, frequency
        )

    return _get_insee_scraping_result_for_target_label(
        load_result.dataframe, target_period, frequency
    )


# __________________________________________________________
# Publication dates (INSEE schedule)
# __________________________________________________________


class _InseeAgendaSortField(TypedDict):
    """Sort field for the INSEE agenda-diffusion search request."""

    field: str
    order: str


class _InseeAgendaRequest(TypedDict):
    """POST body for https://www.insee.fr/fr/agenda-diffusion."""

    q: str
    start: int
    sortFields: list[_InseeAgendaSortField]
    filters: list[str]
    rows: int
    facetsQuery: list[str]


class _InseeAgendaFacetteConjoncture(TypedDict, total=False):
    """Nested INSEE facetteConjoncture block (fields we read)."""

    libelleEn: str


class _InseeAgendaFamille(TypedDict, total=False):
    """Nested INSEE famille block (fields we read)."""

    facetteConjoncture: _InseeAgendaFacetteConjoncture


class _InseeAgendaDocument(TypedDict, total=False):
    """One INSEE agenda document (fields we read)."""

    famille: _InseeAgendaFamille
    embargo: str


class _InseeAgendaResponse(TypedDict, total=False):
    """INSEE agenda-diffusion JSON root (fields we read)."""

    documents: list[_InseeAgendaDocument]


class _InseePublicationScheduleRow(TypedDict):
    """One normalized INSEE publication schedule entry before DataFrame load."""

    name: str
    publication_date: str | None


_INSEE_AGENDA_RESPONSE_ADAPTER = TypeAdapter(_InseeAgendaResponse)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_insee_publication_schedule() -> pd.DataFrame:
    """Get INSEE publication schedule.

    Source: https://www.insee.fr/fr/agenda-diffusion
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
    payload = _InseeAgendaRequest(
        q="*:*",
        start=0,
        sortFields=[{"field": "dateEmbargo_dt", "order": "asc"}],
        filters=[],
        rows=500,
        facetsQuery=[],
    )
    response = requests.post(INSEE_PUBLICATION_SCHEDULE_URL, json=payload)
    if response.status_code >= 400:
        logger.warning(f"Error scraping INSEE publication schedule: {response.text}")
        return default_df

    try:
        raw_payload = json.loads(response.content)
        agenda = _INSEE_AGENDA_RESPONSE_ADAPTER.validate_python(raw_payload)
    except (TypeError, json.JSONDecodeError, ValidationError):
        logger.warning("Invalid INSEE publication schedule JSON")
        return default_df

    records: list[_InseePublicationScheduleRow] = []
    for document in agenda.get("documents", []):
        famille = document.get("famille", {})
        facette = famille.get("facetteConjoncture", {}) if famille else {}
        records.append(
            _InseePublicationScheduleRow(
                name=facette.get("libelleEn", "") if facette else "",
                publication_date=document.get("embargo"),
            )
        )

    df = pd.DataFrame(records)
    if df.empty:
        return default_df
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_insee(name: str) -> list[datetime]:
    """Get upcoming publication dates from INSEE."""
    calendar_title = INSEE_CALENDAR_TITLE_BY_TECHNICAL_NAME.get(name, name)
    publication_schedule = _get_insee_publication_schedule()
    publication_dates = publication_schedule[
        publication_schedule["name"] == calendar_title
    ]["publication_date"]
    publication_datetimes = [
        pd_timestamp.to_pydatetime() for pd_timestamp in publication_dates.tolist()
    ]
    return filter_upcoming_publication_dates(publication_datetimes)
