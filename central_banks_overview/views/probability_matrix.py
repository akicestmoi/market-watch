"""API views for rate-path probability matrices."""

from datetime import date
from typing import NotRequired, TypedDict

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.central_banks_inference as central_banks_inference
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    GetCentralBankProbabilityMatrixSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    CentralBankProbabilityMatrixResponseSerializer,
)
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView


class GetCentralBankProbabilityMatrixValidatedData(TypedDict):
    """Validated data for ``GetCentralBankProbabilityMatrixSerializer``."""

    date: date
    central_banks: NotRequired[list[CentralBankChoices] | None]


class GetCentralBankProbabilityMatrixView(BaseAPIView):
    """Get Central Bank Probability Matrix APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Get Central Bank Probability Matrix",
        description="Get Central Bank Probability Matrix.",
        request_serializer=GetCentralBankProbabilityMatrixSerializer,
        response=OkOpenApiResponse(CentralBankProbabilityMatrixResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("date is required")],
    )
    def get(
        self, validated_data: GetCentralBankProbabilityMatrixValidatedData
    ) -> Response:
        """Get Central Bank Probability Matrix."""
        target_date: date = validated_data["date"]
        central_banks = validated_data.get("central_banks") or []

        probability_matrices = (
            central_banks_inference.get_central_bank_probability_matrices(
                target_date, central_banks
            )
        )
        return Response(
            data=CentralBankProbabilityMatrixResponseSerializer(
                probability_matrices, many=True
            ).data,
            status=status.HTTP_200_OK,
        )
