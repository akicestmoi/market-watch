from datetime import date
from typing import Optional

from rest_framework import status
from rest_framework.response import Response

import market_overview.services.market_data_services as market_data_services
from core.open_api import ApiTags, NotFoundOpenApiResponse, OkOpenApiResponse, open_api
from core.views import BaseAPIView
from market_overview.open_api.request_serializers import GetPriceUpdateLogsSerializer
from market_overview.open_api.response_serializers import (
    PriceUpdateLogResponseSerializer,
)


class GetPriceUpdateLogsView(BaseAPIView):
    """Get Price Update Logs APIView."""

    @open_api(
        tags=[ApiTags.LOGS],
        summary="Get Market Price Change Logs",
        description="Get price update logs with optional filtering.",
        request_serializer=GetPriceUpdateLogsSerializer,
        response=OkOpenApiResponse(PriceUpdateLogResponseSerializer),
        error_responses=[NotFoundOpenApiResponse("Asset not found")],
    )
    def get(self, validated_data: dict) -> Response:
        """Get price update logs with optional filtering."""
        price_date: Optional[date] = validated_data.get("price_date")
        short_name: Optional[str] = validated_data.get("short_name")

        if short_name and not market_data_services.check_asset_existence(short_name):
            return Response(
                {"error_message": f"Asset: {short_name} does not exist in database."},
                status=status.HTTP_404_NOT_FOUND,
            )

        price_update_logs = market_data_services.get_price_update_logs(
            price_date=price_date, short_name=short_name
        )
        return Response(
            data=PriceUpdateLogResponseSerializer(price_update_logs, many=True).data,
            status=status.HTTP_200_OK,
        )
