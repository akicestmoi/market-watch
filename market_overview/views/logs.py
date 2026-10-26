"""API views for price update / ingestion logs."""

from datetime import date
from typing import TypedDict

from rest_framework import status
from rest_framework.response import Response

import core.services as core_services
import market_overview.services.market_data as market_data
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_overview.models import AssetModel
from market_overview.open_api.request_serializers import GetPriceUpdateLogsSerializer
from market_overview.open_api.response_serializers import (
    PriceUpdateLogResponseSerializer,
)


class GetPriceUpdateLogsValidatedData(TypedDict, total=False):
    """Validated data for ``GetPriceUpdateLogsSerializer``."""

    price_date: date
    short_name: str


class GetPriceUpdateLogsView(BaseAPIView):
    """Get Price Update Logs APIView."""

    @open_api(
        tags=[ApiTags.LOGS],
        summary="Get Market Price Change Logs",
        description="Get price update logs with optional filtering.",
        request_serializer=GetPriceUpdateLogsSerializer,
        response=OkOpenApiResponse(PriceUpdateLogResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid price_date."),
            NotFoundOpenApiResponse("Asset not found"),
        ],
    )
    def get(self, validated_data: GetPriceUpdateLogsValidatedData) -> Response:
        """Get price update logs with optional filtering."""
        price_date: date | None = validated_data.get("price_date")
        short_name: str | None = validated_data.get("short_name")

        if short_name:
            core_services.get(AssetModel, short_name=short_name)

        price_update_logs = market_data.get_price_update_logs(
            price_date=price_date, short_name=short_name
        )
        return Response(
            data=PriceUpdateLogResponseSerializer(price_update_logs, many=True).data,
            status=status.HTTP_200_OK,
        )
