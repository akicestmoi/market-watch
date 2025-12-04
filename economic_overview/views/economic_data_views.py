import json
from datetime import date, timedelta
from typing import List, Optional, TypedDict

from rest_framework import status
from rest_framework.response import Response

import economic_overview.services.data_ingestion_services as data_ingestion_services
import economic_overview.services.economic_data_services as economic_data_services
import economic_overview.services.publication_services as publication_services
from core.open_api import (
    ApiTags,
    CreatedOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.services import logger
from core.views import BaseAPIView
from economic_overview.models import (
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from economic_overview.open_api.request_serializers import (
    DeleteEconomicDataSerializer,
    EconomicDataIngestionSerializer,
    ListEconomicDataSerializer,
    SpecificEconomicDataIngestionSerializer,
)
from economic_overview.open_api.response_serializers import (
    EconomicDataIngestionResponseSerializer,
    EconomicDataResponseSerializer,
    SpecificEconomicDataIngestionResponseSerializer,
)


class EconomicOverviewBaseView(BaseAPIView):
    """Base view for economic overview operations."""

    def _validate_indicators_exist(
        self, indicator_names: List[str]
    ) -> Optional[Response]:
        """Validate that all indicator names exist in the database."""
        if not indicator_names:
            return None

        not_existing_indicators = (
            economic_data_services.identify_not_existing_indicators(indicator_names)
        )
        if not_existing_indicators:
            return Response(
                {
                    "error": f"indicators: {not_existing_indicators} do not exist in database."
                },
                status=status.HTTP_404_NOT_FOUND,
            )


class GenerateBaseEconomicIndicatorInformationView(BaseAPIView):
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

        indicators = economic_data_services.get_economic_indicators_to_update(
            start_date=start_date,
            end_date=end_date,
        )
        indicator_not_updated = data_ingestion_services.ingest_economic_data(indicators)
        schedule_not_updated = []
        if update_schedule:
            schedule_not_updated = publication_services.update_publication_schedules(
                indicators
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

        indicators = economic_data_services.get_economic_indicators_by_names(
            indicator_names=indicator_names
        )
        indicator_not_updated = data_ingestion_services.ingest_specific_economic_data(
            indicators, periods=periods
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


class EconomicDataDetailedView(EconomicOverviewBaseView):
    """Economic Data Detailed APIView."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Get Economic Data Detailed",
        description="Get economic data detailed for a specific indicator and period.",
        request_serializer=ListEconomicDataSerializer,
        response=OkOpenApiResponse(EconomicDataResponseSerializer),
        error_responses=[NotFoundOpenApiResponse("Indicator not found")],
    )
    def get(self, validated_data: dict) -> Response:
        """List economic data for a specific indicator and period."""
        indicator_names: List[str] = validated_data.get("indicator_names", [])
        period: Optional[str] = validated_data.get("period")

        if indicator_names:
            validation_error = self._validate_indicators_exist(indicator_names)
            if validation_error:
                return validation_error

        economic_data = economic_data_services.get_economic_data(
            indicator_names, period
        )
        return Response(
            data=EconomicDataResponseSerializer(economic_data, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Delete Economic Data",
        description="Delete economic data",
        request_serializer=DeleteEconomicDataSerializer,
        error_responses=[NotFoundOpenApiResponse("Indicator not found")],
    )
    def delete(self, validated_data: dict) -> Response:
        """Delete economic data for a specific indicator and period."""
        indicator_name: str = validated_data["indicator_name"]
        period: str = validated_data["period"]

        validation_error = self._validate_indicators_exist([indicator_name])
        if validation_error:
            return validation_error

        economic_data_services.delete_economic_data(indicator_name, period)
        return Response(
            data={"message": "Economic data successfully deleted"},
            status=status.HTTP_200_OK,
        )
