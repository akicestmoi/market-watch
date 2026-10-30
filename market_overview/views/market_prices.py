"""API views for market price ingestion and queries."""

from datetime import date
from typing import TypedDict

from django.core.files.uploadedfile import UploadedFile
from rest_framework import status
from rest_framework.response import Response

import market_overview.services.market_data as market_data
import market_overview.services.price_ingestion as price_ingestion
from core.locks import acquire_redis_lock
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    NotFoundOpenApiResponse,
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
    MarkAsHolidaySerializer,
    MarketPriceIngestionSerializer,
)
from market_overview.open_api.response_serializers import (
    BatchPriceIngestionResponseSerializer,
    DeleteMarketPricesResponseSerializer,
    GetAssetWithoutPriceResponseSerializer,
    MarkAsHolidayResponseSerializer,
    MarketPriceIngestionResponseSerializer,
    MarketPriceResponseSerializer,
)
from market_overview.services.market_data import (
    BulkUpdateAssetsPricesItem,
    MarkAsHolidayItem,
)
from market_overview.services.price_ingestion import BatchPriceIngestionItem


class MarketPriceIngestionValidatedData(TypedDict):
    """Validated data for ``MarketPriceIngestionSerializer``."""

    date: date


class IngestMarketPricesView(BaseAPIView):
    """Ingest Market Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Ingest Market Prices",
        description="Ingest market prices gathered from various sources for a specific date. This endpoint scrapes data from multiple sources and stores it in the database.",
        request_serializer=MarketPriceIngestionSerializer,
        response=CreatedOpenApiResponse(MarketPriceIngestionResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Date is required"),
            ConflictOpenApiResponse(
                "Market price ingestion is already in progress for this date."
            ),
        ],
    )
    def post(self, validated_data: MarketPriceIngestionValidatedData) -> Response:
        """Ingest market prices gathered from various sources."""
        price_date: date = validated_data["date"]

        logger.info(f"Ingesting market data for date: {price_date}")
        with acquire_redis_lock(
            price_ingestion.get_market_price_ingestion_lock_key(price_date),
            locked_detail=(
                "Market price ingestion is already in progress for "
                f"{price_date.isoformat()}."
            ),
        ):
            prices_to_ingest = price_ingestion.get_market_data(price_date)
            ingestion_result = price_ingestion.ingest_market_data(prices_to_ingest)
        return Response(
            data=MarketPriceIngestionResponseSerializer(
                {
                    "message": "Market prices successfully ingested",
                    "asset_not_updated": ingestion_result["asset_not_updated"],
                    "asset_not_updated_holiday": ingestion_result[
                        "asset_not_updated_holiday"
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
        error_responses=[BadRequestOpenApiResponse("List cannot be empty.")],
    )
    def post(self, validated_data: list[BatchPriceIngestionItem]) -> Response:
        """Ingest market prices for specific assets over target periods."""
        batch_ingestion_items: list[BatchPriceIngestionItem] = validated_data

        results = price_ingestion.batch_ingest_specific_asset_market_prices(
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


class GetMarketPriceValidatedData(TypedDict):
    """Validated data for ``GetMarketPriceSerializer``."""

    date: date
    short_name: str


class DeleteMarketPricesValidatedData(TypedDict, total=False):
    """Validated data for ``DeleteMarketPricesSerializer``."""

    ids: list[int] | None


class GetMarketPriceView(BaseAPIView):
    """Get Market Price APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Get Market Price",
        description="Get market price for a specific asset and date.",
        request_serializer=GetMarketPriceSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("date is required | short_name is required"),
            NotFoundOpenApiResponse("Market price not found"),
        ],
    )
    def get(self, validated_data: GetMarketPriceValidatedData) -> Response:
        """Get or list all market prices."""
        price_date: date = validated_data["date"]
        short_name: str = validated_data["short_name"]

        asset = MarketPriceModel.objects.get(
            date=price_date, asset__short_name=short_name
        )
        return Response(
            data=MarketPriceResponseSerializer(asset).data, status=status.HTTP_200_OK
        )

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Delete Market Prices",
        description="Delete market prices by IDs.",
        request_serializer=DeleteMarketPricesSerializer,
        response=OkOpenApiResponse(DeleteMarketPricesResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("IDs must be comma-separated integers.")
        ],
    )
    def delete(self, validated_data: DeleteMarketPricesValidatedData) -> Response:
        """Delete market prices by IDs."""
        ids: list[int] = validated_data.get("ids") or []

        deleted_count = market_data.delete_market_prices(ids)
        return Response(
            data=DeleteMarketPricesResponseSerializer(
                {
                    "message": "Market prices successfully deleted.",
                    "deleted_count": deleted_count,
                }
            ).data,
            status=status.HTTP_200_OK,
        )


