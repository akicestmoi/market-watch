import json
from datetime import date, datetime
from typing import List, Optional, Union

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.db.models import QuerySet
from django.utils import timezone

import core.services as core_services
from core.services import logger
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
