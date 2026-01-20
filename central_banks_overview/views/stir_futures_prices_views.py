from datetime import date
from typing import List, Optional

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.stir_prices_ingestion_services as stir_futures_services
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    BulkUpdateStirFuturesPricesSerializer,
    CsvBulkUpdateStirFuturesPricesSerializer,
    DeleteStirFuturesPricesSerializer,
    EstrPriceIngestionViaPdfSerializer,
    ListStirFuturesPricesSerializer,
    StirFuturesPriceIngestionSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    DeleteStirFuturesPricesResponseSerializer,
    StirFuturesPriceIngestionResponseSerializer,
    StirFuturesPriceResponseSerializer,
)
from central_banks_overview.services.stir_prices_ingestion_services import (
    BulkUpdateFuturesPricesItem,
)
from core.open_api import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services import logger
from core.views import BaseAPIView


class StirFuturesPriceIngestionView(BaseAPIView):
    """Stir Futures Price Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Stir Futures Prices",
        description="Ingest Stir Futures Prices for a given date and maturity month.",
        request_serializer=StirFuturesPriceIngestionSerializer,
        response=CreatedOpenApiResponse(StirFuturesPriceIngestionResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest market prices gathered from various sources."""
        price_date: date = validated_data["date"]

        logger.info(f"Ingesting STIR Futures prices for date: {price_date}")
        stir_futures_prices = stir_futures_services.extract_all_stir_futures_prices(
            price_date
        )
        stir_futures_updated = stir_futures_services.ingest_stir_futures_prices(
            stir_futures_prices
        )
        return Response(
            data=StirFuturesPriceIngestionResponseSerializer(
                {
                    "message": "STIR Futures prices successfully ingested",
                    "stir_futures_updated": [
                        f"{stir_future_price['short_name']}.{stir_future_price['maturity']}"
                        for stir_future_price in stir_futures_updated
                    ],
                    "date": price_date,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class EstrPriceIngestionViaPdfView(BaseAPIView):
    """ESTR Price Ingestion via PDF APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest ESTR Prices via PDF",
        description="Ingest ESTR Prices via PDF for a given date.",
        request_serializer=EstrPriceIngestionViaPdfSerializer,
        response=CreatedOpenApiResponse(StirFuturesPriceIngestionResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest PDF Prices for a given date."""
        pdf_file = validated_data["pdf_file"]
        price_date: date = validated_data["date"]

        estr_prices = stir_futures_services.extract_estr_prices_from_pdf(
            pdf_file.read(), price_date
        )
        stir_futures_updated = stir_futures_services.ingest_stir_futures_prices(
            estr_prices
        )
        return Response(
            data=StirFuturesPriceIngestionResponseSerializer(
                {
                    "message": "STIR Futures prices successfully ingested",
                    "stir_futures_updated": [
                        f"{stir_future_price['short_name']}.{stir_future_price['maturity']}"
                        for stir_future_price in stir_futures_updated
                    ],
                    "date": price_date,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ListStirFuturesPricesView(BaseAPIView):
    """List Stir Futures Prices APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="List Stir Futures Prices",
        description="List Stir Futures Prices for a given date.",
        request_serializer=ListStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List Stir Futures Prices for a given date."""
        price_date: date = validated_data["date"]
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        prices = stir_futures_services.get_futures_prices(price_date, central_banks)
        return Response(
            data=StirFuturesPriceResponseSerializer(prices, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Delete STIR Futures Prices",
        description="Delete STIR futures prices based on optional filters.",
        request_serializer=DeleteStirFuturesPricesSerializer,
        response=OkOpenApiResponse(DeleteStirFuturesPricesResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "At least one of 'start_date', 'end_date', or 'central_banks' must be provided."
            )
        ],
    )
    def delete(self, validated_data: dict) -> Response:
        """Delete STIR futures prices based on optional filters."""
        start_date: Optional[date] = validated_data.get("start_date")
        end_date: Optional[date] = validated_data.get("end_date")
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else None
        )

        deleted_count = stir_futures_services.delete_stir_futures_prices(
            start_date, end_date, central_banks
        )
        return Response(
            data=DeleteStirFuturesPricesResponseSerializer(
                {
                    "message": "STIR futures prices successfully deleted.",
                    "deleted_count": deleted_count,
                }
            ).data,
            status=status.HTTP_200_OK,
        )


class BulkUpdateStirFuturesPricesView(BaseAPIView):
    """Bulk Update Stir Futures Prices APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Bulk Update Stir Futures Prices",
        description="Bulk update stir futures prices.",
        request_serializer=BulkUpdateStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
    )
    def patch(self, validated_data: List[BulkUpdateFuturesPricesItem]) -> Response:
        """Bulk update stir futures prices."""
        updates: List[BulkUpdateFuturesPricesItem] = validated_data

        futures_prices = stir_futures_services.bulk_update_futures_prices(updates)
        return Response(
            data=StirFuturesPriceResponseSerializer(futures_prices, many=True).data,
            status=status.HTTP_200_OK,
        )


class CsvBulkUpdateStirFuturesPricesView(BaseAPIView):
    """Bulk Update Stir Futures Prices from CSV APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Bulk Update Stir Futures Prices from CSV",
        description="Bulk update stir futures prices from a CSV file.",
        request_serializer=CsvBulkUpdateStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Bulk update stir futures prices from a CSV file."""
        uploaded_file = validated_data["csv_file"]
        csv_file_bytes = uploaded_file.read()
        futures_prices = stir_futures_services.bulk_update_futures_prices_from_csv(
            csv_file_bytes
        )
        return Response(
            data=StirFuturesPriceResponseSerializer(futures_prices, many=True).data,
            status=status.HTTP_200_OK,
        )