class ListMarketPricesValidatedData(TypedDict):
    """Validated data for ``ListMarketPricesSerializer``."""

    date: date


class ListMarketPricesView(BaseAPIView):
    """List Market Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="List Market Prices",
        description="List all market prices for a specific date.",
        request_serializer=ListMarketPricesSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("date is required")],
    )
    def get(self, validated_data: ListMarketPricesValidatedData) -> Response:
        """List all market prices for a specific date."""
        price_date: date = validated_data["date"]

        market_price_rows = market_data.get_all_asset_prices_for_date(price_date)
        return Response(
            data=MarketPriceResponseSerializer(market_price_rows, many=True).data,
            status=status.HTTP_200_OK,
        )


class GetAssetsWithoutPricesValidatedData(TypedDict, total=False):
    """Validated data for ``GetAssetsWithoutPricesSerializer``."""

    start_date: date
    end_date: date
    include_holidays: bool


class GetAssetsWithoutPricesView(BaseAPIView):
    """Get Assets Without Prices APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Get Assets Without Prices",
        description="Get assets without prices.",
        request_serializer=GetAssetsWithoutPricesSerializer,
        response=OkOpenApiResponse(GetAssetWithoutPriceResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "end_date must be greater than or equal to start_date."
            )
        ],
    )
    def get(self, validated_data: GetAssetsWithoutPricesValidatedData) -> Response:
        """Get assets without prices."""
        start_date: date | None = validated_data.get("start_date")
        end_date: date | None = validated_data.get("end_date")
        include_holidays: bool = validated_data.get("include_holidays", False)
        assets_queryset = market_data.get_assets_without_prices(
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
        error_responses=[
            BadRequestOpenApiResponse(
                "short_name is required | date is required | price is required"
            ),
            NotFoundOpenApiResponse("Market price not found"),
        ],
    )
    def patch(self, validated_data: list[BulkUpdateAssetsPricesItem]) -> Response:
        """Bulk update assets prices."""
        updates: list[BulkUpdateAssetsPricesItem] = validated_data

        assets = market_data.bulk_update_assets_prices(updates)
        return Response(
            data=MarketPriceResponseSerializer(assets, many=True).data,
            status=status.HTTP_200_OK,
        )


class CsvBulkUpdateAssetsPricesValidatedData(TypedDict):
    """Validated data for ``CsvBulkUpdateAssetsPricesSerializer``."""

    csv_file: UploadedFile


class CsvBulkUpdateAssetsPricesView(BaseAPIView):
    """Bulk Update Assets Prices from CSV APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Bulk Update Assets Prices from CSV",
        description="Bulk update assets prices from a CSV file.",
        request_serializer=CsvBulkUpdateAssetsPricesSerializer,
        response=OkOpenApiResponse(MarketPriceResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid request data. Please check your input."),
            NotFoundOpenApiResponse("Market price not found"),
        ],
    )
    def post(self, validated_data: CsvBulkUpdateAssetsPricesValidatedData) -> Response:
        """Bulk update assets prices from a CSV file."""
        uploaded_file = validated_data["csv_file"]
        csv_file_bytes = uploaded_file.read()
        assets = market_data.bulk_update_assets_prices_from_csv(csv_file_bytes)
        return Response(
            data=MarketPriceResponseSerializer(assets, many=True).data,
            status=status.HTTP_200_OK,
        )


class MarkAsHolidayView(BaseAPIView):
    """Mark Market Prices as Holiday APIView."""

    @open_api(
        tags=[ApiTags.ASSET_PRICES],
        summary="Mark As Holiday",
        description="Mark market prices as holiday for the given assets and dates. "
        "Sets the comment to 'Bank holiday' and price to null.",
        request_serializer=MarkAsHolidaySerializer,
        response=CreatedOpenApiResponse(MarkAsHolidayResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("List cannot be empty.")],
    )
    def post(self, validated_data: list[MarkAsHolidayItem]) -> Response:
        """Mark market prices as holiday."""
        items: list[MarkAsHolidayItem] = validated_data

        result = market_data.mark_prices_as_holiday(items)

        return Response(
            data=MarkAsHolidayResponseSerializer(
                {
                    "message": "Market prices marked as holiday.",
                    "updated_count": result["updated_count"],
                    "not_found": result["not_found"],
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )
