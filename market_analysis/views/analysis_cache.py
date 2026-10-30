"""API views to inspect Redis-cached same-day article analyses."""

from datetime import date
from typing import NotRequired, TypedDict

from rest_framework.response import Response

from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_analysis.open_api.request_serializers import GetArticleCacheSerializer
from market_analysis.open_api.response_serializers import ArticleCacheResponseSerializer
from market_analysis.services.cache import list_cached_analyses


class GetArticleCacheValidatedData(TypedDict):
    """Validated data for ``GetArticleCacheSerializer``."""

    reporting_date: date
    source_url: NotRequired[str]


class GetArticleAnalysisCacheView(BaseAPIView):
    """Inspect same-day Redis-cached article analyses (24h TTL, not Postgres)."""

    @open_api(
        tags=[ApiTags.MARKET_ANALYSIS],
        summary="List cached article analyses",
        description=(
            "Return ArticleAnalysis digests cached in Redis for a reporting date. "
            "Optional source_url fetches a single entry. "
            "Entries expire after 24 hours and are keyed by article URL + prompt version."
        ),
        request_serializer=GetArticleCacheSerializer,
        response=OkOpenApiResponse(ArticleCacheResponseSerializer),
        error_responses=[BadRequestOpenApiResponse("reporting_date is required")],
    )
    def get(self, validated_data: GetArticleCacheValidatedData) -> Response:
        """List Redis-cached article analyses for a reporting date."""
        reporting_date: date = validated_data["reporting_date"]
        source_url: str | None = validated_data.get("source_url") or None
        result = list_cached_analyses(
            reporting_date,
            source_url=source_url or None,
        )
        return Response(ArticleCacheResponseSerializer(result).data)
