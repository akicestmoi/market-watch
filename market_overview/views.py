from datetime import date
from enum import Enum
from typing import Optional

from pandas.tseries.offsets import BDay
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

import market_overview.services as market_overview_services
import shared.services as shared_services
from market_overview.models import (
    AssetTypeChoices,
    MarketPriceModel,
    PriceUpdateLogModel,
)
from market_overview.open_api import (
    BULK_UPDATE_ASSETS_PRICES_SCHEMA,
    CALCULATE_PRICE_CHANGE_SCHEMA,
    GET_ASSET_NAMES_SCHEMA,
    GET_ASSETS_WITHOUT_PRICES_SCHEMA,
    GET_HISTORICAL_PRICES_SCHEMA,
    GET_MARKET_PRICE_DATA_SCHEMA,
    GET_PRICE_UPDATE_LOGS_SCHEMA,
    GET_YIELD_CURVE_SCHEMA,
    INGEST_ASSET_DATA_SCHEMA,
    INGEST_DATA_SCHEMA,
    UPDATE_MARKET_PRICE_DATA_SCHEMA,
)
from market_overview.serializers import (
    BulkUpdateAssetsPricesSerializer,
    CalculatePriceDiffSerializer,
    DataCorrectionSerializer,
    MarketPriceIngestionSerializer,
    TargetedMarketPriceIngestionSerializer,
)
from shared.open_api import open_api
from shared.utils import logger
from shared.views import BaseAPIView


class GetActionEnum(str, Enum):
    """Get Action Enum"""

    GET = "GET"
    LIST = "LIST"


class IngestDataView(BaseAPIView):
    """Ingest Data APIView."""

    @open_api(INGEST_DATA_SCHEMA)
    def post(self, request: Request) -> Response:
        """Ingest market prices gathered from various sources."""
        serializer = MarketPriceIngestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_date: date = serializer.validated_data.get("date")
        logger.info(f"Ingesting market data for date: {price_date}")
        market_data = market_overview_services.get_market_data(price_date)
        asset_not_updated = market_overview_services.ingest_market_data(market_data)
        return Response(
            data={
                "message": "Market prices successfully ingested",
                "asset_not_updated": [data["short_name"] for data in asset_not_updated],
                "date": price_date,
            },
            status=status.HTTP_201_CREATED,
        )


