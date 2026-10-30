"""API views for STIR futures prices."""

from datetime import date
from typing import NotRequired, TypedDict

from django.core.files.uploadedfile import UploadedFile
from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.stir_prices_ingestion as stir_prices_ingestion
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
from central_banks_overview.services.scrapers.estr_futures import (
    extract_estr_prices_from_pdf,
)
from central_banks_overview.services.stir_prices_ingestion import (
    BulkUpdateFuturesPricesItem,
)
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


class StirFuturesPriceIngestionValidatedData(TypedDict):
    """Validated data for ``StirFuturesPriceIngestionSerializer``."""

    date: date


class StirFuturesPriceIngestionView(BaseAPIView):
    """Stir Futures Price Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Stir Futures Prices",
        description="Ingest Stir Futures Prices for a given date and maturity month.",
        request_serializer=StirFuturesPriceIngestionSerializer,
        response=CreatedOpenApiResponse(StirFuturesPriceIngestionResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("date is required"),
            ConflictOpenApiResponse(
                "STIR Futures prices ingestion is already in progress for this date."
            ),
        ],
    )
    def post(self, validated_data: StirFuturesPriceIngestionValidatedData) -> Response:
        """Ingest market prices gathered from various sources."""
        price_date: date = validated_data["date"]

        logger.info(f"Ingesting STIR Futures prices for date: {price_date}")
        with acquire_redis_lock(
            stir_prices_ingestion.get_stir_price_ingestion_lock_key(price_date),
            locked_detail=(
                "STIR Futures prices ingestion is already in progress for "
                f"{price_date.isoformat()}."
            ),
        ):
            stir_futures_prices = stir_prices_ingestion.extract_all_stir_futures_prices(
                price_date
            )
            stir_futures_updated = stir_prices_ingestion.ingest_stir_futures_prices(
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


class EstrPriceIngestionViaPdfValidatedData(TypedDict):
    """Validated data for ``EstrPriceIngestionViaPdfSerializer``."""

    pdf_file: UploadedFile
    date: date


class EstrPriceIngestionViaPdfView(BaseAPIView):
    """ESTR Price Ingestion via PDF APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest ESTR Prices via PDF",
        description="Ingest ESTR Prices via PDF for a given date.",
        request_serializer=EstrPriceIngestionViaPdfSerializer,
        response=CreatedOpenApiResponse(StirFuturesPriceIngestionResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("pdf_file is required | date is required"),
            ConflictOpenApiResponse(
                "STIR Futures prices ingestion is already in progress for this date."
            ),
        ],
    )
    def post(self, validated_data: EstrPriceIngestionViaPdfValidatedData) -> Response:
        """Ingest PDF Prices for a given date."""
        pdf_file = validated_data["pdf_file"]
        price_date: date = validated_data["date"]

        with acquire_redis_lock(
            stir_prices_ingestion.get_stir_price_ingestion_lock_key(price_date),
            locked_detail=(
                "STIR Futures prices ingestion is already in progress for "
                f"{price_date.isoformat()}."
            ),
        ):
            estr_prices = extract_estr_prices_from_pdf(pdf_file.read(), price_date)
            stir_futures_updated = stir_prices_ingestion.ingest_stir_futures_prices(
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


class ListStirFuturesPricesValidatedData(TypedDict):
    """Validated data for ``ListStirFuturesPricesSerializer``."""

    date: date
    central_banks: NotRequired[list[CentralBankChoices] | None]


class DeleteStirFuturesPricesValidatedData(TypedDict, total=False):
    """Validated data for ``DeleteStirFuturesPricesSerializer``."""

    central_banks: list[CentralBankChoices] | None
    ids: list[int] | None


class ListStirFuturesPricesView(BaseAPIView):
    """List Stir Futures Prices APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="List Stir Futures Prices",
        description="List Stir Futures Prices for a given date.",
        request_serializer=ListStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("date is required")],
    )
    def get(self, validated_data: ListStirFuturesPricesValidatedData) -> Response:
        """List Stir Futures Prices for a given date."""
        price_date: date = validated_data["date"]
        central_banks = validated_data.get("central_banks") or []

        prices = stir_prices_ingestion.get_futures_prices(price_date, central_banks)
        return Response(
            data=StirFuturesPriceResponseSerializer(prices, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Delete STIR Futures Prices",
        description="Delete STIR futures prices by IDs.",
        request_serializer=DeleteStirFuturesPricesSerializer,
        response=OkOpenApiResponse(DeleteStirFuturesPricesResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("IDs must be comma-separated integers.")
        ],
    )
    def delete(self, validated_data: DeleteStirFuturesPricesValidatedData) -> Response:
        """Delete STIR futures prices by IDs."""
        ids: list[int] = validated_data.get("ids") or []

        deleted_count = stir_prices_ingestion.delete_stir_futures_prices(ids)
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
        error_responses=[
            BadRequestOpenApiResponse(
                "date is required | short_name is required | maturity is required | "
                "price is required"
            ),
            NotFoundOpenApiResponse("STIR futures price not found"),
        ],
    )
    def patch(self, validated_data: list[BulkUpdateFuturesPricesItem]) -> Response:
        """Bulk update stir futures prices."""
        updates: list[BulkUpdateFuturesPricesItem] = validated_data

        futures_prices = stir_prices_ingestion.bulk_update_futures_prices(updates)
        return Response(
            data=StirFuturesPriceResponseSerializer(futures_prices, many=True).data,
            status=status.HTTP_200_OK,
        )


class CsvBulkUpdateStirFuturesPricesValidatedData(TypedDict):
    """Validated data for ``CsvBulkUpdateStirFuturesPricesSerializer``."""

    csv_file: UploadedFile


class CsvBulkUpdateStirFuturesPricesView(BaseAPIView):
    """Bulk Update Stir Futures Prices from CSV APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Bulk Update Stir Futures Prices from CSV",
        description="Bulk update stir futures prices from a CSV file.",
        request_serializer=CsvBulkUpdateStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid request data. Please check your input."),
            NotFoundOpenApiResponse("STIR futures price not found"),
        ],
    )
    def post(
        self, validated_data: CsvBulkUpdateStirFuturesPricesValidatedData
    ) -> Response:
        """Bulk update stir futures prices from a CSV file."""
        uploaded_file = validated_data["csv_file"]
        csv_file_bytes = uploaded_file.read()
        futures_prices = stir_prices_ingestion.bulk_update_futures_prices_from_csv(
            csv_file_bytes
        )
        return Response(
            data=StirFuturesPriceResponseSerializer(futures_prices, many=True).data,
            status=status.HTTP_200_OK,
        )
