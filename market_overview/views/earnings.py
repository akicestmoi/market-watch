"""Serve earnings watchlist ingest, refresh, and lookup endpoints."""

from datetime import date
from typing import NotRequired, TypedDict

from rest_framework import status
from rest_framework.response import Response

import market_overview.services.earnings as earnings
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services.calendar import get_market_watch_as_of_date
from core.services.locks import release_redis_lock, try_acquire_redis_lock
from core.views import BaseAPIView
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.open_api.request_serializers import (
    GetEarningsWatchlistSerializer,
    IngestEarningsWatchlistSerializer,
    RefreshEarningsWatchlistSerializer,
)
from market_overview.open_api.response_serializers import (
    EarningsWatchlistRunResponseSerializer,
    GetEarningsWatchlistResponseSerializer,
)


class _EarningsWatchlistRunResponse(TypedDict):
    """Hold the JSON body returned after an earnings ingest or refresh."""

    message: str
    as_of: str
    earnings_results: list[earnings.EarningsIngestionResult]
    weight_results: list[earnings.EarningsIngestionResult]
    tickers_failed: list[str]


class _IngestEarningsWatchlistValidatedData(TypedDict):
    """Validated data for 'IngestEarningsWatchlistSerializer'."""

    equity_index: NotRequired[str]


class IngestEarningsWatchlistView(BaseAPIView):
    """Ingest earnings: update, refresh weights, and roll on T+1."""

    @open_api(
        tags=[ApiTags.SECTOR_ANALYSIS],
        summary="Ingest earnings watchlist",
        description=(
            "Scrape Yahoo Finance and update upcoming / current / previous with "
            "T+1 roll, then refresh index weights."
        ),
        request_serializer=IngestEarningsWatchlistSerializer,
        response=CreatedOpenApiResponse(EarningsWatchlistRunResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("equity_index is not a valid choice"),
            ConflictOpenApiResponse(
                "Earnings watchlist ingestion already in progress."
            ),
        ],
    )
    def post(self, validated_data: _IngestEarningsWatchlistValidatedData) -> Response:
        """Ingest earnings and weights for the full watchlist or one equity index."""
        lock_key = earnings.get_lock_key_for_earnings_watchlist_ingestion()
        lock = try_acquire_redis_lock(lock_key)
        if lock is None:
            return Response(
                data={"message": "Earnings watchlist ingestion already in progress."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            equity_index_raw = validated_data.get("equity_index")
            equity_index = (
                EquityIndexChoices(equity_index_raw) if equity_index_raw else None
            )
            run_result = earnings.ingest_earnings_watchlist(
                as_of=get_market_watch_as_of_date(),
                equity_index=equity_index,
            )
            return Response(
                data=_EarningsWatchlistRunResponse(
                    message=(
                        "Earnings watchlist ingested and weights refreshed "
                        "successfully."
                    ),
                    as_of=run_result["as_of"],
                    earnings_results=run_result["earnings_results"],
                    weight_results=run_result["weight_results"],
                    tickers_failed=run_result["tickers_failed"],
                ),
                status=status.HTTP_201_CREATED,
            )
        finally:
            release_redis_lock(lock, lock_key)


class _RefreshEarningsWatchlistValidatedData(TypedDict):
    """Validated data for 'RefreshEarningsWatchlistSerializer'."""

    as_of: NotRequired[date]
    equity_index: NotRequired[str]


class RefreshEarningsWatchlistView(BaseAPIView):
    """Refresh earnings: update upcoming and weights without rolling."""

    @open_api(
        tags=[ApiTags.SECTOR_ANALYSIS],
        summary="Refresh earnings watchlist",
        description=(
            "Scrape Yahoo upcoming estimates and index weight proxies. Updates "
            "upcoming_* and weight_pct only — never rolls current_* / previous_*."
        ),
        request_serializer=RefreshEarningsWatchlistSerializer,
        response=CreatedOpenApiResponse(EarningsWatchlistRunResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "as_of is not a valid date | equity_index is not a valid choice"
            ),
            ConflictOpenApiResponse("Earnings watchlist refresh already in progress."),
        ],
    )
    def post(self, validated_data: _RefreshEarningsWatchlistValidatedData) -> Response:
        """Refresh upcoming estimates and weights for all indexes or one index."""
        lock_key = earnings.get_lock_key_for_earnings_watchlist_refresh()
        lock = try_acquire_redis_lock(lock_key)
        if lock is None:
            return Response(
                data={"message": "Earnings watchlist refresh already in progress."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            as_of = validated_data.get("as_of") or get_market_watch_as_of_date()
            equity_index_raw = validated_data.get("equity_index")
            equity_index = (
                EquityIndexChoices(equity_index_raw) if equity_index_raw else None
            )
            run_result = earnings.refresh_earnings_watchlist(as_of, equity_index)
            return Response(
                data=_EarningsWatchlistRunResponse(
                    message=(
                        "Earnings watchlist upcoming estimates and weights "
                        "refreshed successfully."
                    ),
                    as_of=run_result["as_of"],
                    earnings_results=run_result["earnings_results"],
                    weight_results=run_result["weight_results"],
                    tickers_failed=run_result["tickers_failed"],
                ),
                status=status.HTTP_201_CREATED,
            )
        finally:
            release_redis_lock(lock, lock_key)


class _GetEarningsWatchlistResponse(TypedDict):
    """Hold stored earnings watchlist companies returned for one region."""

    location: str
    companies: list[earnings.EarningsWatchlistCompany]


class _GetEarningsWatchlistValidatedData(TypedDict):
    """Validated data for 'GetEarningsWatchlistSerializer'."""

    location: str


class GetEarningsWatchlistView(BaseAPIView):
    """Get stored earnings watchlist companies for one region."""

    @open_api(
        tags=[ApiTags.SECTOR_ANALYSIS],
        summary="Get earnings watchlist",
        description=(
            "Return stored upcoming, current, and previous earnings for watchlist "
            "companies in one US / FR / JP region, sorted by index weight."
        ),
        request_serializer=GetEarningsWatchlistSerializer,
        response=OkOpenApiResponse(GetEarningsWatchlistResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "location is required | location must be US, FR, or JP"
            ),
        ],
    )
    def get(self, validated_data: _GetEarningsWatchlistValidatedData) -> Response:
        """Return stored earnings watchlist companies for the requested location."""
        response_body = _GetEarningsWatchlistResponse(
            location=validated_data["location"],
            companies=earnings.list_earnings_watchlist_companies_for_location(
                LocationChoices(validated_data["location"])
            ),
        )
        return Response(
            data=GetEarningsWatchlistResponseSerializer(response_body).data,
            status=status.HTTP_200_OK,
        )
