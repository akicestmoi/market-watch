"""API views to fetch or generate the daily market analysis recap."""

from datetime import date
from typing import Optional

from rest_framework import status
from rest_framework.response import Response

from core.open_api import (
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
from market_analysis.services import llm_market_recap_services, market_analysis_services


class GetDailyRecapView(BaseAPIView):
    """Fetch the latest or date-specific daily market recap."""

    @open_api(
        tags=[ApiTags.MARKET_ANALYSIS],
        summary="Get daily research recap",
        description="Return the AI-generated daily market recap for a date (or the latest).",
        request_serializer=GetRecapSerializer,
        response=OkOpenApiResponse(RecapResponseSerializer),
        error_responses=[NotFoundOpenApiResponse("Recap not found")],
    )
    def get(self, validated_data: dict) -> Response:
        """Return a daily recap by id, reporting date, or the latest row."""
        recap_id: Optional[int] = validated_data.get("id")
        reporting_date: Optional[date] = validated_data.get("reporting_date")
        if recap_id:
            recap = DailyRecapModel.objects.filter(id=recap_id).first()
        else:
            recap = llm_market_recap_services.get_latest_recap(
                reporting_date=reporting_date
            )
        if not recap:
            return Response(
                {
                    "error": "Not Found",
                    "message": "Recap not found",
                    "status_code": 404,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(RecapResponseSerializer(recap).data)


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
        error_responses=[BadRequestOpenApiResponse()],
    )
    def post(self, validated_data: dict) -> Response:
        """Run the analysis pipeline in-process and return the saved recap."""
        reporting_date = validated_data["reporting_date"]
        force = bool(validated_data.get("force", False))
        result = market_analysis_services.run_daily_analysis_pipeline_with_lock(
            reporting_date, force=force
        )
        if result.get("status") == "skipped":
            return Response(result, status=status.HTTP_200_OK)
        recap = DailyRecapModel.objects.get(id=result["recap_id"])
        return Response(
            RecapResponseSerializer(recap).data,
            status=status.HTTP_201_CREATED,
        )
