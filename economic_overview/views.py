import json
from datetime import date, timedelta
from typing import List

from rest_framework import status
from rest_framework.response import Response

import economic_overview.services as economic_overview_services
from economic_overview.models import (
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from economic_overview.request_serializers import (
    EconomicDataIngestionSerializer,
    UpdatePublicationScheduleSerializer,
)
from economic_overview.response_serializers import (
    EconomicDataIngestionResponseSerializer,
    UpdatePublicationScheduleResponseSerializer,
)
from shared.open_api import (
    ApiTags,
    CreatedOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from shared.utils import logger
from shared.views import BaseAPIView


class EconomicOverviewBaseView(BaseAPIView):
    """Base view for economic overview operations."""

    def _validate_indicators_exist(self, indicator_names: List[str]) -> Response | None:
        """Validate that all indicator names exist in the database."""
        if not indicator_names:
            return None

        not_existing_indicators = (
            economic_overview_services.identify_not_existing_indicators(indicator_names)
        )
        if not_existing_indicators:
            return Response(
                {
                    "error": f"indicators: {not_existing_indicators} do not exist in database."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return None


class GenerateBaseEconomicIndicatorInformationView(EconomicOverviewBaseView):
    """Generate Base Economic Indicator Information APIView."""

    @open_api(
        tags=[ApiTags.ECONOMIC_INDICATOR_INFORMATION],
        summary="Generate Base Economic Data",
        description="Generate base economic indicator information from JSON file.",
    )
    def post(self, validated_data: dict) -> Response:
        """Generate economic indicator information from economic_data.json."""
        with open("economic_overview/data_sources/economic_data.json") as f:
            economic_data = json.load(f)
        for economic_indicator in economic_data:
            logger.info(
                f"Generating economic indicator information: {economic_indicator}"
            )
            indicator, _ = EconomicIndicatorInformationModel.objects.update_or_create(
                id=economic_indicator["id"], defaults=economic_indicator
            )
            PublicationScheduleModel.objects.update_or_create(
                indicator=indicator,
                previous_publication_date=None,
                current_publication_date=None,
                next_publication_date=None,
            )

        return Response(
            data={
                "message": "Economic indicator information successfully generated.",
            },
            status=status.HTTP_200_OK,
        )


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

        indicators = economic_overview_services.get_economic_indicators_by_names(
            indicator_names
        )
        schedule_not_updated = economic_overview_services.update_publication_schedules(
            indicators
        )
        return Response(
            data=UpdatePublicationScheduleResponseSerializer(
                {
                    "message": "Publication schedule successfully updated.",
                    "schedule_not_updated": [
                        schedule.indicator.name for schedule in schedule_not_updated
                    ],
                }
            ).data,
            status=status.HTTP_200_OK,
        )


class IngestEconomicDataView(EconomicOverviewBaseView):
    """Ingest Economic Data APIView."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Ingest Economic Data",
        description="Ingest economic data from various sources.",
        request_serializer=EconomicDataIngestionSerializer,
        response=CreatedOpenApiResponse(EconomicDataIngestionResponseSerializer),
        error_responses=[NotFoundOpenApiResponse("Indicator not found")],
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest economic data from various sources."""
        indicator_names: List[str] = validated_data.get("indicator_names", [])
        start_date: date = validated_data.get(
            "start_date", date.today() - timedelta(days=30)
        )
        end_date: date = validated_data.get("end_date", date.today())
        update_schedule: bool = validated_data.get("update_schedule", True)

        validation_error = self._validate_indicators_exist(indicator_names)
        if validation_error:
            return validation_error

        indicators = economic_overview_services.get_economic_indicators_to_update(
            start_date=start_date,
            end_date=end_date,
            indicator_names=indicator_names,
        )
        if not indicators:
            return Response(
                {
                    "message": "No indicators found for the specified criteria.",
                    "updated_indicators": [],
                    "indicator_not_updated": [],
                    "schedule_not_updated": [],
                },
                status=status.HTTP_200_OK,
            )

        logger.info(
            f"Ingesting economic data for {len(indicators)} indicators: {[indicator.name for indicator in indicators]} and for dates between: {start_date} and {end_date}"
        )
        indicator_not_updated = economic_overview_services.ingest_economic_data(
            indicators
        )
        schedule_not_updated = []
        if update_schedule:
            schedule_not_updated = (
                economic_overview_services.update_publication_schedules(indicators)
            )

        return Response(
            data=EconomicDataIngestionResponseSerializer(
                {
                    "message": "Economic data successfully ingested",
                    "updated_indicators": [indicator.name for indicator in indicators],
                    "indicator_not_updated": [
                        indicator["indicator"].name
                        for indicator in indicator_not_updated
                    ],
                    "schedule_not_updated": (
                        [schedule.indicator.name for schedule in schedule_not_updated]
                        if schedule_not_updated
                        else []
                    ),
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )
