"""API views to inspect Redis-cached same-day article analyses."""

from datetime import date
from typing import Optional

from rest_framework.response import Response

from core.open_api import ApiTags, OkOpenApiResponse, open_api
from core.views import BaseAPIView
from market_analysis.open_api.request_serializers import GetArticleCacheSerializer
from market_analysis.open_api.response_serializers import ArticleCacheResponseSerializer
from market_analysis.services import analysis_cache_services


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
    )
    def get(self, validated_data: dict) -> Response:
        """List Redis-cached article analyses for a reporting date."""
        reporting_date: date = validated_data["reporting_date"]
        source_url: Optional[str] = validated_data.get("source_url") or None
        result = analysis_cache_services.list_cached_analyses(
            reporting_date,
            source_url=source_url or None,
        )
        return Response(ArticleCacheResponseSerializer(result).data)
