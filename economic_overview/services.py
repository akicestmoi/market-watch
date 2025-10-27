import io
import json
import zipfile
from datetime import date, datetime
from typing import List, Optional, TypedDict, Union

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.db.models import QuerySet
from django.utils import timezone

import shared.services as shared_services
from economic_overview.models import (
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from shared.utils import logger


class EconomicData(TypedDict):
    """Economic data dictionnary."""

    indicator: EconomicIndicatorInformationModel
    period: Optional[date]
    data_value: Optional[float]
    comment: Optional[str]


class ScrappingResult(TypedDict):
    """Scrapping result dictionnary."""

    period: Optional[date]
    data_value: Optional[float]
    comment: str


SOURCE_SCRAP_MAP = {
    EconomicDataSourceChoices.INSEE: lambda t, p: _get_data_from_insee(t, p),
}

PUBLICATION_SOURCE_MAP = {
    EconomicDataSourceChoices.INSEE: lambda n: _get_publication_dates_from_insee(n),
}


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_insee_publication_schedule() -> pd.DataFrame:
    """Get INSEE publication schedule.

    Source: https://www.insee.fr/fr/agenda-diffusion
    """
    INSEE_PUBLICATION_SCHEDULE_URL = "https://www.insee.fr/fr/agenda-diffusion"
    payload = {
        "q": "*:*",
        "start": 0,
        "sortFields": [{"field": "dateEmbargo_dt", "order": "asc"}],
        "filters": [],
        "rows": 100,
        "facetsQuery": [],
    }
    response = requests.post(INSEE_PUBLICATION_SCHEDULE_URL, json=payload)
    if response.status_code >= 400:
        logger.warning(f"Error scraping INSEE publication schedule: {response.text}")
        return pd.DataFrame()

    data = json.loads(response.content)["documents"]
    records = []
    for item in data:
        record = {
            "name": item.get("famille", {})
            .get("facetteConjoncture", {})
            .get("libelleEn", ""),
            "publication_date": item.get("embargo"),
        }
        records.append(record)

    df = pd.DataFrame(records)
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_publication_dates_from_insee(name: str) -> List[datetime]:
    """Get publication dates from INSEE."""
    publication_schedule = _get_insee_publication_schedule()
    publication_dates = publication_schedule[publication_schedule["name"] == name][
        "publication_date"
    ]
    return publication_dates.tolist()[:2]


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


def get_economic_indicators_by_names(
    indicator_names: List[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators by names."""
    if not indicator_names:
        return EconomicIndicatorInformationModel.objects.all()
    return EconomicIndicatorInformationModel.objects.filter(name__in=indicator_names)


def _update_publication_schedule(
    indicator: EconomicIndicatorInformationModel,
) -> Optional[PublicationScheduleModel]:
    """Update publication schedule."""
    logger.info(f"Updating publication schedule for indicator: {indicator.name}")
    publication_schedule = shared_services.get(
        model=PublicationScheduleModel,
        indicator=indicator,
    )
    if (
        publication_schedule.current_publication_date
        and publication_schedule.current_publication_date > timezone.now()
    ):
        logger.info(
            f"Current publication date for indicator: {indicator.name} is not reached. Skipping update."
        )
        return publication_schedule

    publication_function = PUBLICATION_SOURCE_MAP.get(indicator.source)
    next_publication_dates = (
        publication_function(indicator.technical_name) if publication_function else []
    )
    publication_schedule.previous_publication_date = (
        publication_schedule.current_publication_date
    )
    publication_schedule.current_publication_date = next_publication_dates[0]
    publication_schedule.next_publication_date = next_publication_dates[1]
    publication_schedule.save()


def update_publication_schedules(
    indicators: Union[
        List[EconomicIndicatorInformationModel],
        QuerySet[EconomicIndicatorInformationModel],
    ],
) -> List[str]:
    """Update publication schedules."""
    schedule_not_updated = []
    for indicator in indicators:
        schedule = _update_publication_schedule(indicator)
        if schedule:
            schedule_not_updated.append(indicator.name)
    return schedule_not_updated


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


def _get_indicators_with_no_publication_date() -> List[PublicationScheduleModel]:
    """Get indicators with no publication date."""
    return list(
        PublicationScheduleModel.objects.filter(
            current_publication_date__isnull=True,
        )
    )


def get_economic_indicators_to_update(
    start_date: date,
    end_date: date,
    indicator_names: List[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators to update."""
    indicators_to_update = get_economic_indicators_by_names(indicator_names)
    publication_schedules = _get_indicators_with_no_publication_date()

    target_date_schedules = list(
        PublicationScheduleModel.objects.filter(
            current_publication_date__gte=start_date,
            current_publication_date__lte=end_date,
        )
    )
    publication_schedules.extend(target_date_schedules)

    indicator_ids = [schedule.indicator.id for schedule in publication_schedules]
    return indicators_to_update.filter(id__in=indicator_ids)


def _ingest_single_economic_data(
    indicator: EconomicIndicatorInformationModel, target_period: Optional[str] = None
) -> bool:
    """Ingest a single economic data."""
    data = _get_economic_data(indicator, target_period)
    is_success = data["data_value"] is not None
    shared_services.upsert_with_logs(
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


def check_economic_indicator_existence(indicator_name: str) -> bool:
    """Check economic indicator existence in database."""
    return EconomicIndicatorInformationModel.objects.filter(  # type: ignore[reportAttributeAccessIssue]
        name=indicator_name
    ).exists()


def identify_not_existing_indicators(indicator_names: List[str]) -> List[str]:
    """Identify not existing indicators."""
    return [
        name for name in indicator_names if not check_economic_indicator_existence(name)
    ]
