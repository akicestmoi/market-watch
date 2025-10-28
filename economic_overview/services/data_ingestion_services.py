import io
import zipfile
from datetime import date, datetime
from typing import List, Optional, TypedDict, Union

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.db.models import QuerySet

import core.services as core_services
from core.services import logger
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


class ScrappingResult(TypedDict):
    """Scrapping result dictionnary."""

    period: Optional[date]
    data_value: Optional[float]
    comment: str


class EconomicData(TypedDict):
    """Economic data dictionnary."""

    indicator: EconomicIndicatorInformationModel
    period: Optional[date]
    data_value: Optional[float]
    comment: Optional[str]


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_data_from_insee(
    ticker: str, target_period: Optional[str] = None
) -> ScrappingResult:
    """Get data from INSEE.

    Note: The data given by INSEE is a zip file containing 2 files:
    - caractéristiques.csv
    - valeurs_mensuelles.csv (which contains statistics values)

    Source: https://bdm.insee.fr/
    Docs: https://www.insee.fr/fr/statistiques/serie/{ticker}
    """
    INSEE_URL = f"https://bdm.insee.fr/series/{ticker}/csv?lang=fr&ordre=antechronologique&transposition=donneescolonne&periodeDebut=1&anneeDebut=1977&periodeFin=10&anneeFin=2025&revision=sansrevisions"
    response = requests.get(INSEE_URL)
    if response.status_code >= 400:
        logger.warning(f"Error scraping INSEE data: {response.text}")
        return ScrappingResult(period=None, data_value=None, comment=response.text)

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            csv_files = [n for n in zf.namelist() if "valeurs_mensuelles" in n.lower()]
            if not csv_files:
                return ScrappingResult(
                    period=None,
                    data_value=None,
                    comment="No 'valeurs_mensuelles' CSV found in archive.",
                )
            with zf.open(csv_files[0]) as f:
                df = pd.read_csv(f, encoding="utf-8", sep=";")
    except Exception as exc:
        return ScrappingResult(
            period=None, data_value=None, comment=f"Error reading ZIP content: {exc}"
        )

    if (
        "Libellé" not in df.columns
        or "Période" not in "Période" not in df["Libellé"].values
    ):
        return ScrappingResult(
            period=None, data_value=None, comment="Data is not in the expected format."
        )

    header_row = df.index[df["Libellé"] == "Période"][0]
    if len(df) <= header_row + 1:
        return ScrappingResult(period=None, data_value=None, comment="No data found.")

    if not target_period:
        target_row = header_row + 1
    else:
        target_row = df.index[df["Libellé"] == target_period]
        if target_row.empty:
            return ScrappingResult(
                period=None, data_value=None, comment="Target period not found."
            )
        target_row = target_row[0]

    period = datetime.strptime(str(df.iloc[target_row, 0]), "%Y-%m").date()
    data_value = float(str(df.iloc[target_row, 1]))
    return ScrappingResult(period=period, data_value=data_value, comment="")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_data_from_japan_cabinet_office(
    ticker: str, target_period: Optional[str] = None
) -> ScrappingResult:
    """Get data from Japan Cabinet Office."""
    raise NotImplementedError("Not implemented.")


def _get_economic_data(
    indicator: EconomicIndicatorInformationModel, period: Optional[str] = None
) -> EconomicData:
    """Get economic data from scrapping function."""
    scrapping_function = SOURCE_SCRAP_MAP.get(indicator.source)
    scrapping_result: ScrappingResult = (
        scrapping_function(indicator.ticker, period)
        if scrapping_function
        else ScrappingResult(
            period=None, data_value=None, comment="No scrapping function found."
        )
    )
    if not scrapping_result.get("data_value"):
        logger.warning("No value found.")
    return EconomicData(
        indicator=indicator,
        period=scrapping_result.get("period"),
        data_value=scrapping_result.get("data_value"),
        comment=scrapping_result.get("comment"),
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
            "logs": f"Automated data update on {data['indicator'].ticker} to data value: {data['data_value']}.",
            "data_value": data["data_value"],
            "comment": data["comment"],
        },
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
