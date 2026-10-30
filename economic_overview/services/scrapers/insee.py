"""Scrape INSEE (BDM) economic series and the INSEE publication schedule."""

import io
import json
import re
import zipfile
from datetime import date, datetime
from typing import NamedTuple, TypedDict

import pandas as pd
import requests
from cachetools.func import ttl_cache
from pydantic import TypeAdapter, ValidationError

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import logger
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.config import (
    INSEE_CSV_NAME_BY_FREQUENCY,
    INSEE_PUBLICATION_SCHEDULE_URL,
    INSEE_SERIES_CSV_URL_TEMPLATE,
)
from economic_overview.services.scrapers.common import ScrapingResult


class InseeValuesLoadResult(NamedTuple):
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
) -> InseeValuesLoadResult:
    """Download and parse the INSEE values CSV for a ticker."""
    expected_values_csv_name = INSEE_CSV_NAME_BY_FREQUENCY.get(frequency)
    if not expected_values_csv_name:
        return InseeValuesLoadResult(
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
        return InseeValuesLoadResult(None, response.text)

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_archive:
            matching_values_csv_files = [
                archive_member_name
                for archive_member_name in zip_archive.namelist()
                if expected_values_csv_name in archive_member_name.lower()
            ]
            if not matching_values_csv_files:
                return InseeValuesLoadResult(
                    None, f"No '{expected_values_csv_name}' CSV found in archive."
                )
            with zip_archive.open(matching_values_csv_files[0]) as values_csv_file:
                dataframe = pd.read_csv(values_csv_file, encoding="utf-8", sep=";")
    except Exception as exc:
        return InseeValuesLoadResult(None, f"Error reading ZIP content: {exc}")

    if (
        "Libellé" not in dataframe.columns
        or "Période" not in dataframe["Libellé"].values
    ):
        return InseeValuesLoadResult(None, "Data is not in the expected format.")

    header_row = dataframe.index[dataframe["Libellé"] == "Période"][0]
    if len(dataframe) <= header_row + 1:
        return InseeValuesLoadResult(None, "No data found.")

    return InseeValuesLoadResult(dataframe, "")


def _parse_economic_data_from_insee_dataframe(
    dataframe: pd.DataFrame, frequency: EconomicPublicationFrequencyChoices
) -> list[ScrapingResult]:
    """Parse all economic data rows from an INSEE values dataframe."""
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


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_insee(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get INSEE economic data (all rows, or a single matching period label).

    Note: The data given by INSEE is a zip file containing:
    - caractéristiques.csv
    - valeurs_mensuelles.csv / valeurs_trimestrielles.csv / valeurs_annuelles.csv

    Source: https://bdm.insee.fr/
    Docs: https://www.insee.fr/fr/statistiques/serie/{ticker}
    """
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

    target_row_index = load_result.dataframe.index[
        load_result.dataframe["Libellé"] == target_period
    ]
    if target_row_index.empty:
        return [
            ScrapingResult(
                period=None, data_value=None, comment="Target period not found."
            )
        ]
    target_row = target_row_index[0]
    period = _parse_insee_period(
        str(load_result.dataframe.iloc[target_row, 0]), frequency
    )
    data_value = float(str(load_result.dataframe.iloc[target_row, 1]))
    return [ScrapingResult(period=period, data_value=data_value, comment="")]


class InseeAgendaSortField(TypedDict):
    """Sort field for the INSEE agenda-diffusion search request."""

    field: str
    order: str


class InseeAgendaRequest(TypedDict):
    """POST body for https://www.insee.fr/fr/agenda-diffusion."""

    q: str
    start: int
    sortFields: list[InseeAgendaSortField]
    filters: list[str]
    rows: int
    facetsQuery: list[str]


class InseeAgendaFacetteConjoncture(TypedDict, total=False):
    """Nested INSEE facetteConjoncture block (fields we read)."""

    libelleEn: str


class InseeAgendaFamille(TypedDict, total=False):
    """Nested INSEE famille block (fields we read)."""

    facetteConjoncture: InseeAgendaFacetteConjoncture


class InseeAgendaDocument(TypedDict, total=False):
    """One INSEE agenda document (fields we read)."""

    famille: InseeAgendaFamille
    embargo: str


class InseeAgendaResponse(TypedDict, total=False):
    """INSEE agenda-diffusion JSON root (fields we read)."""

    documents: list[InseeAgendaDocument]


class InseePublicationScheduleRow(TypedDict):
    """One normalized INSEE publication schedule row before DataFrame load."""

    name: str
    publication_date: str | None


_INSEE_AGENDA_RESPONSE_ADAPTER = TypeAdapter(InseeAgendaResponse)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_insee_publication_schedule() -> pd.DataFrame:
    """Get INSEE publication schedule.

    Source: https://www.insee.fr/fr/agenda-diffusion
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
    payload = InseeAgendaRequest(
        q="*:*",
        start=0,
        sortFields=[{"field": "dateEmbargo_dt", "order": "asc"}],
        filters=[],
        rows=100,
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

    records: list[InseePublicationScheduleRow] = []
    for document in agenda.get("documents", []):
        famille = document.get("famille", {})
        facette = famille.get("facetteConjoncture", {}) if famille else {}
        records.append(
            InseePublicationScheduleRow(
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
    """Get publication dates from INSEE."""
    publication_schedule = _get_insee_publication_schedule()
    publication_dates = publication_schedule[publication_schedule["name"] == name][
        "publication_date"
    ]
    return [
        pd_timestamp.to_pydatetime() for pd_timestamp in publication_dates.tolist()[:2]
    ]
