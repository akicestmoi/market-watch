"""API views for economic data ingestion and retrieval."""

import json
from datetime import date
from typing import NotRequired, TypedDict

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

import economic_overview.services.data_ingestion as data_ingestion
import economic_overview.services.economic_data as economic_data
import economic_overview.services.publication as publication
from core.locks import acquire_redis_lock
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
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
    HistoricalEconomicDataIngestionSerializer,
    LatestEconomicDataIngestionSerializer,
    ListEconomicDataSerializer,
    SpecificEconomicDataIngestionSerializer,
)
from economic_overview.open_api.response_serializers import (
    DeleteEconomicDataResponseSerializer,
    EconomicDataResponseSerializer,
    HistoricalEconomicDataIngestionResponseSerializer,
    LatestEconomicDataIngestionResponseSerializer,
    SpecificEconomicDataIngestionResponseSerializer,
)

ECONOMIC_DATA_JSON = "economic_overview/data_sources/economic_data.json"


class EconomicOverviewBaseView(BaseAPIView):
    """Base view for economic overview operations."""

    def _validate_indicators_exist(self, indicator_names: list[str]) -> None:
        """Raise NotFound if any indicator name is missing from the database."""
        if not indicator_names:
            return None

        not_existing_indicators = economic_data.identify_not_existing_indicators(
            indicator_names
        )
        if not_existing_indicators:
            raise NotFound(
                detail=(
                    f"indicators: {not_existing_indicators} do not exist in database."
                )
            )


class GenerateBaseEconomicIndicatorInformationView(BaseAPIView):
    """Generate Base Economic Indicator Information APIView."""

    @open_api(
        tags=[ApiTags.ECONOMIC_INDICATOR_INFORMATION],
        summary="Generate Base Economic Data",
        description="Generate base economic indicator information from JSON file.",
    )
    def post(self, _request: Request) -> Response:
        """Generate economic indicator information from economic_data.json."""
        with open(ECONOMIC_DATA_JSON) as f:
            indicator_records = json.load(f)
        for economic_indicator in indicator_records:
            logger.info(
                f"Generating economic indicator information: {economic_indicator}"
            )
            indicator, _ = EconomicIndicatorInformationModel.objects.update_or_create(
                id=economic_indicator["id"], defaults=economic_indicator
            )
            # Lookup by indicator only — including null date fields in the
            # lookup creates a second empty schedule whenever dates are filled.
            PublicationScheduleModel.objects.get_or_create(indicator=indicator)

        return Response(
            data={
                "message": "Economic indicator information successfully generated.",
            },
            status=status.HTTP_200_OK,
        )


class _LatestEconomicDataIngestionValidatedData(TypedDict, total=False):
    """Validated data for ``LatestEconomicDataIngestionSerializer``."""

    update_schedule: bool


