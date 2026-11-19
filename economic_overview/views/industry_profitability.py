"""API view to trigger industry profitability ingestion."""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

import economic_overview.services.industry_profitability as industry_profitability
from core.open_api.schema import (
    ApiTags,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    open_api,
)
from core.services.locks import acquire_redis_lock
from core.views import BaseAPIView
from economic_overview.open_api.response_serializers import (
    IndustryProfitabilityIngestionResponseSerializer,
)


class IngestIndustryProfitabilityView(BaseAPIView):
    """Ingest industry profitability tables for US / FR / JP."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Ingest Industry Profitability",
        description=(
            "Scrape and upsert annual industry profitability tables for US, FR, "
            "and JP. Manual trigger: runs immediately regardless of calendar day."
        ),
        response=CreatedOpenApiResponse(
            IndustryProfitabilityIngestionResponseSerializer
        ),
        error_responses=[
            ConflictOpenApiResponse(
                "Industry profitability ingest is already in progress."
            ),
        ],
    )
    def post(self, _request: Request) -> Response:
        """Ingest industry profitability rankings."""
        with acquire_redis_lock(
            "economic_overview:industry_profitability_ingest",
            locked_detail="Industry profitability ingest is already in progress.",
        ):
            report = industry_profitability.ingest_industry_profitability(force=True)
        return Response(
            data=IndustryProfitabilityIngestionResponseSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )
