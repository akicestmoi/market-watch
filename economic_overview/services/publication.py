"""Manage economic publication schedules."""

from collections.abc import Callable
from datetime import date, datetime

from django.db.models import QuerySet
from django.utils import timezone

from core.services import logger
from economic_overview.models import (
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from economic_overview.services.scrapers.boj import get_publication_dates_from_boj
from economic_overview.services.scrapers.eurostat import (
    get_publication_dates_from_eurostat,
)
from economic_overview.services.scrapers.fred import get_publication_dates_from_fred
from economic_overview.services.scrapers.insee import get_publication_dates_from_insee
from economic_overview.services.scrapers.jp_cabinet_office import (
    get_publication_dates_from_japan_cabinet_office,
)
from economic_overview.services.scrapers.mlit import get_publication_dates_from_mlit
from economic_overview.services.scrapers.stat_of_jp import (
    get_publication_dates_from_stat_of_jp,
)

PUBLICATION_SOURCE_MAP: dict[
    EconomicDataSourceChoices, Callable[[str], list[datetime]]
] = {
    EconomicDataSourceChoices.INSEE: lambda n: get_publication_dates_from_insee(n),
    EconomicDataSourceChoices.EUROSTAT: lambda n: get_publication_dates_from_eurostat(
        n
    ),
    EconomicDataSourceChoices.FRED: lambda n: get_publication_dates_from_fred(n),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda n: get_publication_dates_from_japan_cabinet_office(
        n
    ),
    EconomicDataSourceChoices.STAT_OF_JP: lambda n: get_publication_dates_from_stat_of_jp(
        n
    ),
    EconomicDataSourceChoices.MLIT: lambda n: get_publication_dates_from_mlit(n),
    EconomicDataSourceChoices.BOJ: lambda n: get_publication_dates_from_boj(n),
}


def _update_publication_schedule(
    indicator: EconomicIndicatorInformationModel,
) -> PublicationScheduleModel | None:
    """Update publication schedule."""
    logger.info(f"Updating publication schedule for indicator: {indicator.name}")
    publication_schedule = PublicationScheduleModel.objects.get(
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
    publication_schedule.next_publication_date = (
        next_publication_dates[1] if len(next_publication_dates) > 1 else None
    )
    publication_schedule.save()
    return None


def update_publication_schedules(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
) -> list[str]:
    """Update publication schedules.

    Returns names of indicators whose schedules were skipped or failed.
    One indicator failure does not abort the rest of the batch.
    """
    schedules_not_updated = []
    for indicator in indicators:
        try:
            schedule_not_updated = _update_publication_schedule(indicator)
            if schedule_not_updated:
                schedules_not_updated.append(indicator.name)
        except Exception:
            logger.exception(
                "Failed to update publication schedule for indicator: %s",
                indicator.name,
            )
            schedules_not_updated.append(indicator.name)
    return schedules_not_updated


def get_publication_schedules_for_dates(
    start_date: date | None = None,
    end_date: date | None = None,
) -> QuerySet[PublicationScheduleModel, PublicationScheduleModel]:
    """Get publication schedules, optionally between dates."""
    queryset = PublicationScheduleModel.objects.all()
    if start_date:
        queryset = queryset.filter(current_publication_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(current_publication_date__lt=end_date)
    return queryset.all()
