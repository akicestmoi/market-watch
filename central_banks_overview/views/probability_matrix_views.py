from datetime import date
from typing import Optional

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.cb_inference_services as cb_inference_services
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    GetCentralBankProbabilityMatrixSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    CentralBankProbabilityMatrixResponseSerializer,
)
from core.open_api import ApiTags, OkOpenApiResponse, open_api
from core.views import BaseAPIView


class GetCentralBankProbabilityMatrixView(BaseAPIView):
    """Get Central Bank Probability Matrix APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Get Central Bank Probability Matrix",
        description="Get Central Bank Probability Matrix.",
        request_serializer=GetCentralBankProbabilityMatrixSerializer,
        response=OkOpenApiResponse(CentralBankProbabilityMatrixResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get Central Bank Probability Matrix."""
        target_date: date = validated_data["date"]
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        probability_matrices = (
            cb_inference_services.get_central_bank_probability_matrices(
                target_date, central_banks
            )
        )
        return Response(
            data=CentralBankProbabilityMatrixResponseSerializer(
                probability_matrices, many=True
            ).data,
            status=status.HTTP_200_OK,
        )
