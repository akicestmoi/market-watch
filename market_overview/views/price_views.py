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
    OkOpenApiResponse,
    open_api,
)
from core.services import logger
from core.views import BaseAPIView
from market_overview.models import MarketPriceModel
from market_overview.open_api.request_serializers import (
    BatchPriceIngestionSerializer,
    BulkUpdateAssetsPricesSerializer,
    CsvBulkUpdateAssetsPricesSerializer,
    DeleteMarketPricesSerializer,
    GetAssetsWithoutPricesSerializer,
    GetMarketPriceSerializer,
    ListMarketPricesSerializer,
    MarketPriceIngestionSerializer,
)
from market_overview.open_api.response_serializers import (
    BatchPriceIngestionResponseSerializer,
    DeleteMarketPricesResponseSerializer,
    GetAssetWithoutPriceResponseSerializer,
    MarketPriceIngestionResponseSerializer,
    MarketPriceResponseSerializer,
)
from market_overview.services.market_data_services import BulkUpdateAssetsPricesItem
from market_overview.services.price_ingestion_services import BatchPriceIngestionItem


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


class BatchIngestMarketPricesView(BaseAPIView):
    """Batch Ingest Market Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Batch Ingest Market Prices",
        description="Ingest market prices for specific assets over target periods. This endpoint scrapes historical data for multiple assets.",
        request_serializer=BatchPriceIngestionSerializer,
        response=CreatedOpenApiResponse(BatchPriceIngestionResponseSerializer),
    )
    def post(self, validated_data: List[BatchPriceIngestionItem]) -> Response:
        """Ingest market prices for specific assets over target periods."""
        batch_ingestion_items: List[BatchPriceIngestionItem] = validated_data

        results = price_ingestion_services.batch_ingest_specific_asset_market_prices(
            batch_ingestion_items
        )

        return Response(
            BatchPriceIngestionResponseSerializer(
                {
                    "message": "Asset prices ingestion completed",
                    "results": results,
                }
            ).data,
            status=status.HTTP_201_CREATED,
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

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Delete Market Prices",
        description="Delete market prices based on optional filters. At least one of 'start_date', 'end_date', or 'short_names' must be provided.",
        request_serializer=DeleteMarketPricesSerializer,
        response=OkOpenApiResponse(DeleteMarketPricesResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "At least one of 'start_date', 'end_date', or 'short_names' must be provided."
            )
        ],
    )
    def delete(self, validated_data: dict) -> Response:
        """Delete market prices based on optional filters."""
        start_date: Optional[date] = validated_data.get("start_date")
        end_date: Optional[date] = validated_data.get("end_date")
        short_names: Optional[List[str]] = validated_data.get("short_names")

        deleted_count = market_data_services.delete_market_prices(
            start_date, end_date, short_names
        )
        return Response(
            data=DeleteMarketPricesResponseSerializer(
                {
                    "message": "Market prices successfully deleted.",
                    "deleted_count": deleted_count,
                }
            ).data,
            status=status.HTTP_200_OK,
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
        start_date: Optional[date] = validated_data.get("start_date")
        end_date: Optional[date] = validated_data.get("end_date")
        include_holidays: bool = validated_data.get("include_holidays", False)
        assets_queryset = market_data_services.get_assets_without_prices(
            start_date, end_date, include_holidays
        )
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


class CsvBulkUpdateAssetsPricesView(BaseAPIView):
    """Bulk Update Assets Prices from CSV APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Bulk Update Assets Prices from CSV",
        description="Bulk update assets prices from a CSV file.",
        request_serializer=CsvBulkUpdateAssetsPricesSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Bulk update assets prices from a CSV file."""
        uploaded_file = validated_data["csv_file"]
        csv_file_bytes = uploaded_file.read()
        assets = market_data_services.bulk_update_assets_prices_from_csv(csv_file_bytes)
        return Response(
            data=MarketPriceResponseSerializer(assets, many=True).data,
            status=status.HTTP_200_OK,
        )
