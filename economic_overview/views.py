import json
from datetime import date, timedelta
from typing import List, Optional, TypedDict

from rest_framework import status
from rest_framework.response import Response

import economic_overview.services as economic_overview_services
from economic_overview.models import (
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from economic_overview.request_serializers import (
    EconomicDataIngestionSerializer,
    SpecificEconomicDataIngestionSerializer,
    UpdatePublicationScheduleSerializer,
)
from economic_overview.response_serializers import (
    EconomicDataIngestionResponseSerializer,
    SpecificEconomicDataIngestionResponseSerializer,
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

    def _validate_indicators_exist(
        self, indicator_names: List[str]
    ) -> Optional[Response]:
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
                    "schedule_not_updated": schedule_not_updated,
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
        start_date: date = validated_data.get(
            "start_date", date.today() - timedelta(days=30)
        )
        end_date: date = validated_data.get("end_date", date.today())
        update_schedule: bool = validated_data.get("update_schedule", True)

        indicators = economic_overview_services.get_economic_indicators_to_update(
            start_date=start_date,
            end_date=end_date,
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
                    "indicator_not_updated": indicator_not_updated,
                    "schedule_not_updated": schedule_not_updated,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class SpecificEconomicDataIngestionItem(TypedDict):
    """Specific Economic Data Ingestion Item."""

    indicator_name: str
    periods: List[str]


class IngestSpecificEconomicDataView(EconomicOverviewBaseView):
    """Ingest Specific Economic Data APIView."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Ingest Specific Economic Data",
        description="Ingest specific economic data for a specific indicator and period.",
        request_serializer=SpecificEconomicDataIngestionSerializer,
        response=CreatedOpenApiResponse(
            SpecificEconomicDataIngestionResponseSerializer
        ),
        error_responses=[NotFoundOpenApiResponse("Indicator not found")],
    )
    def post(self, validated_data: List[SpecificEconomicDataIngestionItem]) -> Response:
        """Ingest specific economic data for a specific indicator and period."""
        indicator_names: List[str] = [item["indicator_name"] for item in validated_data]
        periods: List[List[str]] = [item["periods"] for item in validated_data]
        validation_error = self._validate_indicators_exist(indicator_names)
        if validation_error:
            return validation_error

        indicators = economic_overview_services.get_economic_indicators_by_names(
            indicator_names=indicator_names
        )
        indicator_not_updated = (
            economic_overview_services.ingest_specific_economic_data(
                indicators, periods=periods
            )
        )
        return Response(
            data=SpecificEconomicDataIngestionResponseSerializer(
                {
                    "message": "Economic data successfully ingested",
                    "indicator_not_updated": indicator_not_updated,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )
