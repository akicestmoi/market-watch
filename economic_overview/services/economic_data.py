"""Query and transform stored economic indicator data."""

from datetime import date

from django.db.models import QuerySet

import economic_overview.services.publication as publication
from economic_overview.models import (
    EconomicDataModel,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)


def get_economic_indicators_by_names(
    indicator_names: list[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators by names."""
    if not indicator_names:
        return EconomicIndicatorInformationModel.objects.all()
    return EconomicIndicatorInformationModel.objects.filter(name__in=indicator_names)


def _get_indicators_with_no_publication_date() -> list[PublicationScheduleModel]:
    """Get indicators with no publication date."""
    return list(
        PublicationScheduleModel.objects.filter(
            current_publication_date__isnull=True,
        )
    )


def get_economic_indicators_to_update(
    start_date: date | None = None,
    end_date: date | None = None,
    indicator_names: list[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators to update.

    Start date is inclusive but end date is exclusive.
    """
    indicators_to_update = get_economic_indicators_by_names(indicator_names)
    publication_schedules = _get_indicators_with_no_publication_date()

    target_date_schedules = publication.get_publication_schedules_for_dates(
        start_date=start_date,
        end_date=end_date,
    )
    publication_schedules.extend(list(target_date_schedules))

    indicator_ids = [schedule.indicator.id for schedule in publication_schedules]
    return indicators_to_update.filter(id__in=indicator_ids)


def check_economic_indicator_existence(indicator_name: str) -> bool:
    """Check economic indicator existence in database."""
    return EconomicIndicatorInformationModel.objects.filter(
        name=indicator_name
    ).exists()


def identify_not_existing_indicators(indicator_names: list[str]) -> list[str]:
    """Identify not existing indicators."""
    return [
        name for name in indicator_names if not check_economic_indicator_existence(name)
    ]


def get_economic_data(
    indicator_names: list[str] = [], period: str | None = None
) -> QuerySet[EconomicDataModel]:
    """Get economic data for a specific indicator and period."""
    query = EconomicDataModel.objects.all()
    if indicator_names:
        query = query.filter(indicator__name__in=indicator_names)
    if period:
        query = query.filter(period=period)
    return query


def delete_economic_data(ids: list[int]) -> int:
    """Delete economic data by IDs."""
    queryset = EconomicDataModel.objects.filter(pk__in=ids)
    deleted_count = queryset.count()
    queryset.delete()
    return deleted_count


def delete_economic_data_update_logs_before_date(logs_date: date):
    """Delete economic data update logs before a given date."""
    EconomicDataUpdateLogModel.objects.filter(date_added__lt=logs_date).delete()
