import io
import zipfile
from datetime import date, datetime
from typing import List, Optional, TypedDict, Union

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
)

SOURCE_SCRAP_MAP = {
    EconomicDataSourceChoices.INSEE: lambda t, p: _get_data_from_insee(t, p),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda t, p: _get_data_from_japan_cabinet_office(
        t, p
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


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_data_from_insee(
    ticker: str, target_period: Optional[str] = None
) -> ScrapingResult:
    """Get data from INSEE.

    Note: The data given by INSEE is a zip file containing 2 files:
    - caractéristiques.csv
    - valeurs_mensuelles.csv (which contains statistics values)

    Source: https://bdm.insee.fr/
    Docs: https://www.insee.fr/fr/statistiques/serie/{ticker}
    """
    params = {
        "lang": "fr",
        "ordre": "antechronologique",
        "transposition": "donneescolonne",
        "anneeDebut": "2010",
        "anneeFin": str(date.today().year),
        "revision": "sansrevisions",
    }
    INSEE_URL = f"https://bdm.insee.fr/series/{ticker}/csv"
    response = requests.get(INSEE_URL, params=params)
    if response.status_code >= 400:
        logger.warning(f"Error scraping INSEE data: {response.text}")
        return ScrapingResult(period=None, data_value=None, comment=response.text)

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            csv_files = [n for n in zf.namelist() if "valeurs_mensuelles" in n.lower()]
            if not csv_files:
                return ScrapingResult(
                    period=None,
                    data_value=None,
                    comment="No 'valeurs_mensuelles' CSV found in archive.",
                )
            with zf.open(csv_files[0]) as f:
                df = pd.read_csv(f, encoding="utf-8", sep=";")
    except Exception as exc:
        return ScrapingResult(
            period=None, data_value=None, comment=f"Error reading ZIP content: {exc}"
        )

    if (
        "Libellé" not in df.columns
        or "Période" not in "Période" not in df["Libellé"].values
    ):
        return ScrapingResult(
            period=None, data_value=None, comment="Data is not in the expected format."
        )

    header_row = df.index[df["Libellé"] == "Période"][0]
    if len(df) <= header_row + 1:
        return ScrapingResult(period=None, data_value=None, comment="No data found.")

    if not target_period:
        target_row = header_row + 1
    else:
        target_row = df.index[df["Libellé"] == target_period]
        if target_row.empty:
            return ScrapingResult(
                period=None, data_value=None, comment="Target period not found."
            )
        target_row = target_row[0]

    period = datetime.strptime(str(df.iloc[target_row, 0]), "%Y-%m").date()
    data_value = float(str(df.iloc[target_row, 1]))
    return ScrapingResult(period=period, data_value=data_value, comment="")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_data_from_japan_cabinet_office(
    ticker: str, target_period: Optional[str] = None
) -> ScrapingResult:
    """Get data from Japan Cabinet Office."""
    raise NotImplementedError("Not implemented.")


def _get_economic_data(
    indicator: EconomicIndicatorInformationModel, period: Optional[str] = None
) -> EconomicData:
    """Get economic data from scraping function."""
    scraping_function = SOURCE_SCRAP_MAP.get(indicator.source)
    scraping_result: ScrapingResult = (
        scraping_function(indicator.ticker, period)
        if scraping_function
        else ScrapingResult(
            period=None, data_value=None, comment="No scraping function found."
        )
    )
    if not scraping_result.get("data_value"):
        logger.warning("No value found.")
    return EconomicData(
        indicator=indicator,
        period=scraping_result.get("period"),
        data_value=scraping_result.get("data_value"),
        comment=scraping_result.get("comment"),
    )


def _ingest_single_economic_data(
    indicator: EconomicIndicatorInformationModel, target_period: Optional[str] = None
) -> bool:
    """Ingest a single economic data."""
    data = _get_economic_data(indicator, target_period)
    is_success = data["data_value"] is not None
    core_services.upsert_with_logs(
        model=EconomicDataModel,
        log_model=EconomicDataUpdateLogModel,
        lookup_kwargs={"indicator": data["indicator"], "period": data["period"]},
        updates={
            "logs": f"Automated data update on {data['indicator'].ticker}.",
            "data_value": data["data_value"],
            "comment": data["comment"],
        },
        logging_on_fields=["data_value"],
        none_skip_fields=["data_value"],
    )
    return is_success


class SpecificEconomicDataNotUpdatedItem(TypedDict):
    """Specific Economic Data Not Updated."""

    indicator: str
    period: str


def ingest_economic_data(
    indicators: Union[
        List[EconomicIndicatorInformationModel],
        QuerySet[EconomicIndicatorInformationModel],
    ],
) -> List[str]:
    """Ingest economic data for all indicators."""
    economic_data_not_updated = []
    for indicator in indicators:
        logger.info(f"Ingesting economic data for indicator: {indicator.name}")
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
