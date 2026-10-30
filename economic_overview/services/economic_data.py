"""Query and transform stored economic indicator data."""

from datetime import date
from typing import NamedTuple

from django.db.models import QuerySet

import economic_overview.services.publication as publication
from core.services import ValueChangeType, calculate_value_change
from economic_overview.models import (
    EconomicDataModel,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
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
    query = EconomicDataModel.objects.select_related("indicator").all()
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


def get_lag_for_mode_change_calculation(
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> int:
    """How many prior observations to use when changing a series' mode."""
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    if mode_value == IndicatorDisplayModeChoices.RAW:
        return 0
    frequency_value = (
        frequency.value
        if isinstance(frequency, EconomicPublicationFrequencyChoices)
        else str(frequency)
    )
    if mode_value in {
        IndicatorDisplayModeChoices.QUARTER,
        IndicatorDisplayModeChoices.ANNUALIZED_QUARTER,
    }:
        if frequency_value == EconomicPublicationFrequencyChoices.MONTHLY:
            return 3
        if frequency_value == EconomicPublicationFrequencyChoices.QUARTERLY:
            return 1
        return 1
    if frequency_value == EconomicPublicationFrequencyChoices.MONTHLY:
        return 12
    if frequency_value == EconomicPublicationFrequencyChoices.QUARTERLY:
        return 4
    return 1


class _IndicatorValueTriplet(NamedTuple):
    """Current / previous / change values for an indicator time series."""

    current: float | None
    previous: float | None
    change: float | None


def change_indicator_values_mode(
    economic_data_time_series: list[float],
    *,
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> _IndicatorValueTriplet:
    """Change newest / previous indicator values (and their delta) into ``mode``.

    Input is a newest-first raw series (``[0]`` = latest). Output is only the
    current / previous / change triplet — not a transformed full series.
    """
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    if not economic_data_time_series:
        return _IndicatorValueTriplet(current=None, previous=None, change=None)

    if mode_value == IndicatorDisplayModeChoices.RAW:
        current_value = economic_data_time_series[0]
        previous_value = (
            economic_data_time_series[1] if len(economic_data_time_series) > 1 else None
        )
        return _IndicatorValueTriplet(
            current=current_value,
            previous=previous_value,
            change=calculate_value_change(
                current_value, previous_value, ValueChangeType.ABSOLUTE
            ),
        )

    lag = get_lag_for_mode_change_calculation(frequency, mode_value)
    value_change_type = (
        ValueChangeType.ANNUALIZED_PERCENT
        if mode_value == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER
        else ValueChangeType.PERCENT
    )
    annualized_ratio = (
        4 if mode_value == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER else None
    )

    lookback_index_for_current_value = lag
    current_value = (
        calculate_value_change(
            economic_data_time_series[0],
            economic_data_time_series[lookback_index_for_current_value],
            value_change_type,
            annualized_ratio=annualized_ratio,
        )
        if lookback_index_for_current_value < len(economic_data_time_series)
        else None
    )
    lookback_index_for_previous_value = 1 + lag
    previous_value = (
        calculate_value_change(
            economic_data_time_series[1],
            economic_data_time_series[lookback_index_for_previous_value],
            value_change_type,
            annualized_ratio=annualized_ratio,
        )
        if lookback_index_for_previous_value < len(economic_data_time_series)
        else None
    )
    change = (
        current_value - previous_value
        if current_value is not None and previous_value is not None
        else None
    )
    return _IndicatorValueTriplet(
        current=current_value, previous=previous_value, change=change
    )
