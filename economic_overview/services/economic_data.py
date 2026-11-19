"""Query, transform, and ingest economic indicator data."""

import logging
from collections.abc import Callable
from datetime import date
from typing import NamedTuple, TypedDict

from dateutil.relativedelta import relativedelta
from django.db.models import QuerySet

import core.services.orm as core_services
from core.services.time_series_calculation import (
    ValueChangeType,
    calculate_value_change,
)
from economic_overview.models.common import EconomicDataSourceChoices
from economic_overview.models.economic_indicators import (
    EconomicDataModel,
    EconomicDataUpdateLogModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
    PublicationScheduleModeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from economic_overview.services.config import INDICATOR_TICKERS_TO_SKIP_DURING_INGEST
from economic_overview.services.scrapers.banque_de_france import (
    get_data_from_banque_de_france,
)
from economic_overview.services.scrapers.bea import get_data_from_bea
from economic_overview.services.scrapers.boj import get_data_from_boj
from economic_overview.services.scrapers.census import get_data_from_census
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.conference_board import (
    get_data_from_conference_board,
)
from economic_overview.services.scrapers.ecb import get_data_from_ecb
from economic_overview.services.scrapers.eurostat import get_data_from_eurostat
from economic_overview.services.scrapers.fred import get_data_from_fred
from economic_overview.services.scrapers.imf import get_data_from_imf
from economic_overview.services.scrapers.insee import get_data_from_insee
from economic_overview.services.scrapers.ism import get_data_from_ism
from economic_overview.services.scrapers.jp_cabinet_office import (
    get_data_from_japan_cabinet_office,
)
from economic_overview.services.scrapers.meti import get_data_from_meti
from economic_overview.services.scrapers.mlit import get_data_from_mlit
from economic_overview.services.scrapers.mof import get_data_from_mof
from economic_overview.services.scrapers.nahb import get_data_from_nahb
from economic_overview.services.scrapers.oecd import get_data_from_oecd
from economic_overview.services.scrapers.stat_of_jp import get_data_from_stat_of_jp
from economic_overview.services.scrapers.trading_economics import (
    get_data_from_trading_economics,
)
from economic_overview.services.scrapers.univ_michigan import (
    get_data_from_univ_michigan,
)
from economic_overview.services.scrapers.wid import get_data_from_wid

logger = logging.getLogger(__name__)

SOURCE_SCRAP_MAP: dict[
    EconomicDataSourceChoices,
    Callable[
        [str, str | None, EconomicPublicationFrequencyChoices, str],
        list[ScrapingResult],
    ],
] = {
    EconomicDataSourceChoices.INSEE: lambda t, p, f, _location: get_data_from_insee(
        t, p, f
    ),
    EconomicDataSourceChoices.EUROSTAT: lambda t, p, f, location: get_data_from_eurostat(
        t, p, f, location
    ),
    EconomicDataSourceChoices.FRED: lambda t, p, f, _location: get_data_from_fred(
        t, p, f
    ),
    EconomicDataSourceChoices.UNIV_MICHIGAN: (
        lambda t, p, f, _location: get_data_from_univ_michigan(t, p, f)
    ),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda t, p, f, _location: get_data_from_japan_cabinet_office(
        t, p, f
    ),
    EconomicDataSourceChoices.STAT_OF_JP: lambda t, p, f, _location: get_data_from_stat_of_jp(
        t, p, f
    ),
    EconomicDataSourceChoices.MLIT: lambda t, p, f, _location: get_data_from_mlit(
        t, p, f
    ),
    EconomicDataSourceChoices.METI: lambda t, p, f, _location: get_data_from_meti(
        t, p, f
    ),
    EconomicDataSourceChoices.BOJ: lambda t, p, f, _location: get_data_from_boj(
        t, p, f
    ),
    EconomicDataSourceChoices.MOF: lambda t, p, f, _location: get_data_from_mof(
        t, p, f
    ),
    EconomicDataSourceChoices.ECB: lambda t, p, f, location: get_data_from_ecb(
        t, p, f, location
    ),
    EconomicDataSourceChoices.IMF: lambda t, p, f, location: get_data_from_imf(
        t, p, f, location
    ),
    EconomicDataSourceChoices.OECD: lambda t, p, f, location: get_data_from_oecd(
        t, p, f, location
    ),
    EconomicDataSourceChoices.BEA: lambda t, p, f, _location: get_data_from_bea(
        t, p, f
    ),
    EconomicDataSourceChoices.BANQUE_DE_FRANCE: (
        lambda t, p, f, _location: get_data_from_banque_de_france(t, p, f)
    ),
    EconomicDataSourceChoices.NAHB: lambda t, p, f, _location: get_data_from_nahb(
        t, p, f
    ),
    EconomicDataSourceChoices.ISM: lambda t, p, f, _location: get_data_from_ism(
        t, p, f
    ),
    EconomicDataSourceChoices.CONFERENCE_BOARD: (
        lambda t, p, f, _location: get_data_from_conference_board(t, p, f)
    ),
    EconomicDataSourceChoices.CENSUS: lambda t, p, f, _location: get_data_from_census(
        t, p, f
    ),
    EconomicDataSourceChoices.TRADING_ECONOMICS: (
        lambda t, p, f, _location: get_data_from_trading_economics(t, p, f)
    ),
    EconomicDataSourceChoices.WID: lambda t, p, f, location: get_data_from_wid(
        t, p, f, location
    ),
}


def get_economic_indicators_by_names(
    indicator_names: list[str] = [],
) -> QuerySet[EconomicIndicatorInformationModel]:
    """Get economic indicators by names."""
    if not indicator_names:
        return EconomicIndicatorInformationModel.objects.all()
    return EconomicIndicatorInformationModel.objects.filter(
        full_name__in=indicator_names
    )


def _get_indicators_with_no_publication_date() -> list[PublicationScheduleModel]:
    """Get calendar-mode indicators that still lack a current publication date.

    Monthly-update indicators are excluded: they are checked on the first
    calendar day of each month instead of the daily no-date backfill path.
    """
    return list(
        PublicationScheduleModel.objects.filter(
            current_publication_date__isnull=True,
        ).exclude(
            indicator__publication_schedule_mode=(
                PublicationScheduleModeChoices.MONTHLY_UPDATE
            )
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
    # Circular: economic_data ↔ publication_update (monthly ingest imports this module).
    import economic_overview.services.publication_update as publication_update

    indicators_to_update = get_economic_indicators_by_names(indicator_names)
    publication_schedules = _get_indicators_with_no_publication_date()

    target_date_schedules = publication_update.get_publication_schedules_for_dates(
        start_date=start_date,
        end_date=end_date,
    )
    publication_schedules.extend(list(target_date_schedules))

    indicator_ids = [schedule.indicator.id for schedule in publication_schedules]
    return indicators_to_update.filter(id__in=indicator_ids)


def check_economic_indicator_existence(indicator_name: str) -> bool:
    """Check economic indicator existence in database."""
    return EconomicIndicatorInformationModel.objects.filter(
        full_name=indicator_name
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
        query = query.filter(indicator__full_name__in=indicator_names)
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


def get_lookback_months_for_mode_change(
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> int:
    """Return calendar months to subtract for MoM / QoQ / QoQy / YoY lookback.

    Raw / vsGDP need no lookback (0). Gaps must not be bridged by counting
    available observations — callers look up this exact prior period.
    """
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    if mode_value in {
        IndicatorDisplayModeChoices.RAW,
        IndicatorDisplayModeChoices.VS_GDP,
        IndicatorDisplayModeChoices.YTD_RAW,
        IndicatorDisplayModeChoices.YTD_YOY,
        IndicatorDisplayModeChoices.YTD_VS_GDP,
        IndicatorDisplayModeChoices.REL_QOQ,
        IndicatorDisplayModeChoices.REL_YOY,
        IndicatorDisplayModeChoices.CONTR_QOQ,
        IndicatorDisplayModeChoices.CONTR_YOY,
        IndicatorDisplayModeChoices.YTD_REL_QOQ,
        IndicatorDisplayModeChoices.YTD_REL_YOY,
        IndicatorDisplayModeChoices.YTD_CONTR_QOQ,
        IndicatorDisplayModeChoices.YTD_CONTR_YOY,
    }:
        # Rel / Contr / YTD share math runs in the recap or charts UI only.
        return 0
    if mode_value == IndicatorDisplayModeChoices.MONTH:
        return 1
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
            return 3
        # Annual series: treat QoQ / QoQy like YoY.
        return 12
    # Annual (YoY): same calendar month / quarter / year one year earlier.
    return 12


def get_lookback_period_for_mode_change(
    period: date,
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> date | None:
    """Return the calendar period a mode change should compare 'period' against."""
    lookback_months = get_lookback_months_for_mode_change(frequency, mode)
    if lookback_months == 0:
        return None
    return period - relativedelta(months=lookback_months)


def get_lag_for_mode_change_calculation(
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> int:
    """Return a dense-series observation lag (history window sizing only).

    Mode transforms must use 'get_lookback_period_for_mode_change' so missing
    months do not shift YoY onto the wrong calendar period.
    """
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    lookback_months = get_lookback_months_for_mode_change(frequency, mode)
    if lookback_months == 0:
        return 0
    frequency_value = (
        frequency.value
        if isinstance(frequency, EconomicPublicationFrequencyChoices)
        else str(frequency)
    )
    if frequency_value == EconomicPublicationFrequencyChoices.QUARTERLY:
        # One quarter ≈ three calendar months.
        return max(1, lookback_months // 3)
    if frequency_value == EconomicPublicationFrequencyChoices.ANNUAL:
        return max(1, lookback_months // 12)
    if mode_value == IndicatorDisplayModeChoices.MONTH:
        return 1
    return lookback_months


def get_number_of_months_to_calculate_mode_change(
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> int:
    """Return how many months of history to load for current + previous mode values."""
    lookback_months = get_lookback_months_for_mode_change(frequency, mode)
    if lookback_months == 0:
        # Raw: latest value plus the prior available observation.
        return 24
    # Previous observation (~one period) plus that observation's lookback.
    return lookback_months * 2 + 2


class TimedEconomicDataValue(NamedTuple):
    """One dated level in an economic time series."""

    period: date
    value: float


class _IndicatorValueTriplet(NamedTuple):
    """Current / previous / change values for an indicator time series."""

    current: float | None
    previous: float | None
    change: float | None


_LEVEL_AND_SHARE_DISPLAY_MODES: frozenset[str] = frozenset(
    {
        IndicatorDisplayModeChoices.RAW,
        IndicatorDisplayModeChoices.VS_GDP,
        IndicatorDisplayModeChoices.YTD_RAW,
        IndicatorDisplayModeChoices.YTD_YOY,
        IndicatorDisplayModeChoices.YTD_VS_GDP,
        IndicatorDisplayModeChoices.REL_QOQ,
        IndicatorDisplayModeChoices.REL_YOY,
        IndicatorDisplayModeChoices.CONTR_QOQ,
        IndicatorDisplayModeChoices.CONTR_YOY,
        IndicatorDisplayModeChoices.YTD_REL_QOQ,
        IndicatorDisplayModeChoices.YTD_REL_YOY,
        IndicatorDisplayModeChoices.YTD_CONTR_QOQ,
        IndicatorDisplayModeChoices.YTD_CONTR_YOY,
    }
)


def _get_latest_value_triplet(
    economic_data_time_series: list[TimedEconomicDataValue],
) -> _IndicatorValueTriplet:
    """Return the latest level triplet for Raw / vsGDP / Rel / Contr / YTD modes."""
    # vsGDP callers pass an already-scaled % of GDP series; treat like Raw.
    # Rel / Contr / YTD share math runs in the recap or charts UI only.
    # The series is newest-first, so index 0 is the latest value.
    current_value = economic_data_time_series[0].value
    # The series is newest-first, so index 1 is the prior value for the change.
    previous_value = (
        economic_data_time_series[1].value
        if len(economic_data_time_series) > 1
        else None
    )
    return _IndicatorValueTriplet(
        current=current_value,
        previous=previous_value,
        change=calculate_value_change(
            current_value, previous_value, ValueChangeType.ABSOLUTE
        ),
    )


def _get_latest_growth_triplet(
    economic_data_time_series: list[TimedEconomicDataValue],
    *,
    frequency: EconomicPublicationFrequencyChoices | str,
    mode_value: str,
) -> _IndicatorValueTriplet:
    """Return the latest growth triplet using calendar lookback periods."""
    # Usage of dict: keys are observation periods; values are raw levels.
    value_by_period: dict[date, float] = {
        timed_value.period: timed_value.value
        for timed_value in economic_data_time_series
    }
    # The series is newest-first, so index 0 is the latest value.
    current_value = _get_percent_change_at_period(
        value_by_period,
        economic_data_time_series[0].period,
        frequency=frequency,
        mode_value=mode_value,
    )
    previous_value = (
        _get_percent_change_at_period(
            value_by_period,
            economic_data_time_series[1].period,
            frequency=frequency,
            mode_value=mode_value,
        )
        if len(economic_data_time_series) > 1
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


def _get_percent_change_at_period(
    value_by_period: dict[date, float],
    period: date,
    *,
    frequency: EconomicPublicationFrequencyChoices | str,
    mode_value: str,
) -> float | None:
    """Compute one MoM / QoQ / QoQy / YoY value at 'period' via calendar lookback."""
    lookback_period = get_lookback_period_for_mode_change(period, frequency, mode_value)
    if lookback_period is None:
        return None
    current_level = value_by_period.get(period)
    lookback_level = value_by_period.get(lookback_period)
    if current_level is None or lookback_level is None:
        return None
    value_change_type = (
        ValueChangeType.ANNUALIZED_PERCENT
        if mode_value == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER
        else ValueChangeType.PERCENT
    )
    annualized_ratio = (
        4 if mode_value == IndicatorDisplayModeChoices.ANNUALIZED_QUARTER else None
    )
    return calculate_value_change(
        current_level,
        lookback_level,
        value_change_type,
        annualized_ratio=annualized_ratio,
    )


def change_triplet_values_for_mode(
    economic_data_time_series: list[TimedEconomicDataValue],
    *,
    frequency: EconomicPublicationFrequencyChoices | str,
    mode: IndicatorDisplayModeChoices | str,
) -> _IndicatorValueTriplet:
    """Change newest / previous indicator values (and their delta) into 'mode'.

    Input is a newest-first dated raw series ('[0]' = latest). Growth modes
    compare each value to the matching calendar lookback period (not a fixed
    observation count), so a missing month cannot shift YoY onto the wrong
    prior month. Output is only the current / previous / change triplet.
    """
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    if not economic_data_time_series:
        return _IndicatorValueTriplet(current=None, previous=None, change=None)

    if mode_value in _LEVEL_AND_SHARE_DISPLAY_MODES:
        return _get_latest_value_triplet(economic_data_time_series)

    return _get_latest_growth_triplet(
        economic_data_time_series,
        frequency=frequency,
        mode_value=mode_value,
    )


def get_lock_key_for_economic_data_ingestion() -> str:
    """Return Redis lock key for economic data ingestion."""
    return "lock:economic_data_ingestion"


class _EconomicData(TypedDict):
    """Scraped economic indicator value ready for upsert."""

    indicator: EconomicIndicatorInformationModel
    period: date | None
    data_value: float | None
    comment: str | None


def _ingest_historical_data_for_indicator_within_range(
    indicator: EconomicIndicatorInformationModel,
    scraping_function: Callable[
        [str, str | None, EconomicPublicationFrequencyChoices, str],
        list[ScrapingResult],
    ],
    start_date: date,
    end_date: date,
) -> bool:
    """Upsert scraped values in '[start_date, end_date]' for one indicator.

    Returns True when at least one value was stored.
    """
    economic_data = scraping_function(
        indicator.ticker,
        None,
        EconomicPublicationFrequencyChoices(indicator.frequency),
        indicator.location,
    )
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
    return has_been_upserted


def _get_economic_data(
    indicator: EconomicIndicatorInformationModel, period: str | None = None
) -> _EconomicData:
    """Get economic data from scraping function (latest or a specific period)."""
    ticker = str(indicator.ticker or "")
    # Empty ticker = intentionally unwired location stub (recap shows —).
    if not ticker or ticker in INDICATOR_TICKERS_TO_SKIP_DURING_INGEST:
        return _EconomicData(
            indicator=indicator,
            period=None,
            data_value=None,
            comment=(
                "No ticker wired for this indicator; skipped by scraper."
                if not ticker
                else "Non-scraped indicator; skipped by scraper."
            ),
        )
    scraping_function = SOURCE_SCRAP_MAP.get(
        EconomicDataSourceChoices(indicator.source)
    )
    economic_data: list[ScrapingResult] = (
        scraping_function(
            indicator.ticker,
            period,
            EconomicPublicationFrequencyChoices(indicator.frequency),
            indicator.location,
        )
        if scraping_function
        else [
            ScrapingResult(
                period=None, data_value=None, comment="No scraping function found."
            )
        ]
    )
    # Scrapers return newest-first or a single filtered value; index 0 is what we upsert.
    scraping_result = (
        economic_data[0]
        if economic_data
        else ScrapingResult(period=None, data_value=None, comment="No value found.")
    )
    if not scraping_result.get("data_value"):
        logger.warning("No value found.")
    return _EconomicData(
        indicator=indicator,
        period=scraping_result.get("period"),
        data_value=scraping_result.get("data_value"),
        comment=scraping_result.get("comment"),
    )


def _upsert_economic_data_item(
    indicator: EconomicIndicatorInformationModel,
    period: date | None,
    data_value: float | None,
    comment: str | None,
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
    indicator: EconomicIndicatorInformationModel, target_period: str | None = None
) -> bool:
    """Ingest a single (latest or period-specific) economic data item."""
    data = _get_economic_data(indicator, target_period)
    return _upsert_economic_data_item(
        indicator=data["indicator"],
        period=data["period"],
        data_value=data["data_value"],
        comment=data["comment"],
    )


def ingest_latest_economic_data(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
) -> list[str]:
    """Ingest the latest economic data for each indicator."""
    economic_data_not_updated = []
    for indicator in indicators:
        logger.info(
            f"Ingesting latest economic data for indicator: {indicator.full_name}"
        )
        is_success = _ingest_single_economic_data(indicator)
        if not is_success:
            economic_data_not_updated.append(indicator.full_name)
    return economic_data_not_updated


class _SpecificEconomicDataNotUpdatedItem(TypedDict):
    """Specific Economic Data Not Updated."""

    indicator: str
    period: str


def ingest_specific_economic_data(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
    periods: list[list[str]],
) -> list[_SpecificEconomicDataNotUpdatedItem]:
    """Ingest specific economic data for indicators and target periods."""
    economic_data_not_updated = []
    for indicator, period_list in zip(indicators, periods):
        for target_period in period_list:
            logger.info(
                f"Ingesting economic data for indicator: {indicator.full_name} and period: {target_period}"
            )
            is_success = _ingest_single_economic_data(indicator, target_period)
            if not is_success:
                economic_data_not_updated.append(
                    _SpecificEconomicDataNotUpdatedItem(
                        indicator=indicator.full_name,
                        period=target_period,
                    )
                )
    return economic_data_not_updated


def ingest_historical_economic_data(
    indicators: (
        list[EconomicIndicatorInformationModel]
        | QuerySet[EconomicIndicatorInformationModel]
    ),
    start_date: date,
    end_date: date,
) -> list[_SpecificEconomicDataNotUpdatedItem]:
    """Ingest all economic data in [start_date, end_date] for each indicator."""
    economic_data_not_updated: list[_SpecificEconomicDataNotUpdatedItem] = []
    window_label = f"{start_date.isoformat()}/{end_date.isoformat()}"
    for indicator in indicators:
        logger.info(
            f"Ingesting historical economic data for indicator: {indicator.full_name} "
            f"from {start_date} to {end_date}"
        )
        ticker = str(indicator.ticker or "")
        if not ticker or ticker in INDICATOR_TICKERS_TO_SKIP_DURING_INGEST:
            continue

        scraping_function = SOURCE_SCRAP_MAP.get(
            EconomicDataSourceChoices(indicator.source)
        )
        if not scraping_function:
            economic_data_not_updated.append(
                _SpecificEconomicDataNotUpdatedItem(
                    indicator=indicator.full_name,
                    period=window_label,
                )
            )
            continue

        has_been_upserted = _ingest_historical_data_for_indicator_within_range(
            indicator,
            scraping_function,
            start_date,
            end_date,
        )

        if not has_been_upserted:
            economic_data_not_updated.append(
                _SpecificEconomicDataNotUpdatedItem(
                    indicator=indicator.full_name,
                    period=window_label,
                )
            )
    return economic_data_not_updated