class IngestAssetDataView(BaseAPIView):
    """Ingest Specific Asset Data APIView."""

    @open_api(INGEST_ASSET_DATA_SCHEMA)
    def post(self, request: Request) -> Response:
        """Ingest market prices gathered from a specific source for a target period."""
        serializer = TargetedMarketPriceIngestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        short_name: date = serializer.validated_data.get("short_name")
        start_date: date = serializer.validated_data.get("start_date")
        end_date: date = serializer.validated_data.get(
            "end_date", (date.today() - BDay(1)).date()
        )

        if end_date <= start_date:
            return Response(
                {"error": "end_date must be greater than start_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not market_overview_services.check_asset_existence(short_name):
            return Response(
                {"error": f"asset: {short_name} does not exist in database."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        market_data = market_overview_services.get_specific_asset_market_data(
            short_name, start_date, end_date
        )
        asset_not_updated = market_overview_services.ingest_market_data(market_data)
        return Response(
            data={
                "message": "Asset prices successfully ingested",
                "asset_not_updated": [data["date"] for data in asset_not_updated],
            },
            status=status.HTTP_201_CREATED,
        )


class CalculatePriceChangeView(BaseAPIView):
    """Calculate Price Change APIView."""

    @open_api(CALCULATE_PRICE_CHANGE_SCHEMA)
    def post(self, request: Request) -> Response:
        """Calculate price change for all assets between two dates."""
        serializer = CalculatePriceDiffSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference_date: date = serializer.validated_data.get("reference_date")
        previous_date: date = serializer.validated_data.get("previous_date")
        if reference_date <= previous_date:
            return Response(
                {"error": "reference_date must be greater than previous_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference_market_prices = (
            market_overview_services.get_all_asset_prices_for_date(reference_date)
        )
        if not reference_market_prices:
            return Response(
                {"error": f"No data found for reference date: {reference_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comparison_market_prices = (
            market_overview_services.get_all_asset_prices_for_date(previous_date)
        )
        if not comparison_market_prices:
            return Response(
                {"error": f"No data found for reference date: {previous_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_diffs = market_overview_services.get_price_change(
            reference_market_prices, comparison_market_prices
        )
        return Response(data=price_diffs, status=status.HTTP_200_OK)


class GetAssetNamesView(BaseAPIView):
    """Get Asset Names APIView."""

    @open_api(GET_ASSET_NAMES_SCHEMA)
    def get(self, request: Request) -> Response:
        """List all asset names in the database."""
        filters = {key: value for key, value in request.query_params.items()}
        accepted_params = ["asset_class", "asset_type", "location", "source"]
        unaccepted_params = [
            param for param in filters.keys() if param not in accepted_params
        ]
        if unaccepted_params:
            return Response(
                {
                    "error": f"Parameters: {unaccepted_params} are not accepted. Please only use: {accepted_params}]."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        unique_short_name = market_overview_services.get_asset_names(filters)
        return Response(data=unique_short_name, status=status.HTTP_200_OK)


class GetHistoricalPricesView(BaseAPIView):
    """Get Historical Prices APIView."""

    @open_api(GET_HISTORICAL_PRICES_SCHEMA)
    def get(self, request: Request) -> Response:
        """Get historical prices of an asset."""
        short_name: Optional[str] = request.query_params.get("short_name")
        start_date: Optional[date] = request.query_params.get("start_date")
        end_date: Optional[date] = request.query_params.get("end_date")
        if not short_name:
            return Response(
                {"error": "short_name parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if start_date and end_date and start_date > end_date:
            return Response(
                {"error": "end_date must be greater than start_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        historical_prices = market_overview_services.get_historical_prices(
            short_name, start_date, end_date
        )
        return Response(data=historical_prices, status=status.HTTP_200_OK)


class GetYieldCurveView(BaseAPIView):
    """Get Yield Curve APIView."""

    @open_api(GET_YIELD_CURVE_SCHEMA)
    def get(self, request: Request) -> Response:
        """Get yield curve for a specific date and location."""
        target_date: Optional[date] = request.query_params.get("date")
        location: Optional[str] = request.query_params.get("location")
        asset_type: Optional[str] = request.query_params.get("asset_type")
        if not target_date:
            return Response(
                {"error": "date parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not location:
            return Response(
                {"error": "location parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if asset_type and asset_type not in AssetTypeChoices:
            autorized_values = ", ".join([choice.value for choice in AssetTypeChoices])
            return Response(
                {
                    "error": f"asset_type must be one of the following: {autorized_values}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        yield_curve = market_overview_services.get_yield_curve(target_date, location)
        return Response(data=yield_curve, status=status.HTTP_200_OK)


class DatabaseInteractionView(BaseAPIView):
    """Database Interaction APIView."""

    @open_api(GET_MARKET_PRICE_DATA_SCHEMA)
    def get(self, request: Request) -> Response:
        """List all market prices for a specific date."""
        action: GetActionEnum = request.query_params.get("action")
        action_values = [e.value for e in GetActionEnum]
        if not action or action not in action_values:
            return Response(
                {
                    "error": f"action parameter is required, and must be one of the following: {action_values}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == GetActionEnum.GET:
            price_date: date = request.query_params.get("date")
            short_name: str = request.query_params.get("short_name")
            if not price_date:
                return Response(
                    {"error": "date parameter is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not short_name:
                return Response(
                    {"error": "short_name parameter is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            asset = shared_services.get(
                MarketPriceModel, date=price_date, short_name=short_name
            )
            return Response(data=asset.convert_to_dict(), status=status.HTTP_200_OK)

        elif action == GetActionEnum.LIST:
            price_date: date = request.query_params.get("date")
            if not price_date:
                return Response(
                    {"error": "date parameter is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            market_data = market_overview_services.get_all_asset_prices_for_date(
                price_date
            )
            return Response(data=market_data, status=status.HTTP_200_OK)

    @open_api(UPDATE_MARKET_PRICE_DATA_SCHEMA)
    def patch(self, request: Request) -> Response:
        """Update market price data for a specific asset and date."""
        serializer = DataCorrectionSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_date: date = serializer.validated_data.get("date")
        short_name: str = serializer.validated_data.get("short_name")

        if not market_overview_services.check_asset_existence(short_name):
            return Response(
                {"error": f"asset: {short_name} does not exist in database."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset = shared_services.get(
            MarketPriceModel, date=price_date, short_name=short_name
        )
        updated_asset = shared_services.update_with_logs(
            asset, PriceUpdateLogModel, serializer.validated_data
        )
        return Response(data=updated_asset.convert_to_dict(), status=status.HTTP_200_OK)


class GetPriceUpdateLogsView(BaseAPIView):
    """Get Price Update Logs APIView."""

    @open_api(GET_PRICE_UPDATE_LOGS_SCHEMA)
    def get(self, request: Request) -> Response:
        """Get price update logs with optional filtering."""
        price_date: date = request.query_params.get("date")
        short_name: str = request.query_params.get("short_name")

        logs = market_overview_services.get_price_update_logs(
            price_date=price_date, short_name=short_name
        )

        return Response(data=logs, status=status.HTTP_200_OK)


class GetAssetsWithoutPricesView(BaseAPIView):
    """Get Assets Without Prices APIView."""

    @open_api(GET_ASSETS_WITHOUT_PRICES_SCHEMA)
    def get(self, request: Request) -> Response:
        """Get assets without prices."""
        price_date: date = request.query_params.get("date")
        assets = market_overview_services.get_assets_without_prices(price_date)
        return Response(data=assets, status=status.HTTP_200_OK)


class BulkUpdateAssetsPricesView(BaseAPIView):
    """Bulk Update Assets Prices APIView."""

    @open_api(BULK_UPDATE_ASSETS_PRICES_SCHEMA)
    def post(self, request: Request) -> Response:
        """Bulk update assets prices."""
        serializer = BulkUpdateAssetsPricesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        updates = serializer.validated_data
        assets = market_overview_services.bulk_update_assets_prices(updates)
        return Response(data=assets, status=status.HTTP_200_OK)
