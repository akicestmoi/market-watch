"""Scrape and ingest economic indicator time series."""

import io
import re
import zipfile
from datetime import date, datetime
from typing import List, NamedTuple, Optional, TypedDict, Union

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.db.models import QuerySet

import core.services as core_services
from core.services import CACHE_MAXSIZE, CACHE_TTL_SECONDS, logger
from economic_overview.models import (
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
)


def get_economic_data_ingestion_lock_key() -> str:
    return "lock:economic_data_ingestion"


INSEE_CSV_NAME_BY_FREQUENCY = {
    EconomicPublicationFrequencyChoices.MONTHLY: "valeurs_mensuelles",
    EconomicPublicationFrequencyChoices.QUARTERLY: "valeurs_trimestrielles",
    EconomicPublicationFrequencyChoices.ANNUAL: "valeurs_annuelles",
}

SOURCE_SCRAP_MAP = {
    EconomicDataSourceChoices.INSEE: lambda t, p, f: _get_data_from_insee(t, p, f),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda t, p, f: _get_data_from_japan_cabinet_office(
        t, p, f
    ),
}


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

    period: Optional[date]
    data_value: Optional[float]
    comment: str


class EconomicData(TypedDict):
    """Economic data dictionnary."""

    indicator: EconomicIndicatorInformationModel
    period: Optional[date]
    data_value: Optional[float]
    comment: Optional[str]


class InseeValuesLoadResult(NamedTuple):
    """INSEE CSV load outcome."""

    dataframe: Optional[pd.DataFrame]
    error_comment: str


def _parse_insee_period(period_str: str, frequency: str) -> date:
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
    frequency: str,
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
    insee_url = f"https://bdm.insee.fr/series/{ticker}/csv"
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
    dataframe: pd.DataFrame, frequency: str
) -> List[ScrapingResult]:
    """Parse all economic data rows from an INSEE values dataframe."""
    header_row = dataframe.index[dataframe["Libellé"] == "Période"][0]
    economic_data: List[ScrapingResult] = []
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
def _get_data_from_insee(
    ticker: str,
    target_period: Optional[str] = None,
    frequency: str = EconomicPublicationFrequencyChoices.MONTHLY,
) -> List[ScrapingResult]:
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


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_data_from_japan_cabinet_office(
    ticker: str,
    target_period: Optional[str] = None,
    frequency: str = EconomicPublicationFrequencyChoices.QUARTERLY,
) -> List[ScrapingResult]:
    """Get data from Japan Cabinet Office."""
    raise NotImplementedError("Not implemented.")


def _get_economic_data(
    indicator: EconomicIndicatorInformationModel, period: Optional[str] = None
) -> EconomicData:
    """Get economic data from scraping function (latest or a specific period)."""
    scraping_function = SOURCE_SCRAP_MAP.get(indicator.source)
    economic_data: List[ScrapingResult] = (
        scraping_function(indicator.ticker, period, indicator.frequency)
        if scraping_function
        else [
            ScrapingResult(
                period=None, data_value=None, comment="No scraping function found."
            )
        ]
    )
    scraping_result = (
        economic_data[0]
        if economic_data
        else ScrapingResult(period=None, data_value=None, comment="No value found.")
    )
    if not scraping_result.get("data_value"):
        logger.warning("No value found.")
    return EconomicData(
        indicator=indicator,
        period=scraping_result.get("period"),
        data_value=scraping_result.get("data_value"),
        comment=scraping_result.get("comment"),
    )


def _upsert_economic_data_item(
    indicator: EconomicIndicatorInformationModel,
    period: Optional[date],
    data_value: Optional[float],
    comment: Optional[str],
) -> bool:
    """Upsert one economic data item and return whether a value was stored."""
    is_success = data_value is not None
    core_services.upsert_with_logs(
        model=EconomicDataModel,
        log_model=EconomicDataUpdateLogModel,
        lookup_kwargs={"indicator": indicator, "period": period},
        updates={
            "logs": f"Automated data update on {indicator.ticker}.",
            "data_value": data_value,
            "comment": comment,
        },
        logging_on_fields=["data_value"],
        none_skip_fields=["data_value"],
    )
    return is_success


