"""Serve sector-analysis ingestion and lookup endpoints."""

from datetime import date
from typing import NotRequired, TypedDict

from rest_framework import status
from rest_framework.response import Response

import market_overview.services.sector_analysis as sector_analysis
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services.locks import release_redis_lock, try_acquire_redis_lock
from core.views import BaseAPIView
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.open_api.request_serializers import (
    GetSectorAnalysisSerializer,
    IngestSectorAnalysisSerializer,
)
from market_overview.open_api.response_serializers import (
    GetSectorAnalysisResponseSerializer,
    IngestSectorAnalysisResponseSerializer,
)


class _IngestSectorAnalysisValidatedData(TypedDict):
    """Validated data for 'IngestSectorAnalysisSerializer'."""

    start_date: date
    end_date: date
    equity_index: NotRequired[str]


class IngestSectorAnalysisView(BaseAPIView):
    """Ingest sector-analysis subsector day moves for a date window."""

    @open_api(
        tags=[ApiTags.SECTOR_ANALYSIS],
        summary="Ingest sector analysis",
        description=(
            "Scrape single-name closes and index-weight proxies, aggregate to "
            "subsector weight / return / contribution, and store every trading "
            "day in [start_date, end_date] inclusive."
        ),
        request_serializer=IngestSectorAnalysisSerializer,
        response=CreatedOpenApiResponse(IngestSectorAnalysisResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "start_date is required | end_date is required | "
                "end_date must be greater than or equal to start_date. | "
                "equity_index is not a valid choice"
            ),
            ConflictOpenApiResponse(
                "Sector analysis ingestion already in progress for this date window."
            ),
        ],
    )
    def post(self, validated_data: _IngestSectorAnalysisValidatedData) -> Response:
        """Ingest sector analysis for a date window, optionally one equity index."""
        start_date = validated_data["start_date"]
        end_date = validated_data["end_date"]
        equity_index_raw = validated_data.get("equity_index")
        lock_key = sector_analysis.get_lock_key_for_sector_analysis_ingestion(
            start_date,
            end_date,
        )
        lock = try_acquire_redis_lock(lock_key)
        if lock is None:
            return Response(
                data={
                    "message": (
                        "Sector analysis ingestion already in progress for "
                        f"{start_date.isoformat()} .. {end_date.isoformat()}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            if equity_index_raw:
                results = sector_analysis.ingest_equity_index_subsector_daily_moves_for_date_range(
                    EquityIndexChoices(equity_index_raw),
                    start_date,
                    end_date,
                )
            else:
                results = sector_analysis.ingest_all_equity_index_subsector_daily_moves_for_date_range(
                    start_date,
                    end_date,
                )
            return Response(
                data={
                    "message": (
                        "Sector analysis ingested successfully for "
                        f"{start_date.isoformat()} .. {end_date.isoformat()}."
                    ),
                    "results": results,
                },
                status=status.HTTP_201_CREATED,
            )
        finally:
            release_redis_lock(lock, lock_key)


class _GetSectorAnalysisValidatedData(TypedDict):
    """Validated data for 'GetSectorAnalysisSerializer'."""

    date: date
    location: str


class GetSectorAnalysisView(BaseAPIView):
    """Get stored subsector day moves for one region and trading day."""

    @open_api(
        tags=[ApiTags.SECTOR_ANALYSIS],
        summary="Get sector analysis",
        description=(
            "Return stored subsector weight, return, contribution, and top movers "
            "for one US / FR / JP region on a trading day."
        ),
        request_serializer=GetSectorAnalysisSerializer,
        response=OkOpenApiResponse(GetSectorAnalysisResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "date is required | location is required | "
                "location must be US, FR, or JP"
            ),
        ],
    )
    def get(self, validated_data: _GetSectorAnalysisValidatedData) -> Response:
        """Return stored subsector day moves for the requested location and date."""
        payload = sector_analysis.list_subsector_daily_moves_for_location_on_date(
            LocationChoices(validated_data["location"]),
            validated_data["date"],
        )
        return Response(
            data=GetSectorAnalysisResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )
