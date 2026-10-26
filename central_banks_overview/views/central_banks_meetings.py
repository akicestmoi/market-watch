"""API views for central bank meetings."""

from typing import TypedDict

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

import central_banks_overview.services.central_banks_meetings as central_banks_meetings
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    GetCentralBankMeetingDatesSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    CentralBankMeetingDatesResponseSerializer,
)
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView


class CentralBankMeetingDatesIngestionView(BaseAPIView):
    """Central Bank Meeting Dates Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Central Bank Meeting Dates",
        description="Ingest Central Bank Meeting Dates for a given date.",
        response=CreatedOpenApiResponse(),
    )
    def post(self, _request: Request) -> Response:
        """Get Central Bank Meeting Dates for a given date."""
        central_banks_meetings.ingest_all_central_bank_meeting_dates()
        return Response(
            data={"message": "Central Bank Meeting Dates successfully ingested"},
            status=status.HTTP_201_CREATED,
        )


class GetCentralBankMeetingDatesValidatedData(TypedDict, total=False):
    """Validated data for ``GetCentralBankMeetingDatesSerializer``."""

    central_banks: list[CentralBankChoices] | None


class GetCentralBankMeetingDatesView(BaseAPIView):
    """Get Central Bank Meeting Dates APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Get Central Bank Meeting Dates",
        description="Get Central Bank Meeting Dates.",
        request_serializer=GetCentralBankMeetingDatesSerializer,
        response=OkOpenApiResponse(CentralBankMeetingDatesResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("Invalid central_banks.")],
    )
    def get(self, validated_data: GetCentralBankMeetingDatesValidatedData) -> Response:
        """Get Central Bank Meeting Dates."""
        central_banks = validated_data.get("central_banks") or []

        meeting_dates = central_banks_meetings.get_central_bank_meeting_dates(
            central_banks
        )
        return Response(
            data=CentralBankMeetingDatesResponseSerializer(
                meeting_dates, many=True
            ).data,
            status=status.HTTP_200_OK,
        )
