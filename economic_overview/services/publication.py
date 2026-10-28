"""Manage and scrape economic publication schedules."""

import json
from datetime import date, datetime, timedelta
from typing import TypedDict

import pandas as pd
import requests
from cachetools.func import ttl_cache
from django.db.models import QuerySet
from django.utils import timezone
from pydantic import TypeAdapter, ValidationError

import core.services as core_services
from core.services import CACHE_MAXSIZE, CACHE_TTL_SECONDS, logger
from economic_overview.models import (
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)

PUBLICATION_SOURCE_MAP = {
    EconomicDataSourceChoices.INSEE: lambda n: _get_publication_dates_from_insee(n),
    EconomicDataSourceChoices.EUROSTAT: lambda n: _get_publication_dates_from_eurostat(
        n
    ),
    EconomicDataSourceChoices.JP_CABINET_OFFICE: lambda n: _get_publication_dates_from_japan_cabinet_office(
        n
    ),
}

EUROSTAT_PUBLICATION_SCHEDULE_URL = (
    "https://ec.europa.eu/eurostat/o/calendars/eventsJson"
)
# FullCalendar feed is range-bounded; ~13 months covers monthly euro-indicators.
EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS = 400


class InseeAgendaSortField(TypedDict):
    """Sort field for the INSEE agenda-diffusion search request."""

    field: str
    order: str


class InseeAgendaRequest(TypedDict):
    """POST body for https://www.insee.fr/fr/agenda-diffusion."""

    q: str
    start: int
    sortFields: list[InseeAgendaSortField]
    filters: list[str]
    rows: int
    facetsQuery: list[str]


class InseeAgendaFacetteConjoncture(TypedDict, total=False):
    """Nested INSEE facetteConjoncture block (fields we read)."""

    libelleEn: str


class InseeAgendaFamille(TypedDict, total=False):
    """Nested INSEE famille block (fields we read)."""

    facetteConjoncture: InseeAgendaFacetteConjoncture


class InseeAgendaDocument(TypedDict, total=False):
    """One INSEE agenda document (fields we read)."""

    famille: InseeAgendaFamille
    embargo: str


class InseeAgendaResponse(TypedDict, total=False):
    """INSEE agenda-diffusion JSON root (fields we read)."""

    documents: list[InseeAgendaDocument]


class InseePublicationScheduleRow(TypedDict):
    """One normalized INSEE publication schedule row before DataFrame load."""

    name: str
    publication_date: str | None


_INSEE_AGENDA_RESPONSE_ADAPTER = TypeAdapter(InseeAgendaResponse)


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_insee_publication_schedule() -> pd.DataFrame:
    """Get INSEE publication schedule.

    Source: https://www.insee.fr/fr/agenda-diffusion
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
    INSEE_PUBLICATION_SCHEDULE_URL = "https://www.insee.fr/fr/agenda-diffusion"
    payload = InseeAgendaRequest(
        q="*:*",
        start=0,
        sortFields=[{"field": "dateEmbargo_dt", "order": "asc"}],
        filters=[],
        rows=100,
        facetsQuery=[],
    )
    response = requests.post(INSEE_PUBLICATION_SCHEDULE_URL, json=payload)
    if response.status_code >= 400:
        logger.warning(f"Error scraping INSEE publication schedule: {response.text}")
        return default_df

    try:
        raw_payload = json.loads(response.content)
        agenda = _INSEE_AGENDA_RESPONSE_ADAPTER.validate_python(raw_payload)
    except (TypeError, json.JSONDecodeError, ValidationError):
        logger.warning("Invalid INSEE publication schedule JSON")
        return default_df

    records: list[InseePublicationScheduleRow] = []
    for document in agenda.get("documents", []):
        famille = document.get("famille", {})
        facette = famille.get("facetteConjoncture", {}) if famille else {}
        records.append(
            InseePublicationScheduleRow(
                name=facette.get("libelleEn", "") if facette else "",
                publication_date=document.get("embargo"),
            )
        )

    df = pd.DataFrame(records)
    if df.empty:
        return default_df
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_publication_dates_from_insee(name: str) -> list[datetime]:
    """Get publication dates from INSEE."""
    publication_schedule = _get_insee_publication_schedule()
    publication_dates = publication_schedule[publication_schedule["name"] == name][
        "publication_date"
    ]
    return [
        pd_timestamp.to_pydatetime() for pd_timestamp in publication_dates.tolist()[:2]
    ]


class EurostatCalendarEvent(TypedDict, total=False):
    """One FullCalendar event from Eurostat eventsJson (fields we read)."""

    title: str
    start: str


class EurostatPublicationScheduleRow(TypedDict):
    """One normalized Eurostat publication schedule row before DataFrame load."""

    name: str
    publication_date: str | None


_EUROSTAT_CALENDAR_EVENTS_ADAPTER = TypeAdapter(list[EurostatCalendarEvent])


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_eurostat_publication_schedule() -> pd.DataFrame:
    """Get Eurostat publication schedule.

    Source: https://ec.europa.eu/eurostat/news/release-calendar/
    JSON feed: https://ec.europa.eu/eurostat/o/calendars/eventsJson
    Event ``start`` values are UTC (``…Z``); the UI labels Europe/Luxembourg.
    """
    default_df = pd.DataFrame(columns=["name", "publication_date"])
    range_start = timezone.now()
    range_end = range_start + timedelta(days=EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS)
    response = requests.get(
        EUROSTAT_PUBLICATION_SCHEDULE_URL,
        params={
            "start": range_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": range_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Eurostat publication schedule: {response.text}")
        return default_df

    try:
        raw_payload = json.loads(response.content)
        events = _EUROSTAT_CALENDAR_EVENTS_ADAPTER.validate_python(raw_payload)
    except (TypeError, json.JSONDecodeError, ValidationError):
        logger.warning("Invalid Eurostat publication schedule JSON")
        return default_df

    records: list[EurostatPublicationScheduleRow] = []
    for event in events:
        records.append(
            EurostatPublicationScheduleRow(
                name=event.get("title", ""),
                publication_date=event.get("start"),
            )
        )

    df = pd.DataFrame(records)
    if df.empty:
        return default_df
    df["publication_date"] = pd.to_datetime(df["publication_date"], utc=True)
    df = df.sort_values("publication_date").reset_index(drop=True)
    return df


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_publication_dates_from_eurostat(name: str) -> list[datetime]:
    """Get publication dates from Eurostat."""
    publication_schedule = _get_eurostat_publication_schedule()
    publication_dates = publication_schedule[publication_schedule["name"] == name][
        "publication_date"
    ]
    return [
        pd_timestamp.to_pydatetime() for pd_timestamp in publication_dates.tolist()[:2]
    ]


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_publication_dates_from_japan_cabinet_office(name: str) -> list[datetime]:
    """Get publication dates from Japan Cabinet Office."""
    raise NotImplementedError("Not implemented.")


def _update_publication_schedule(
    indicator: EconomicIndicatorInformationModel,
) -> PublicationScheduleModel | None:
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
