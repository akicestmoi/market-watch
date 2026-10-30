"""API views for central bank data ingestion and retrieval."""

from datetime import date
from typing import TypedDict

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.central_banks_data as central_banks_data
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    CentralBankDataIngestionSerializer,
    DeleteCentralBankDataSerializer,
    ListCentralBankDataSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    CentralBankDataIngestionResponseSerializer,
    CentralBankDataResponseSerializer,
    DeleteCentralBankDataResponseSerializer,
)
from central_banks_overview.services.central_banks_data import CentralBankDataDate
from core.locks import acquire_redis_locks
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView


class _CentralBankDataIngestionItemValidatedData(TypedDict):
    """One item from ``CentralBankDataIngestionSerializer`` (ChoiceField → str)."""

    central_bank: str
    date: date


class CentralBankDataIngestionView(BaseAPIView):
    """Central Bank Data Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Central Bank Data",
        description="Ingest Central Bank Data for a given date by central bank.",
        request_serializer=CentralBankDataIngestionSerializer,
        response=CreatedOpenApiResponse(CentralBankDataIngestionResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("central_bank is required | date is required"),
            ConflictOpenApiResponse(
                "Central bank data ingestion is already in progress."
            ),
        ],
    )
    def post(
        self, validated_data: list[_CentralBankDataIngestionItemValidatedData]
    ) -> Response:
        """Ingest central bank data."""
        dates_to_ingest_by_central_bank: list[CentralBankDataDate] = [
            CentralBankDataDate(
                central_bank=CentralBankChoices(item["central_bank"]),
                date=item["date"],
            )
            for item in validated_data
        ]
        lock_keys = [
            central_banks_data.get_cb_data_ingestion_lock_key(
                item["central_bank"], item["date"]
            )
            for item in dates_to_ingest_by_central_bank
        ]
        with acquire_redis_locks(
            lock_keys,
            locked_detail="Central bank data ingestion is already in progress.",
        ):
            central_bank_data_updated = (
                central_banks_data.ingest_requested_central_bank_data(
                    dates_to_ingest_by_central_bank
                )
            )
        return Response(
            data=CentralBankDataIngestionResponseSerializer(
                {
                    "message": "Central Bank Data successfully ingested",
                    "updates": central_bank_data_updated,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class _ListCentralBankDataValidatedData(TypedDict, total=False):
    """Validated data for ``ListCentralBankDataSerializer``."""

    central_banks: list[CentralBankChoices] | None
    date: date | None
    last_value: bool


class _DeleteCentralBankDataValidatedData(TypedDict, total=False):
    """Validated data for ``DeleteCentralBankDataSerializer``."""

    central_banks: list[CentralBankChoices] | None
    ids: list[int] | None


class ListCentralBankDataView(BaseAPIView):
    """List Central Bank Data APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="List Central Bank Data",
        description="List Central Bank Data for a specific date and central bank.",
        request_serializer=ListCentralBankDataSerializer,
        response=OkOpenApiResponse(CentralBankDataResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid central_banks, date, or last_value.")
        ],
    )
    def get(self, validated_data: _ListCentralBankDataValidatedData) -> Response:
        """List Central Bank Data for a specific date and central bank."""
        target_date: date | None = validated_data.get("date")
        last_value: bool = validated_data.get("last_value", False)
        central_banks = validated_data.get("central_banks") or []

        central_bank_data = central_banks_data.get_central_bank_data(
            target_date, central_banks, last_value
        )
        return Response(
            data=CentralBankDataResponseSerializer(central_bank_data, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Delete Central Bank Data",
        description="Delete Central Bank Data by IDs.",
        request_serializer=DeleteCentralBankDataSerializer,
        response=OkOpenApiResponse(DeleteCentralBankDataResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("IDs must be comma-separated integers.")
        ],
    )
    def delete(self, validated_data: _DeleteCentralBankDataValidatedData) -> Response:
        """Delete Central Bank Data by IDs."""
        ids: list[int] = validated_data.get("ids") or []

        deleted_count = central_banks_data.delete_central_bank_data(ids)
        return Response(
            data=DeleteCentralBankDataResponseSerializer(
                {
                    "message": "Central Bank Data successfully deleted",
                    "deleted_count": deleted_count,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
