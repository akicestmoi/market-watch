import json
from datetime import date
from typing import List, Optional

from rest_framework import status
from rest_framework.response import Response

import core.services as core_services
import market_overview.services.market_data_services as market_data_services
import market_overview.services.price_ingestion_services as price_ingestion_services
from core.open_api import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services import logger
from core.views import BaseAPIView
from market_overview.models import AssetModel, LocationChoices, MarketPriceModel
from market_overview.open_api.request_serializers import (
    BaseAssetSerializer,
    BulkUpdateAssetsPricesSerializer,
    CalculatePriceDiffSerializer,
    GetAssetNamesSerializer,
    GetAssetsWithoutPricesSerializer,
    GetHistoricalPricesSerializer,
    GetMarketPriceSerializer,
    GetPriceUpdateLogsSerializer,
    GetYieldCurveSerializer,
    ListMarketPricesSerializer,
    MarketPriceIngestionSerializer,
    SpecificAssetMarketPriceIngestionSerializer,
)
from market_overview.open_api.response_serializers import (
    AssetResponseSerializer,
    CalculatePriceChangeResponseSerializer,
    GetAssetNamesResponseSerializer,
    GetAssetWithoutPriceResponseSerializer,
    GetHistoricalPriceResponseSerializer,
    GetYieldCurveResponseSerializer,
    MarketPriceIngestionResponseSerializer,
    MarketPriceResponseSerializer,
    PriceUpdateLogResponseSerializer,
    SpecificAssetMarketPriceIngestionResponseSerializer,
)
from market_overview.services.market_data_services import BulkUpdateAssetsPricesItem