def _ingest_single_economic_data(
    indicator: EconomicIndicatorInformationModel, target_period: Optional[str] = None
) -> bool:
    """Ingest a single (latest or period-specific) economic data item."""
    data = _get_economic_data(indicator, target_period)
    return _upsert_economic_data_item(
        indicator=data["indicator"],
        period=data["period"],
        data_value=data["data_value"],
        comment=data["comment"],
    )


class SpecificEconomicDataNotUpdatedItem(TypedDict):
    """Specific Economic Data Not Updated."""

    indicator: str
    period: str


def ingest_latest_economic_data(
    indicators: Union[
        List[EconomicIndicatorInformationModel],
        QuerySet[EconomicIndicatorInformationModel],
    ],
) -> List[str]:
    """Ingest the latest economic data for each indicator."""
    economic_data_not_updated = []
    for indicator in indicators:
        logger.info(f"Ingesting latest economic data for indicator: {indicator.name}")
        is_success = _ingest_single_economic_data(indicator)
        if not is_success:
            economic_data_not_updated.append(indicator.name)
    return economic_data_not_updated


def ingest_specific_economic_data(
    indicators: Union[
        List[EconomicIndicatorInformationModel],
        QuerySet[EconomicIndicatorInformationModel],
    ],
    periods: List[List[str]],
) -> List[SpecificEconomicDataNotUpdatedItem]:
    """Ingest specific economic data for indicators and target periods."""
    economic_data_not_updated = []
    for indicator, period_list in zip(indicators, periods):
        for target_period in period_list:
            logger.info(
                f"Ingesting economic data for indicator: {indicator.name} and period: {target_period}"
            )
            is_success = _ingest_single_economic_data(indicator, target_period)
            if not is_success:
                economic_data_not_updated.append(
                    SpecificEconomicDataNotUpdatedItem(
                        indicator=indicator.name,
                        period=target_period,
                    )
                )
    return economic_data_not_updated


def ingest_historical_economic_data(
    indicators: Union[
        List[EconomicIndicatorInformationModel],
        QuerySet[EconomicIndicatorInformationModel],
    ],
    start_date: date,
    end_date: date,
) -> List[SpecificEconomicDataNotUpdatedItem]:
    """Ingest all economic data in [start_date, end_date] for each indicator."""
    economic_data_not_updated: List[SpecificEconomicDataNotUpdatedItem] = []
    window_label = f"{start_date.isoformat()}/{end_date.isoformat()}"
    for indicator in indicators:
        logger.info(
            f"Ingesting historical economic data for indicator: {indicator.name} "
            f"from {start_date} to {end_date}"
        )
        scraping_function = SOURCE_SCRAP_MAP.get(indicator.source)
        if not scraping_function:
            economic_data_not_updated.append(
                SpecificEconomicDataNotUpdatedItem(
                    indicator=indicator.name,
                    period=window_label,
                )
            )
            continue

        economic_data = scraping_function(indicator.ticker, None, indicator.frequency)
        has_been_upserted = False
        for economic_data_item in economic_data:
            period = economic_data_item.get("period")
            data_value = economic_data_item.get("data_value")
            if period is None or data_value is None:
                continue
            if not (start_date <= period <= end_date):
                continue
            _upsert_economic_data_item(
                indicator=indicator,
                period=period,
                data_value=data_value,
                comment=economic_data_item.get("comment"),
            )
            has_been_upserted = True

        if not has_been_upserted:
            economic_data_not_updated.append(
                SpecificEconomicDataNotUpdatedItem(
                    indicator=indicator.name,
                    period=window_label,
                )
            )
    return economic_data_not_updated
