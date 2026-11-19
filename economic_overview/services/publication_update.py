"""Update publication schedules and monthly calendar-less indicator refreshes."""

import logging
from collections.abc import Callable
from datetime import date, datetime
from enum import Enum
from typing import NamedTuple, TypedDict

from django.db.models import QuerySet
from django.utils import timezone

from core.services.calendar import get_local_today
from economic_overview.models.common import EconomicDataSourceChoices
from economic_overview.models.economic_indicators import (
    EconomicIndicatorInformationModel,
    IndicatorMeasureTypeChoices,
    PublicationScheduleModeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from economic_overview.services.config import (
    ANNUAL_GDP_GROWTH_TICKER,
    DERIVED_SCHEDULE_CALENDAR_TECHNICAL_NAME_BY_TICKER,
    DERIVED_SCHEDULE_INPUT_TICKERS_BY_LOCATION_AND_TICKER,
    DERIVED_SCHEDULE_INPUT_TICKERS_BY_TICKER,
)
from economic_overview.services.economic_data import ingest_latest_economic_data
from economic_overview.services.scrapers.banque_de_france import (
    get_publication_dates_from_banque_de_france,
)
from economic_overview.services.scrapers.bea import get_publication_dates_from_bea
from economic_overview.services.scrapers.boj import get_publication_dates_from_boj
from economic_overview.services.scrapers.census import get_publication_dates_from_census
from economic_overview.services.scrapers.conference_board import (
    get_publication_dates_from_conference_board,
)
from economic_overview.services.scrapers.ecb import get_publication_dates_from_ecb
from economic_overview.services.scrapers.eurostat import (
    get_publication_dates_from_eurostat,
)
from economic_overview.services.scrapers.fred import get_publication_dates_from_fred
from economic_overview.services.scrapers.imf import get_publication_dates_from_imf
from economic_overview.services.scrapers.insee import get_publication_dates_from_insee
from economic_overview.services.scrapers.ism import get_publication_dates_from_ism
from economic_overview.services.scrapers.jp_cabinet_office import (
    get_publication_dates_from_japan_cabinet_office,
)
from economic_overview.services.scrapers.meti import get_publication_dates_from_meti
from economic_overview.services.scrapers.mlit import get_publication_dates_from_mlit
from economic_overview.services.scrapers.mof import get_publication_dates_from_mof
from economic_overview.services.scrapers.nahb import get_publication_dates_from_nahb
from economic_overview.services.scrapers.oecd import get_publication_dates_from_oecd
from economic_overview.services.scrapers.stat_of_jp import (
    get_publication_dates_from_stat_of_jp,
)
from economic_overview.services.scrapers.trading_economics import (
    get_publication_dates_from_trading_economics,
)
from economic_overview.services.scrapers.univ_michigan import (
    get_publication_dates_from_univ_michigan,
)
from economic_overview.services.scrapers.wid import get_publication_dates_from_wid

logger = logging.getLogger(__name__)


class _PublicationScheduleLookup(NamedTuple):
    """Technical name + location for a source calendar scrape."""

    technical_name: str
    location: str


PUBLICATION_SOURCE_MAP: dict[
    EconomicDataSourceChoices,
    Callable[[_PublicationScheduleLookup], list[datetime]],
] = {
    EconomicDataSourceChoices.INSEE: (
        lambda lookup: get_publication_dates_from_insee(lookup.technical_name)
    ),
    EconomicDataSourceChoices.EUROSTAT: (
        lambda lookup: get_publication_dates_from_eurostat(lookup.technical_name)
    ),
    EconomicDataSourceChoices.FRED: (
        lambda lookup: get_publication_dates_from_fred(lookup.technical_name)
    ),
    EconomicDataSourceChoices.UNIV_MICHIGAN: (
        lambda lookup: get_publication_dates_from_univ_michigan(lookup.technical_name)
    ),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: (
        lambda lookup: get_publication_dates_from_japan_cabinet_office(
            lookup.technical_name
        )
    ),
    EconomicDataSourceChoices.STAT_OF_JP: (
        lambda lookup: get_publication_dates_from_stat_of_jp(lookup.technical_name)
    ),
    EconomicDataSourceChoices.MLIT: (
        lambda lookup: get_publication_dates_from_mlit(lookup.technical_name)
    ),
    EconomicDataSourceChoices.METI: (
        lambda lookup: get_publication_dates_from_meti(lookup.technical_name)
    ),
    EconomicDataSourceChoices.BOJ: (
        lambda lookup: get_publication_dates_from_boj(lookup.technical_name)
    ),
    EconomicDataSourceChoices.MOF: (
        lambda lookup: get_publication_dates_from_mof(lookup.technical_name)
    ),
    EconomicDataSourceChoices.ECB: (
        lambda lookup: get_publication_dates_from_ecb(lookup.technical_name)
    ),
    EconomicDataSourceChoices.IMF: (
        lambda lookup: get_publication_dates_from_imf(lookup.technical_name)
    ),
    EconomicDataSourceChoices.OECD: (
        lambda lookup: get_publication_dates_from_oecd(lookup.technical_name)
    ),
    EconomicDataSourceChoices.BANQUE_DE_FRANCE: (
        lambda lookup: get_publication_dates_from_banque_de_france(
            lookup.technical_name
        )
    ),
    EconomicDataSourceChoices.BEA: (
        lambda lookup: get_publication_dates_from_bea(lookup.technical_name)
    ),
    EconomicDataSourceChoices.NAHB: (
        lambda lookup: get_publication_dates_from_nahb(lookup.technical_name)
    ),
    EconomicDataSourceChoices.ISM: (
        lambda lookup: get_publication_dates_from_ism(lookup.technical_name)
    ),
    EconomicDataSourceChoices.CONFERENCE_BOARD: (
        lambda lookup: get_publication_dates_from_conference_board(
            lookup.technical_name
        )
    ),
    EconomicDataSourceChoices.CENSUS: (
        lambda lookup: get_publication_dates_from_census(lookup.technical_name)
    ),
    EconomicDataSourceChoices.TRADING_ECONOMICS: (
        lambda lookup: get_publication_dates_from_trading_economics(
            lookup.technical_name,
            lookup.location,
        )
    ),
    EconomicDataSourceChoices.WID: (
        lambda lookup: get_publication_dates_from_wid(lookup.technical_name)
    ),
}


def _get_monthly_update_indicators() -> QuerySet[EconomicIndicatorInformationModel]:
    """Return non-hidden indicators tagged for monthly calendar-less updates."""
    return EconomicIndicatorInformationModel.objects.filter(
        publication_schedule_mode=PublicationScheduleModeChoices.MONTHLY_UPDATE,
        is_hidden=False,
    ).order_by("id")


class MonthlyUpdateRunStatus(str, Enum):
    """Top-level status for a monthly publication-update Celery run."""

    SUCCESS = "success"
    SKIPPED_NOT_FIRST_OF_MONTH = "skipped_not_first_of_month"


class MonthlyUpdateIndicatorStatus(str, Enum):
    """Per-indicator outcome for a monthly publication-update run."""

    SUCCESS = "success"
    FAILED = "failed"


class MonthlyUpdateIndicatorResult(TypedDict):
    """Per-indicator result from a monthly publication-update run."""

    name: str
    status: str


class MonthlyUpdateReport(TypedDict):
    """Summary returned by the monthly publication-update Celery task."""

    as_of: str
    status: str
    message: str
    checked: int
    updated: list[str]
    failed: list[str]
    results: list[MonthlyUpdateIndicatorResult]


def _build_monthly_update_skip_report(reference_date: date) -> MonthlyUpdateReport:
    """Return the skip report when the run is not on calendar day 1."""
    message = (
        f"Skipped: {reference_date.isoformat()} is not the first calendar day "
        f"of the month."
    )
    logger.info(message)
    return MonthlyUpdateReport(
        as_of=reference_date.isoformat(),
        status=MonthlyUpdateRunStatus.SKIPPED_NOT_FIRST_OF_MONTH.value,
        message=message,
        checked=0,
        updated=[],
        failed=[],
        results=[],
    )


def _build_monthly_update_report_from_ingest(
    *,
    reference_date: date,
    indicators: list[EconomicIndicatorInformationModel],
    not_updated: set[str],
) -> MonthlyUpdateReport:
    """Assemble the monthly update report from ingest success and failure names."""
    results: list[MonthlyUpdateIndicatorResult] = []
    updated: list[str] = []
    failed: list[str] = []
    for indicator in indicators:
        if indicator.full_name in not_updated:
            failed.append(indicator.full_name)
            results.append(
                MonthlyUpdateIndicatorResult(
                    name=indicator.full_name,
                    status=MonthlyUpdateIndicatorStatus.FAILED.value,
                )
            )
        else:
            updated.append(indicator.full_name)
            results.append(
                MonthlyUpdateIndicatorResult(
                    name=indicator.full_name,
                    status=MonthlyUpdateIndicatorStatus.SUCCESS.value,
                )
            )
    message = (
        f"Checked {len(indicators)} indicator(s): "
        f"{len(updated)} updated, {len(failed)} failed."
    )
    logger.info(message)
    return MonthlyUpdateReport(
        as_of=reference_date.isoformat(),
        status=MonthlyUpdateRunStatus.SUCCESS.value,
        message=message,
        checked=len(indicators),
        updated=updated,
        failed=failed,
        results=results,
    )


def run_monthly_publication_update(
    *,
    as_of: date | None = None,
    force: bool = False,
) -> MonthlyUpdateReport:
    """Update indicators tagged for monthly calendar-less refresh.

    Normally only runs on calendar day 1. Pass 'force=True' to run on any day
    (manual runs and tests).
    """
    reference_date = as_of if as_of is not None else get_local_today()
    if not force and reference_date.day != 1:
        return _build_monthly_update_skip_report(reference_date)

    indicators = list(_get_monthly_update_indicators())
    not_updated = set(ingest_latest_economic_data(indicators))
    return _build_monthly_update_report_from_ingest(
        reference_date=reference_date,
        indicators=indicators,
        not_updated=not_updated,
    )


def _list_derived_schedule_input_tickers(
    indicator: EconomicIndicatorInformationModel,
) -> list[str]:
    """Return same-location input tickers that gate a derived indicator's schedule."""
    if indicator.ticker == ANNUAL_GDP_GROWTH_TICKER:
        real_gdp = (
            EconomicIndicatorInformationModel.objects.filter(
                location=indicator.location,
                series_label="Real GDP",
                is_hidden=False,
            )
            .order_by("id")
            .first()
        )
        return [real_gdp.ticker] if real_gdp is not None else []
    # Same ticker can mean different inputs per location (e.g. US vs JP debt ratio).
    location_inputs = DERIVED_SCHEDULE_INPUT_TICKERS_BY_LOCATION_AND_TICKER.get(
        indicator.location, {}
    ).get(indicator.ticker)
    if location_inputs is not None:
        return list(location_inputs)
    return list(DERIVED_SCHEDULE_INPUT_TICKERS_BY_TICKER.get(indicator.ticker, []))


def _get_derived_publication_dates_from_inputs(
    indicator: EconomicIndicatorInformationModel,
) -> list[datetime]:
    """Build upcoming derived slots as the max (latest) among input schedules.

    A derived value is only available once every input for that period has
    landed, so each schedule slot uses the latest input release time.
    """
    input_tickers = _list_derived_schedule_input_tickers(indicator)
    if not input_tickers:
        return []

    input_schedules = list(
        PublicationScheduleModel.objects.filter(
            indicator__location=indicator.location,
            indicator__ticker__in=input_tickers,
        )
        .select_related("indicator")
        .order_by("indicator_id")
    )
    # Usage of dict: one schedule per input ticker (duplicates share a ticker).
    input_schedule_by_ticker: dict[str, PublicationScheduleModel] = {}
    for input_schedule in input_schedules:
        input_schedule_by_ticker.setdefault(
            input_schedule.indicator.ticker, input_schedule
        )
    if set(input_schedule_by_ticker) != set(input_tickers):
        logger.warning(
            "Derived schedule inputs incomplete for "
            f"{indicator.full_name}: need {input_tickers}"
        )
        return []

    current_candidates: list[datetime] = []
    next_candidates: list[datetime] = []
    for input_ticker in input_tickers:
        input_schedule = input_schedule_by_ticker[input_ticker]
        if input_schedule.current_publication_date is not None:
            current_candidates.append(input_schedule.current_publication_date)
        if input_schedule.next_publication_date is not None:
            next_candidates.append(input_schedule.next_publication_date)

    # Require a current slot from every input before publishing a derived current.
    if len(current_candidates) != len(input_tickers):
        return []

    upcoming: list[datetime] = [max(current_candidates)]
    if len(next_candidates) == len(input_tickers):
        upcoming.append(max(next_candidates))
    upcoming.sort()
    return upcoming


def _does_indicator_use_derived_publication_schedule(
    indicator: EconomicIndicatorInformationModel,
) -> bool:
    """Return True when this indicator's release slots come from input schedules."""
    return indicator.measure_type == IndicatorMeasureTypeChoices.DERIVED or (
        indicator.ticker in DERIVED_SCHEDULE_INPUT_TICKERS_BY_TICKER
        or indicator.ticker == ANNUAL_GDP_GROWTH_TICKER
        or indicator.ticker
        in DERIVED_SCHEDULE_INPUT_TICKERS_BY_LOCATION_AND_TICKER.get(
            indicator.location, {}
        )
    )


def _fetch_upcoming_publication_dates_for_indicator(
    indicator: EconomicIndicatorInformationModel,
) -> list[datetime]:
    """Scrape upcoming publication datetimes for one indicator."""
    if _does_indicator_use_derived_publication_schedule(
        indicator
    ) and _list_derived_schedule_input_tickers(indicator):
        derived_dates = _get_derived_publication_dates_from_inputs(indicator)
        if derived_dates:
            return derived_dates
    publication_function = PUBLICATION_SOURCE_MAP.get(
        EconomicDataSourceChoices(indicator.source)
    )
    if not publication_function:
        raise ValueError(
            f"Publication function not found for indicator: {indicator.full_name}"
        )
    calendar_technical_name = (
        DERIVED_SCHEDULE_CALENDAR_TECHNICAL_NAME_BY_TICKER.get(indicator.ticker)
        or indicator.technical_name
    )
    return publication_function(
        _PublicationScheduleLookup(
            technical_name=calendar_technical_name,
            location=indicator.location,
        )
    )


def _roll_publication_schedule_forward(
    publication_schedule: PublicationScheduleModel,
    next_publication_dates: list[datetime],
) -> None:
    """Roll previous / current / next slots forward from scraped upcoming dates."""
    publication_schedule.previous_publication_date = (
        publication_schedule.current_publication_date
    )
    # Upcoming dates are earliest-first; index 0 becomes the new current.
    publication_schedule.current_publication_date = next_publication_dates[0]
    # Index 1 is the following slot (next), when the source returned more than one date.
    publication_schedule.next_publication_date = (
        next_publication_dates[1] if len(next_publication_dates) > 1 else None
    )
    publication_schedule.save()


def _update_publication_schedule(
    indicator: EconomicIndicatorInformationModel,
) -> PublicationScheduleModel | None:
    """Update publication schedule.

    When 'current' has passed, move it to 'previous' and advance 'current' /
    'next' from the source scrape so market-recap day events still match the
    release calendar day via 'previous_publication_date'.
    """
    logger.info(f"Updating publication schedule for indicator: {indicator.full_name}")
    if (
        indicator.publication_schedule_mode
        == PublicationScheduleModeChoices.MONTHLY_UPDATE
    ):
        logger.info(
            "Skipping calendar scrape for monthly-update indicator: %s",
            indicator.full_name,
        )
        return None
    publication_schedule, _created = PublicationScheduleModel.objects.get_or_create(
        indicator=indicator
    )
    if (
        publication_schedule.current_publication_date
        and publication_schedule.current_publication_date > timezone.now()
    ):
        logger.info(
            f"Current publication date for indicator: {indicator.full_name} is not reached. Skipping update."
        )
        return publication_schedule

    next_publication_dates = _fetch_upcoming_publication_dates_for_indicator(indicator)
    if not next_publication_dates:
        logger.warning(
            f"No publication dates found for indicator: {indicator.full_name}"
        )
        return publication_schedule

    _roll_publication_schedule_forward(publication_schedule, next_publication_dates)
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
    Derived indicators are updated after sourced ones so input schedules exist.
    """
    indicator_list = list(indicators)

    def _is_derived_schedule_indicator(
        indicator: EconomicIndicatorInformationModel,
    ) -> bool:
        """True when this indicator's schedule should follow input series."""
        return (
            indicator.measure_type == IndicatorMeasureTypeChoices.DERIVED
            or indicator.ticker in DERIVED_SCHEDULE_INPUT_TICKERS_BY_TICKER
            or indicator.ticker
            in DERIVED_SCHEDULE_INPUT_TICKERS_BY_LOCATION_AND_TICKER.get(
                indicator.location, {}
            )
            or indicator.ticker == ANNUAL_GDP_GROWTH_TICKER
            or indicator.ticker in DERIVED_SCHEDULE_CALENDAR_TECHNICAL_NAME_BY_TICKER
        )

    sourced_indicators = [
        indicator
        for indicator in indicator_list
        if not _is_derived_schedule_indicator(indicator)
    ]
    derived_indicators = [
        indicator
        for indicator in indicator_list
        if _is_derived_schedule_indicator(indicator)
    ]

    schedules_not_updated = []
    for indicator in sourced_indicators + derived_indicators:
        try:
            schedule_not_updated = _update_publication_schedule(indicator)
            if schedule_not_updated:
                schedules_not_updated.append(indicator.full_name)
        except Exception:
            logger.exception(
                "Failed to update publication schedule for indicator: %s",
                indicator.full_name,
            )
            schedules_not_updated.append(indicator.full_name)
    return schedules_not_updated


def get_publication_schedules_for_dates(
    start_date: date | None = None,
    end_date: date | None = None,
) -> QuerySet[PublicationScheduleModel, PublicationScheduleModel]:
    """Get publication schedules, optionally between dates."""
    queryset = PublicationScheduleModel.objects.filter(indicator__is_hidden=False)
    if start_date:
        queryset = queryset.filter(current_publication_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(current_publication_date__lt=end_date)
    return queryset.all()
