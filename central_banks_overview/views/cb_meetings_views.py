from typing import Optional

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.cb_meetings_services as cb_meetings_services
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    GetCentralBankMeetingDatesSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    CentralBankMeetingDatesResponseSerializer,
)
from core.open_api import ApiTags, CreatedOpenApiResponse, OkOpenApiResponse, open_api
from core.views import BaseAPIView


class CentralBankMeetingDatesIngestionView(BaseAPIView):
    """Central Bank Meeting Dates Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Central Bank Meeting Dates",
        description="Ingest Central Bank Meeting Dates for a given date.",
        response=CreatedOpenApiResponse(),
    )
    def post(self, validated_data: dict) -> Response:
        """Get Central Bank Meeting Dates for a given date."""
        cb_meetings_services.ingest_all_central_bank_meeting_dates()
        return Response(
            data={"message": "Central Bank Meeting Dates successfully ingested"},
            status=status.HTTP_201_CREATED,
        )


class GetCentralBankMeetingDatesView(BaseAPIView):
    """Get Central Bank Meeting Dates APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Get Central Bank Meeting Dates",
        description="Get Central Bank Meeting Dates.",
        request_serializer=GetCentralBankMeetingDatesSerializer,
        response=OkOpenApiResponse(CentralBankMeetingDatesResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get Central Bank Meeting Dates."""
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        meeting_dates = cb_meetings_services.get_central_bank_meeting_dates(
            central_banks
        )
        return Response(
            data=CentralBankMeetingDatesResponseSerializer(
                meeting_dates, many=True
            ).data,
            status=status.HTTP_200_OK,
        )
