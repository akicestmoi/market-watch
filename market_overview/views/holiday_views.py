from datetime import date
from typing import Optional

from rest_framework import status
from rest_framework.response import Response

import market_overview.services.holiday_services as holiday_services
from core.open_api import ApiTags, CreatedOpenApiResponse, OkOpenApiResponse, open_api
from core.services import logger
from core.views import BaseAPIView
from market_overview.models import LocationChoices
from market_overview.open_api.request_serializers import (
    DeleteHolidaysSerializer,
    IngestHolidaysSerializer,
    ListHolidaysSerializer,
)
from market_overview.open_api.response_serializers import HolidayResponseSerializer
from market_overview.services.holiday_services import HOLIDAY_COUNTRIES


class IngestHolidaysView(BaseAPIView):
    """Ingest Holidays APIView."""

    @open_api(
        tags=[ApiTags.HOLIDAYS],
        summary="Ingest Holidays",
        description="Ingest holidays for a given year and country code from external API.",
        request_serializer=IngestHolidaysSerializer,
        response=CreatedOpenApiResponse(),
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest holidays for a given year and country code."""
        holiday_date: date = validated_data.get("date", date.today())
        location_str: Optional[str] = validated_data.get("location")
        location: Optional[LocationChoices] = (
            LocationChoices(location_str) if location_str else None
        )

        all_locations = HOLIDAY_COUNTRIES if not location else [location]
        for location in all_locations:
            logger.info(
                f"Ingesting holidays for {location.value} starting from {holiday_date}"
            )
            holiday_services.ingest_one_year_holidays(holiday_date, location)
        return Response(
            data={"message": "Holidays successfully ingested."},
            status=status.HTTP_201_CREATED,
        )


class HolidaysDetailsView(BaseAPIView):
    """Holidays Details APIView."""

    @open_api(
        tags=[ApiTags.HOLIDAYS],
        summary="List Holidays",
        description=("List holidays for a given date and country code."),
        request_serializer=ListHolidaysSerializer,
        response=OkOpenApiResponse(HolidayResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List holidays for a given year, country code, and optionally by months."""
        location: Optional[str] = validated_data.get("location")
        year: Optional[int] = validated_data.get("year")
        months_str: Optional[str] = validated_data.get("months")
        months = [int(month) for month in months_str.split(",")] if months_str else []

        holidays = holiday_services.get_holidays(
            location=location, year=year, months=months
        )
        return Response(
            data=HolidayResponseSerializer(holidays, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.HOLIDAYS],
        summary="Delete Holidays",
        description="Delete holidays before a given year.",
        request_serializer=DeleteHolidaysSerializer,
    )
    def delete(self, validated_data: dict) -> Response:
        """Delete holidays before a given year."""
        holiday_date: date = validated_data["date"]

        holiday_services.delete_holidays_before_date(holiday_date)
        return Response(
            data={"message": "Holidays successfully deleted."},
            status=status.HTTP_200_OK,
        )