class IngestLatestEconomicDataView(EconomicOverviewBaseView):
    """Ingest the latest observation for every economic indicator."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Ingest Latest Economic Data",
        description=(
            "Ingest the latest available observation for every seeded economic "
            "indicator. Optionally refresh publication schedules for those indicators."
        ),
        request_serializer=LatestEconomicDataIngestionSerializer,
        response=CreatedOpenApiResponse(LatestEconomicDataIngestionResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid update_schedule."),
            ConflictOpenApiResponse("Economic data ingestion is already in progress."),
        ],
    )
    def post(
        self, validated_data: _LatestEconomicDataIngestionValidatedData
    ) -> Response:
        """Ingest the latest observation for all indicators."""
        update_schedule: bool = validated_data.get("update_schedule", True)
        indicators = economic_data.get_economic_indicators_by_names()

        with acquire_redis_lock(
            data_ingestion.get_economic_data_ingestion_lock_key(),
            locked_detail="Economic data ingestion is already in progress.",
        ):
            indicator_not_updated = data_ingestion.ingest_latest_economic_data(
                indicators
            )
            schedule_not_updated = []
            if update_schedule:
                schedule_not_updated = publication.update_publication_schedules(
                    indicators
                )
        return Response(
            data=LatestEconomicDataIngestionResponseSerializer(
                {
                    "message": "Latest economic data successfully ingested",
                    "updated_indicators": [indicator.name for indicator in indicators],
                    "indicator_not_updated": indicator_not_updated,
                    "schedule_not_updated": schedule_not_updated,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class _HistoricalEconomicDataIngestionValidatedData(TypedDict):
    """Validated data for ``HistoricalEconomicDataIngestionSerializer``."""

    start_date: date
    end_date: date
    indicators: NotRequired[list[str]]


class IngestHistoricalEconomicDataView(EconomicOverviewBaseView):
    """Ingest historical observations for a date window."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Ingest Historical Economic Data",
        description=(
            "Ingest every available observation whose period falls in "
            "[start_date, end_date] inclusive. Pass `indicators` as indicator names "
            "to restrict the run; omit or pass an empty list to ingest all indicators."
        ),
        request_serializer=HistoricalEconomicDataIngestionSerializer,
        response=CreatedOpenApiResponse(
            HistoricalEconomicDataIngestionResponseSerializer
        ),
        error_responses=[
            BadRequestOpenApiResponse(
                "end_date must be greater than or equal to start_date."
            ),
            NotFoundOpenApiResponse("Indicator not found"),
            ConflictOpenApiResponse("Economic data ingestion is already in progress."),
        ],
    )
    def post(
        self, validated_data: _HistoricalEconomicDataIngestionValidatedData
    ) -> Response:
        """Ingest historical economic data for a date window."""
        start_date: date = validated_data["start_date"]
        end_date: date = validated_data["end_date"]
        indicator_names: list[str] = validated_data.get("indicators", [])

        self._validate_indicators_exist(indicator_names)

        indicators = economic_data.get_economic_indicators_by_names(
            indicator_names=indicator_names
        )
        with acquire_redis_lock(
            data_ingestion.get_economic_data_ingestion_lock_key(),
            locked_detail="Economic data ingestion is already in progress.",
        ):
            indicator_not_updated = data_ingestion.ingest_historical_economic_data(
                indicators, start_date=start_date, end_date=end_date
            )
        return Response(
            data=HistoricalEconomicDataIngestionResponseSerializer(
                {
                    "message": "Historical economic data successfully ingested",
                    "updated_indicators": [indicator.name for indicator in indicators],
                    "indicator_not_updated": indicator_not_updated,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class _SpecificEconomicDataIngestionItemValidatedData(TypedDict):
    """Validated data for ``SpecificEconomicDataIngestionSerializerItem``."""

    indicator_name: str
    periods: list[str]


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
        error_responses=[
            BadRequestOpenApiResponse(
                "indicator_name is required | periods is required"
            ),
            NotFoundOpenApiResponse("Indicator not found"),
            ConflictOpenApiResponse("Economic data ingestion is already in progress."),
        ],
    )
    def post(
        self, validated_data: list[_SpecificEconomicDataIngestionItemValidatedData]
    ) -> Response:
        """Ingest specific economic data for a specific indicator and period."""
        indicator_names: list[str] = [item["indicator_name"] for item in validated_data]
        periods: list[list[str]] = [item["periods"] for item in validated_data]
        self._validate_indicators_exist(indicator_names)

        indicators = economic_data.get_economic_indicators_by_names(
            indicator_names=indicator_names
        )
        with acquire_redis_lock(
            data_ingestion.get_economic_data_ingestion_lock_key(),
            locked_detail="Economic data ingestion is already in progress.",
        ):
            indicator_not_updated = data_ingestion.ingest_specific_economic_data(
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


class _ListEconomicDataValidatedData(TypedDict, total=False):
    """Validated data for ``ListEconomicDataSerializer``."""

    indicator_names: list[str]
    period: str


class _DeleteEconomicDataValidatedData(TypedDict, total=False):
    """Validated data for ``DeleteEconomicDataSerializer``."""

    ids: list[int] | None


class EconomicDataDetailedView(EconomicOverviewBaseView):
    """Economic Data Detailed APIView."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Get Economic Data Detailed",
        description="Get economic data detailed for a specific indicator and period.",
        request_serializer=ListEconomicDataSerializer,
        response=OkOpenApiResponse(EconomicDataResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid indicator_names or period."),
            NotFoundOpenApiResponse("Indicator not found"),
        ],
    )
    def get(self, validated_data: _ListEconomicDataValidatedData) -> Response:
        """List economic data for a specific indicator and period."""
        indicator_names: list[str] = validated_data.get("indicator_names", [])
        period: str | None = validated_data.get("period")

        if indicator_names:
            self._validate_indicators_exist(indicator_names)

        economic_data_rows = economic_data.get_economic_data(indicator_names, period)
        return Response(
            data=EconomicDataResponseSerializer(economic_data_rows, many=True).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Delete Economic Data",
        description="Delete economic data by IDs.",
        request_serializer=DeleteEconomicDataSerializer,
        response=OkOpenApiResponse(DeleteEconomicDataResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("IDs must be comma-separated integers.")
        ],
    )
    def delete(self, validated_data: _DeleteEconomicDataValidatedData) -> Response:
        """Delete economic data by IDs."""
        ids: list[int] = validated_data.get("ids") or []

        deleted_count = economic_data.delete_economic_data(ids)
        return Response(
            data=DeleteEconomicDataResponseSerializer(
                {
                    "message": "Economic data successfully deleted",
                    "deleted_count": deleted_count,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
