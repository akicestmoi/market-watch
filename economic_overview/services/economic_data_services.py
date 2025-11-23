from datetime import date
from typing import List, Optional

from django.db.models import QuerySet

import economic_overview.services.publication_services as publication_services
from economic_overview.models import (
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)


def get_economic_indicators_by_names(
    indicator_names: List[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators by names."""
    if not indicator_names:
        return EconomicIndicatorInformationModel.objects.all()
    return EconomicIndicatorInformationModel.objects.filter(name__in=indicator_names)


def _get_indicators_with_no_publication_date() -> List[PublicationScheduleModel]:
    """Get indicators with no publication date."""
    return list(
        PublicationScheduleModel.objects.filter(
            current_publication_date__isnull=True,
        )
    )


def get_economic_indicators_to_update(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    indicator_names: List[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators to update.

    Start date is inclusive but end date is exclusive.
    """
    indicators_to_update = get_economic_indicators_by_names(indicator_names)
    publication_schedules = _get_indicators_with_no_publication_date()

    target_date_schedules = publication_services.get_publication_schedules_for_dates(
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


def identify_not_existing_indicators(indicator_names: List[str]) -> List[str]:
    """Identify not existing indicators."""
    return [
        name for name in indicator_names if not check_economic_indicator_existence(name)
    ]


def delete_economic_data_update_logs_before_date(logs_date: date):
    """Delete economic data update logs before a given date."""
    EconomicDataUpdateLogModel.objects.filter(date_added__lt=logs_date).delete()
