from datetime import date
from enum import Enum
from typing import Optional

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from pandas.tseries.offsets import BDay
import scrap_data.services as scrap_data_services
import shared.services as shared_services
from scrap_data.models import AssetTypeChoices, MarketPriceModel, PriceUpdateLogModel
from scrap_data.serializers import (
    CalculatePriceDiffSerializer,
    DataCorrectionSerializer,
    MarketPriceIngestionSerializer,
    TargetedMarketPriceIngestionSerializer,
)


class GetActionEnum(str, Enum):
    """Get Action Enum"""

    GET = "GET"
    LIST = "LIST"


class ScrapDataView(APIView):
    """Scrap Data APIView."""

    def post(self, request: Request) -> Response:
        """Ingest market prices gathered from various sources."""
        serializer = MarketPriceIngestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_date: date = serializer.validated_data.get("date")
        market_data = scrap_data_services.get_market_data(target_date)
        for data in market_data:
            shared_services.upsert_with_logs(
                model=MarketPriceModel,
                log_model=PriceUpdateLogModel,
                lookup_kwargs={"date": data["date"], "short_name": data["short_name"]},
                updates={
                    "logs": f"Automated price update on {data['short_name']} to price: {data['price']}.",
                    "asset_class": data["asset_class"],
                    "asset_type": data["asset_type"],
                    "location": data["location"],
                    "full_name": data["full_name"],
                    "maturity": data["maturity"],
                    "source": data["source"],
                    "price": data["price"],
                },
            )

        return Response(status=status.HTTP_201_CREATED)


class ScrapAssetDataView(APIView):
    """Scrap Specific Asset Data APIView."""

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
        if not scrap_data_services.check_asset_existence(short_name):
            return Response(
                {"error": f"asset: {short_name} does not exist in database."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        market_data = scrap_data_services.get_specific_asset_market_data(
            short_name, start_date, end_date
        )

        for data in market_data:
            shared_services.upsert_with_logs(
                model=MarketPriceModel,
                log_model=PriceUpdateLogModel,
                lookup_kwargs={"date": data["date"], "short_name": data["short_name"]},
                updates={
                    "logs": f"Automated price update on {data['short_name']} to price: {data['price']}.",
                    "asset_class": data["asset_class"],
                    "asset_type": data["asset_type"],
                    "location": data["location"],
                    "full_name": data["full_name"],
                    "maturity": data["maturity"],
                    "source": data["source"],
                    "price": data["price"],
                },
            )

        return Response(status=status.HTTP_201_CREATED)


class CalculatePriceChangeView(APIView):
    """Calculate Price Change APIView."""

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

        reference_market_prices = scrap_data_services.get_all_asset_prices_for_date(
            reference_date
        )
        if not reference_market_prices:
            return Response(
                {"error": f"No data found for reference date: {reference_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comparison_market_prices = scrap_data_services.get_all_asset_prices_for_date(
            previous_date
        )
        if not comparison_market_prices:
            return Response(
                {"error": f"No data found for reference date: {previous_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_diffs = scrap_data_services.get_price_change(
            reference_market_prices, comparison_market_prices
        )
        return Response(data=price_diffs, status=status.HTTP_200_OK)


class GetAssetNamesView(APIView):
    """Get Asset Names APIView."""

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
        unique_short_name = scrap_data_services.get_asset_names(filters)
        return Response(data=unique_short_name, status=status.HTTP_200_OK)


class GetHistoricalPricesView(APIView):
    """Get Historical Prices APIView."""

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
        historical_prices = scrap_data_services.get_historical_prices(
            short_name, start_date, end_date
        )
        return Response(data=historical_prices, status=status.HTTP_200_OK)


class GetYieldCurveView(APIView):
    """Get Yield Curve APIView."""

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

        yield_curve = scrap_data_services.get_yield_curve(target_date, location)
        return Response(data=yield_curve, status=status.HTTP_200_OK)


class DatabaseInteractionView(APIView):
    """Database Interaction APIView."""

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
            market_data = scrap_data_services.get_all_asset_prices_for_date(price_date)
            return Response(data=market_data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        """Get yield curve for a specific date and location."""
        serializer = DataCorrectionSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                data={"error_message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_date: date = serializer.validated_data.get("date")
        short_name: str = serializer.validated_data.get("short_name")

        if not scrap_data_services.check_asset_existence(short_name):
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
