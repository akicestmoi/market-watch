from datetime import date
from typing import List, Optional

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.cb_data_services as cb_data_services
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
from central_banks_overview.services.cb_data_services import CentralBankDataDate
from core.open_api import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView


class CentralBankDataIngestionView(BaseAPIView):
    """Central Bank Data Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Central Bank Data",
        description="Ingest Central Bank Data for a given date by central bank.",
        request_serializer=CentralBankDataIngestionSerializer,
        response=CreatedOpenApiResponse(CentralBankDataIngestionResponseSerializer),
    )
    def post(self, validated_data: List[CentralBankDataDate]) -> Response:
        """Ingest central bank data."""
        dates_to_ingest_by_central_bank: List[CentralBankDataDate] = validated_data
        central_bank_data_updated = cb_data_services.ingest_requested_central_bank_data(
            dates_to_ingest_by_central_bank
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


class ListCentralBankDataView(BaseAPIView):
    """List Central Bank Data APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="List Central Bank Data",
        description="List Central Bank Data for a specific date and central bank.",
        request_serializer=ListCentralBankDataSerializer,
        response=OkOpenApiResponse(CentralBankDataResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List Central Bank Data for a specific date and central bank."""
        target_date: Optional[date] = validated_data.get("date")
        last_value: bool = validated_data.get("last_value", False)
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        central_bank_data = cb_data_services.get_central_bank_data(
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
    def delete(self, validated_data: dict) -> Response:
        """Delete Central Bank Data by IDs."""
        ids: List[int] = validated_data.get("ids", [])

        deleted_count = cb_data_services.delete_central_bank_data(ids)
        return Response(
            data=DeleteCentralBankDataResponseSerializer(
                {
                    "message": "Central Bank Data successfully deleted",
                    "deleted_count": deleted_count,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
