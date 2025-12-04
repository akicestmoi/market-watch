from typing import List

from rest_framework import status
from rest_framework.response import Response

import economic_overview.services.economic_data_services as economic_data_services
import economic_overview.services.publication_services as publication_services
from core.open_api import ApiTags, NotFoundOpenApiResponse, OkOpenApiResponse, open_api
from economic_overview.open_api.request_serializers import (
    UpdatePublicationScheduleSerializer,
)
from economic_overview.open_api.response_serializers import (
    UpdatePublicationScheduleResponseSerializer,
)
from economic_overview.views.economic_data_views import EconomicOverviewBaseView


class UpdatePublicationScheduleView(EconomicOverviewBaseView):
    """Update Publication Schedule APIView."""

    @open_api(
        tags=[ApiTags.PUBLICATION_SCHEDULE],
        summary="Update Publication Schedule",
        description="Update publication schedule for specific economic indicators.",
        request_serializer=UpdatePublicationScheduleSerializer,
        response=OkOpenApiResponse(UpdatePublicationScheduleResponseSerializer),
        error_responses=[NotFoundOpenApiResponse("Indicator not found")],
    )
    def post(self, validated_data: dict) -> Response:
        """Update publication schedule for specific economic indicators."""
        indicator_names: List[str] = validated_data.get("indicator_names", [])

        validation_error = self._validate_indicators_exist(indicator_names)
        if validation_error:
            return validation_error

        indicators = economic_data_services.get_economic_indicators_by_names(
            indicator_names
        )
        schedule_not_updated = publication_services.update_publication_schedules(
            indicators
        )
        return Response(
            data=UpdatePublicationScheduleResponseSerializer(
                {
                    "message": "Publication schedule successfully updated.",
                    "schedule_not_updated": schedule_not_updated,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
