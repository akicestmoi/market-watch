"""API views for publication schedule and monthly calendar-less updates."""

from typing import TypedDict

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

import economic_overview.services.economic_data as economic_data
import economic_overview.services.publication_update as publication_update
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services.locks import acquire_redis_lock
from core.views import BaseAPIView
from economic_overview.open_api.request_serializers import (
    UpdatePublicationScheduleSerializer,
)
from economic_overview.open_api.response_serializers import (
    MonthlyPublicationUpdateResponseSerializer,
    UpdatePublicationScheduleResponseSerializer,
)
from economic_overview.views.economic_data import EconomicOverviewBaseView


class RunMonthlyPublicationUpdateView(BaseAPIView):
    """Update indicators tagged for monthly calendar-less refresh."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Run Monthly Publication Update",
        description=(
            "Refresh indicators without an official release calendar "
            "(MONTHLY_UPDATE). Manual trigger: runs immediately regardless of "
            "calendar day."
        ),
        response=CreatedOpenApiResponse(MonthlyPublicationUpdateResponseSerializer),
        error_responses=[
            ConflictOpenApiResponse(
                "Monthly publication update is already in progress."
            ),
        ],
    )
    def post(self, _request: Request) -> Response:
        """Run the monthly calendar-less publication update."""
        with acquire_redis_lock(
            "economic_overview:monthly_publication_update",
            locked_detail="Monthly publication update is already in progress.",
        ):
            report = publication_update.run_monthly_publication_update(force=True)
        return Response(
            data=MonthlyPublicationUpdateResponseSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )


class _UpdatePublicationScheduleValidatedData(TypedDict, total=False):
    """Validated data for 'UpdatePublicationScheduleSerializer'."""

    indicator_names: list[str]


class UpdatePublicationScheduleView(EconomicOverviewBaseView):
    """Update Publication Schedule APIView."""

    @open_api(
        tags=[ApiTags.PUBLICATION_SCHEDULE],
        summary="Update Publication Schedule",
        description=(
            "Update publication schedules. Pass `indicator_names` to restrict; "
            "omit or pass an empty list to update all indicators."
        ),
        request_serializer=UpdatePublicationScheduleSerializer,
        response=OkOpenApiResponse(UpdatePublicationScheduleResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("indicator_names must be a list of strings."),
            NotFoundOpenApiResponse("Indicator not found"),
        ],
    )
    def post(self, validated_data: _UpdatePublicationScheduleValidatedData) -> Response:
        """Update publication schedule for specific economic indicators."""
        indicator_names: list[str] = validated_data.get("indicator_names", [])

        self._validate_indicators_exist(indicator_names)

        indicators = economic_data.get_economic_indicators_by_names(indicator_names)
        schedule_not_updated = publication_update.update_publication_schedules(
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