class GenerateBaseAssetsDataView(BaseAPIView):
    """Generate Base Assets Data APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Generate Base Assets Data",
        description="Generate base assets data from JSON file.",
    )
    def post(self, validated_data: dict) -> Response:
        """Generate asset data from market_data.json."""
        with open("market_overview/data_sources/market_data.json") as f:
            assets_base_info = json.load(f)
        for asset in assets_base_info:
            AssetModel.objects.update_or_create(id=asset["id"], defaults=asset)
        return Response(
            data={"message": "Asset data successfully generated."},
            status=status.HTTP_200_OK,
        )


class GetAssetNamesView(BaseAPIView):
    """Get Asset Names APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Get Asset Names",
        description="Get all asset names in the database.",
        request_serializer=GetAssetNamesSerializer,
        response=OkOpenApiResponse(GetAssetNamesResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List all asset names in the database."""
        asset_names = market_data_services.get_asset_names(validated_data)
        return Response(
            data=GetAssetNamesResponseSerializer(asset_names).data,
            status=status.HTTP_200_OK,
        )


class AssetDetailsView(BaseAPIView):
    """Asset Details APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Get Asset",
        description="Get an asset.",
        request_serializer=BaseAssetSerializer,
        response=OkOpenApiResponse(AssetResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get an asset."""
        asset_id: int = validated_data["id"]
        asset = core_services.get(AssetModel, id=asset_id)
        return Response(
            data=AssetResponseSerializer(asset).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Delete Asset",
        description="Delete an asset.",
        request_serializer=BaseAssetSerializer,
    )
    def delete(self, validated_data: dict) -> Response:
        """Delete an asset."""
        asset_id: int = validated_data["id"]
        asset = core_services.get(AssetModel, id=asset_id)
        asset.delete()
        return Response(
            data={"message": "Asset deleted successfully."},
            status=status.HTTP_200_OK,
        )


class IngestMarketPricesView(BaseAPIView):
    """Ingest Market Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Ingest Market Prices",
        description="Ingest market prices gathered from various sources for a specific date. This endpoint scrapes data from multiple sources and stores it in the database.",
        request_serializer=MarketPriceIngestionSerializer,
        response=CreatedOpenApiResponse(MarketPriceIngestionResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("Date is required")],
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest market prices gathered from various sources."""
        price_date: date = validated_data["date"]

        logger.info(f"Ingesting market data for date: {price_date}")
        market_data = price_ingestion_services.get_market_data(price_date)
        asset_not_updated = price_ingestion_services.ingest_market_data(market_data)
        return Response(
            data=MarketPriceIngestionResponseSerializer(
                {
                    "message": "Market prices successfully ingested",
                    "asset_not_updated": [
                        data["asset"].short_name for data in asset_not_updated
                    ],
                    "date": price_date,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class IngestSpecificAssetMarketPricesView(BaseAPIView):
    """Ingest Specific Asset Market Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Ingest Specific Asset Market Prices",
        description="Ingest market prices for a specific asset over a target period. This endpoint scrapes historical data for a single asset.",
        request_serializer=SpecificAssetMarketPriceIngestionSerializer,
        response=CreatedOpenApiResponse(
            SpecificAssetMarketPriceIngestionResponseSerializer
        ),
        error_responses=[NotFoundOpenApiResponse("Asset not found")],
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest market prices for a specific asset over a target period."""
        short_name: str = validated_data["short_name"]
        start_date: date = validated_data["start_date"]
        end_date: date = validated_data["end_date"]

        if not market_data_services.check_asset_existence(short_name):
            return Response(
                {"error": f"asset: {short_name} does not exist in database."},
                status=status.HTTP_404_NOT_FOUND,
            )

        market_data = price_ingestion_services.get_specific_asset_market_data(
            short_name, start_date, end_date
        )
        asset_not_updated = price_ingestion_services.ingest_market_data(market_data)
        return Response(
            SpecificAssetMarketPriceIngestionResponseSerializer(
                {
                    "message": "Asset prices successfully ingested",
                    "asset_not_updated": [data["date"] for data in asset_not_updated],
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CalculatePriceChangeView(BaseAPIView):
    """Calculate Price Change APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Calculate Price Change",
        description="Calculate price change for all assets between two dates.",
        request_serializer=CalculatePriceDiffSerializer,
        response=OkOpenApiResponse(CalculatePriceChangeResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("No data found for requested date"),
        ],
    )
    def post(self, validated_data: dict) -> Response:
        """Calculate price change for all assets between two dates."""
        reference_date: date = validated_data["reference_date"]
        previous_date: date = validated_data["previous_date"]

        reference_market_prices = market_data_services.get_all_asset_prices_for_date(
            reference_date
        )
        if not reference_market_prices:
            return Response(
                {"error": f"No data found for reference date: {reference_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comparison_market_prices = market_data_services.get_all_asset_prices_for_date(
            previous_date
        )
        if not comparison_market_prices:
            return Response(
                {"error": f"No data found for previous date: {previous_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_diffs = market_data_services.calculate_price_change(
            reference_market_prices, comparison_market_prices
        )
        return Response(
            data=CalculatePriceChangeResponseSerializer(price_diffs, many=True).data,
            status=status.HTTP_200_OK,
        )


class GetMarketPriceView(BaseAPIView):
    """Get Market Price APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Get Market Price",
        description="Get market price for a specific asset and date.",
        request_serializer=GetMarketPriceSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get or list all market prices."""
        price_date: date = validated_data["date"]
        short_name: str = validated_data["short_name"]

        asset = core_services.get(
            MarketPriceModel, date=price_date, asset__short_name=short_name
        )
        return Response(
            data=MarketPriceResponseSerializer(asset).data, status=status.HTTP_200_OK
        )


class ListMarketPricesView(BaseAPIView):
    """List Market Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="List Market Prices",
        description="List all market prices for a specific date.",
        request_serializer=ListMarketPricesSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List all market prices for a specific date."""
        price_date: date = validated_data["date"]

        market_data = market_data_services.get_all_asset_prices_for_date(price_date)
        return Response(
            data=MarketPriceResponseSerializer(market_data, many=True).data,
            status=status.HTTP_200_OK,
        )


class GetHistoricalPricesView(BaseAPIView):
    """Get Historical Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Get Historical Prices",
        description="Get historical prices of an asset.",
        request_serializer=GetHistoricalPricesSerializer,
        response=OkOpenApiResponse(GetHistoricalPriceResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get historical prices of an asset."""
        short_name: str = validated_data["short_name"]
        start_date: Optional[date] = validated_data.get("start_date")
        end_date: Optional[date] = validated_data.get("end_date")

        historical_prices = market_data_services.get_historical_prices(
            short_name, start_date, end_date
        )
        return Response(
            data=GetHistoricalPriceResponseSerializer(
                historical_prices, many=True
            ).data,
            status=status.HTTP_200_OK,
        )


class GetYieldCurveView(BaseAPIView):
    """Get Yield Curve APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Get Yield Curve",
        description="Get yield curve for a specific date and location.",
        request_serializer=GetYieldCurveSerializer,
        response=OkOpenApiResponse(GetYieldCurveResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get yield curve for a specific date and location."""
        target_date: date = validated_data["date"]
        location: LocationChoices = validated_data["location"]

        yield_curve = market_data_services.get_yield_curve(target_date, location)
        return Response(
            data=GetYieldCurveResponseSerializer(yield_curve, many=True).data,
            status=status.HTTP_200_OK,
        )


class GetAssetsWithoutPricesView(BaseAPIView):
    """Get Assets Without Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Get Assets Without Prices",
        description="Get assets without prices.",
        request_serializer=GetAssetsWithoutPricesSerializer,
        response=OkOpenApiResponse(GetAssetWithoutPriceResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get assets without prices."""
        price_date: Optional[date] = validated_data.get("price_date")
        assets_queryset = market_data_services.get_assets_without_prices(price_date)
        return Response(
            data=GetAssetWithoutPriceResponseSerializer(
                assets_queryset, many=True
            ).data,
            status=status.HTTP_200_OK,
        )


class BulkUpdateAssetsPricesView(BaseAPIView):
    """Bulk Update Assets Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Bulk Update Assets Prices",
        description="Bulk update assets prices.",
        request_serializer=BulkUpdateAssetsPricesSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
    )
    def patch(self, validated_data: List[BulkUpdateAssetsPricesItem]) -> Response:
        """Bulk update assets prices."""
        updates: List[BulkUpdateAssetsPricesItem] = validated_data

        assets = market_data_services.bulk_update_assets_prices(updates)
        return Response(
            data=MarketPriceResponseSerializer(assets, many=True).data,
            status=status.HTTP_200_OK,
        )


class GetPriceUpdateLogsView(BaseAPIView):
    """Get Price Update Logs APIView."""

    @open_api(
        tags=[ApiTags.PRICE_LOGS],
        summary="Get Price Update Logs",
        description="Get price update logs with optional filtering.",
        request_serializer=GetPriceUpdateLogsSerializer,
        response=OkOpenApiResponse(PriceUpdateLogResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get price update logs with optional filtering."""
        price_date: date = validated_data["price_date"]
        short_name: str = validated_data["short_name"]
        price_update_logs = market_data_services.get_price_update_logs(
            price_date=price_date, short_name=short_name
        )
        return Response(
            data=PriceUpdateLogResponseSerializer(price_update_logs, many=True).data,
            status=status.HTTP_200_OK,
        )
