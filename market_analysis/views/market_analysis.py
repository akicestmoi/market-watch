"""API views to fetch or generate the daily market analysis recap."""

from datetime import date
from typing import NotRequired, TypedDict

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_analysis.models import DailyRecapModel
from market_analysis.open_api.request_serializers import (
    GetRecapSerializer,
    ReportingDateSerializer,
)
from market_analysis.open_api.response_serializers import RecapResponseSerializer
from market_analysis.services import llm_market_recap, market_analysis


class GetRecapValidatedData(TypedDict, total=False):
    """Validated data for ``GetRecapSerializer``."""

    reporting_date: date
    id: int


class GetDailyRecapView(BaseAPIView):
    """Fetch the latest or date-specific daily market recap."""

    @open_api(
        tags=[ApiTags.MARKET_ANALYSIS],
        summary="Get daily research recap",
        description="Return the AI-generated daily market recap for a date (or the latest).",
        request_serializer=GetRecapSerializer,
        response=OkOpenApiResponse(RecapResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("Invalid reporting_date or id."),
            NotFoundOpenApiResponse("Recap not found"),
        ],
    )
    def get(self, validated_data: GetRecapValidatedData) -> Response:
        """Return a daily recap by id, reporting date, or the latest row."""
        recap_id: int | None = validated_data.get("id")
        reporting_date: date | None = validated_data.get("reporting_date")
        if recap_id:
            recap = DailyRecapModel.objects.get(id=recap_id)
        else:
            recap = llm_market_recap.get_latest_recap(reporting_date=reporting_date)
            if not recap:
                raise NotFound(detail="Recap not found")
        return Response(RecapResponseSerializer(recap).data)


class ReportingDateValidatedData(TypedDict):
    """Validated data for ``ReportingDateSerializer``."""

    reporting_date: date
    force: NotRequired[bool]


class GenerateDailyRecapView(BaseAPIView):
    """Run the full pipeline (collect → analyze in memory → save daily recap)."""

    @open_api(
        tags=[ApiTags.MARKET_ANALYSIS],
        summary="Generate daily market analysis recap",
        description=(
            "Collect news into memory, analyze it, and save the daily recap "
            "with verified market prices. Articles are not stored in the database."
        ),
        request_serializer=ReportingDateSerializer,
        response=CreatedOpenApiResponse(RecapResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "reporting_date is required | Daily recap was not created"
            ),
            NotFoundOpenApiResponse("Recap not found"),
        ],
    )
    def post(self, validated_data: ReportingDateValidatedData) -> Response:
        """Run the analysis pipeline in-process and return the saved recap."""
        reporting_date = validated_data["reporting_date"]
        force = bool(validated_data.get("force", False))
        result = market_analysis.run_daily_analysis_pipeline_with_lock(
            reporting_date, force=force
        )
        if result.get("status") == "skipped":
            return Response(result, status=status.HTTP_200_OK)
        recap_id = result.get("recap_id")
        if recap_id is None:
            raise ValidationError(
                detail=result.get("message")
                or result.get("reason")
                or "Daily recap was not created"
            )
        recap = DailyRecapModel.objects.get(id=recap_id)
        return Response(
            RecapResponseSerializer(recap).data,
            status=status.HTTP_201_CREATED,
        )
