"""API views for holiday ingestion and lookup."""

from datetime import date
from typing import TypedDict

from rest_framework import status
from rest_framework.response import Response

import market_overview.services.holidays as holidays
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services import logger
from core.views import BaseAPIView
from market_overview.models import LocationChoices
from market_overview.open_api.request_serializers import (
    DeleteHolidaysSerializer,
    IngestHolidaysSerializer,
    ListHolidaysSerializer,
)
from market_overview.open_api.response_serializers import HolidayResponseSerializer
from market_overview.services.config import HOLIDAY_COUNTRIES


class _IngestHolidaysValidatedData(TypedDict, total=False):
    """Validated data for ``IngestHolidaysSerializer``."""

    date: date
    location: LocationChoices


class IngestHolidaysView(BaseAPIView):
    """Ingest Holidays APIView."""

    @open_api(
        tags=[ApiTags.HOLIDAYS],
        summary="Ingest Holidays",
        description="Ingest holidays for a given year and country code from external API.",
        request_serializer=IngestHolidaysSerializer,
        response=CreatedOpenApiResponse(),
        error_responses=[BadRequestOpenApiResponse("Invalid location or date.")],
    )
    def post(self, validated_data: _IngestHolidaysValidatedData) -> Response:
        """Ingest holidays for a given year and country code."""
        holiday_date: date = validated_data.get("date", date.today())
        location_raw = validated_data.get("location")
        location = LocationChoices(location_raw) if location_raw else None

        all_locations = HOLIDAY_COUNTRIES if not location else [location]
        for location in all_locations:
            logger.info(
                f"Ingesting holidays for {location.value} starting from {holiday_date}"
            )
            holidays.ingest_one_year_holidays(holiday_date, location)
        return Response(
            data={"message": "Holidays successfully ingested."},
            status=status.HTTP_201_CREATED,
        )


class _ListHolidaysValidatedData(TypedDict, total=False):
    """Validated data for ``ListHolidaysSerializer``."""

    location: LocationChoices
    year: int
    months: list[int]


class _DeleteHolidaysValidatedData(TypedDict):
    """Validated data for ``DeleteHolidaysSerializer``."""

    date: date


class HolidaysDetailsView(BaseAPIView):
    """Holidays Details APIView."""

    @open_api(
        tags=[ApiTags.HOLIDAYS],
        summary="List Holidays",
        description=("List holidays for a given date and country code."),
        request_serializer=ListHolidaysSerializer,
        response=OkOpenApiResponse(HolidayResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("Invalid month.")],
    )
    def get(self, validated_data: _ListHolidaysValidatedData) -> Response:
        """List holidays for a given year, country code, and optionally by months."""
        location_raw = validated_data.get("location")
        location = LocationChoices(location_raw) if location_raw else None
        year: int | None = validated_data.get("year")
        months = validated_data.get("months") or []

        holiday_rows = holidays.get_holidays(
            location=location, year=year, months=months
        )
        return Response(
            data=HolidayResponseSerializer(holiday_rows, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.HOLIDAYS],
        summary="Delete Holidays",
        description="Delete holidays before a given year.",
        request_serializer=DeleteHolidaysSerializer,
        error_responses=[BadRequestOpenApiResponse("date is required")],
    )
    def delete(self, validated_data: _DeleteHolidaysValidatedData) -> Response:
        """Delete holidays before a given year."""
        holiday_date: date = validated_data["date"]

        holidays.delete_holidays_before_date(holiday_date)
        return Response(
            data={"message": "Holidays successfully deleted."},
            status=status.HTTP_200_OK,
        )
