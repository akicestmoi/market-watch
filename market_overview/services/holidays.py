"""Fetch and ingest public holidays used for price completeness checks."""

from datetime import date, datetime, timedelta
from typing import TypedDict

import requests
from django.db.models import QuerySet

from core.services import logger
from market_overview.models import HolidayModel, LocationChoices

HOLIDAY_COUNTRIES: list[LocationChoices] = [
    LocationChoices.US,
    LocationChoices.FR,
    LocationChoices.JP,
]
HOLIDAY_API_URL = "https://date.nager.at/api/v3/publicholidays/"


class HolidayApiItem(TypedDict):
    """One public holiday from the Nager.Date API (fields we consume)."""

    date: str
    localName: str
    countryCode: str


def _call_holiday_api(year: int, location: LocationChoices) -> list[HolidayApiItem]:
    """Call the holiday API for a given year and location."""
    url = f"{HOLIDAY_API_URL}{year}/{location.value}"
    response = requests.get(url)
    response.raise_for_status()
    items: list[HolidayApiItem] = []
    for entry in response.json():
        items.append(
            HolidayApiItem(
                date=entry["date"],
                localName=entry["localName"],
                countryCode=entry["countryCode"],
            )
        )
    return items


def _ingest_holidays(
    year: int,
    location: LocationChoices,
    filter_start_date: date | None,
    filter_end_date: date | None,
):
    """Ingest holidays for a given country code."""
    data = _call_holiday_api(year, location)
    for holiday in data:
        holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
        if filter_start_date and holiday_date < filter_start_date:
            continue
        if filter_end_date and holiday_date > filter_end_date:
            continue
        HolidayModel.objects.update_or_create(
            date=holiday_date,
            name=holiday["localName"],
            location=holiday["countryCode"],
        )


def ingest_one_year_holidays(holiday_start_date: date, location: LocationChoices):
    """Ingest one year of holidays for a given country code."""
    holiday_end_date = holiday_start_date + timedelta(days=364)
    holiday_years = set([holiday_start_date.year, holiday_end_date.year])

    for year in holiday_years:
        logger.info(f"Ingesting holidays for {location} in {year}")
        _ingest_holidays(year, location, holiday_start_date, holiday_end_date)


def get_holidays(
    location: LocationChoices | None = None,
    year: int | None = None,
    months: list[int] = [],
) -> QuerySet[HolidayModel, HolidayModel]:
    """Get holidays for a given year, location, and months."""
    queryset = HolidayModel.objects.all()
    if location:
        queryset = queryset.filter(location=location)
    if year:
        queryset = queryset.filter(date__year=year)
    if months:
        queryset = queryset.filter(date__month__in=months)
    return queryset


def delete_holidays_before_date(holiday_date: date):
    """Delete holidays before a given date."""
    HolidayModel.objects.filter(date__lt=holiday_date).delete()
