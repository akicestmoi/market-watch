import json
from datetime import date, datetime
from typing import List, Optional, Union

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.db.models import QuerySet
from django.utils import timezone

import core.services as core_services
from core.services import CACHE_MAXSIZE, CACHE_TTL_SECONDS, logger
from economic_overview.models import (
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)

PUBLICATION_SOURCE_MAP = {
    EconomicDataSourceChoices.INSEE: lambda n: _get_publication_dates_from_insee(n),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda n: _get_publication_dates_from_japan_cabinet_office(
        n
    ),
}


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_insee_publication_schedule() -> pd.DataFrame:
    """Get INSEE publication schedule.

    Source: https://www.insee.fr/fr/agenda-diffusion
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
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
        return default_df

    data = json.loads(response.content).get("documents", [])
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
    if df.empty:
        return default_df
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_publication_dates_from_insee(name: str) -> List[datetime]:
    """Get publication dates from INSEE."""
    publication_schedule = _get_insee_publication_schedule()
    publication_dates = publication_schedule[publication_schedule["name"] == name][
        "publication_date"
    ]
    return [
        pd_timestamp.to_pydatetime().replace(tzinfo=None)
        for pd_timestamp in publication_dates.tolist()[:2]
    ]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_publication_dates_from_japan_cabinet_office(name: str) -> List[datetime]:
    """Get publication dates from Japan Cabinet Office."""
    raise NotImplementedError("Not implemented.")


def _update_publication_schedule(
    indicator: EconomicIndicatorInformationModel,
) -> Optional[PublicationScheduleModel]:
    """Update publication schedule."""
    logger.info(f"Updating publication schedule for indicator: {indicator.name}")
    publication_schedule = core_services.get(
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
    if not publication_function:
        raise ValueError(
            f"Publication function not found for indicator: {indicator.name}"
        )
    next_publication_dates = (
        publication_function(indicator.technical_name) if publication_function else []
    )
    if not next_publication_dates:
        logger.warning(f"No publication dates found for indicator: {indicator.name}")
        return publication_schedule

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
    schedules_not_updated = []
    for indicator in indicators:
        schedule_not_updated = _update_publication_schedule(indicator)
        if schedule_not_updated:
            schedules_not_updated.append(indicator.name)
    return schedules_not_updated


def get_publication_schedules_for_dates(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> QuerySet[PublicationScheduleModel, PublicationScheduleModel]:
    """Get publication schedules, optionally between dates."""
    queryset = PublicationScheduleModel.objects.all()
    if start_date:
        queryset = queryset.filter(current_publication_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(current_publication_date__lt=end_date)
    return queryset.all()
