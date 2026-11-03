"""API views to scrape and return extracted market-wrap articles."""

from datetime import date
from typing import TypedDict

from rest_framework.response import Response

from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_analysis.models import ArticleRegionChoices, NewsSourceChoices
from market_analysis.open_api.request_serializers import ExtractArticleSerializer
from market_analysis.open_api.response_serializers import (
    ExtractArticleResponseSerializer,
)
from market_analysis.services.article_extraction import extract_all_articles


class _ExtractArticleValidatedData(TypedDict):
    """Validated data for 'ExtractArticleSerializer'."""

    reporting_date: date
    source: str | None
    region: str | None


class _ExtractedArticleWire(TypedDict):
    """Wire shape for one scraped wrap in the extract-article response."""

    source_key: str
    source_name: str
    regions: list[str]
    url: str
    title: str
    content: str


class _ExtractArticleSourceWire(TypedDict):
    """Wire shape for one per-source scrape status (articles live only at top level)."""

    source_id: str
    name: str
    base_url: str
    regions: list[str]
    comment: str | None


class _ExtractArticleResponseWire(TypedDict):
    """Wire shape for 'ExtractArticleResponseSerializer'."""

    reporting_date: date
    source: str | None
    region: str | None
    articles: list[_ExtractedArticleWire]
    sources: list[_ExtractArticleSourceWire]


class ExtractArticleView(BaseAPIView):
    """Scrape catalog news sources and return extracted wrap(s)."""

    @open_api(
        tags=[ApiTags.MARKET_ANALYSIS],
        summary="Extract market-wrap articles",
        description=(
            "Scrape catalog news sources for the reporting date. "
            "'reporting_date' is required. Optional 'source' and 'region' "
            "narrow the scrape: source only → all regions for that source; "
            "region only → every source that lists the region; both → that "
            "source's wraps for the region; neither → every source and region. "
            "An empty articles list with per-source comments means no matching "
            "wraps were found."
        ),
        request_serializer=ExtractArticleSerializer,
        response=OkOpenApiResponse(ExtractArticleResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "reporting_date is required | source is not a valid choice | "
                "region is not a valid choice | region is not available for source"
            ),
            NotFoundOpenApiResponse("News source is not configured"),
        ],
    )
    def get(self, validated_data: _ExtractArticleValidatedData) -> Response:
        """Extract wraps for the reporting date with optional source/region filters."""
        reporting_date = validated_data["reporting_date"]
        source_value = validated_data.get("source")
        region_value = validated_data.get("region")
        source = NewsSourceChoices(source_value) if source_value is not None else None
        region = (
            ArticleRegionChoices(region_value) if region_value is not None else None
        )
        extracted_articles = extract_all_articles(
            reporting_date=reporting_date,
            source=source,
            region=region,
        )
        payload = _ExtractArticleResponseWire(
            reporting_date=extracted_articles["reporting_date"],
            source=source.value if source is not None else None,
            region=region.value if region is not None else None,
            articles=[
                _ExtractedArticleWire(
                    source_key=article["source_key"].value,
                    source_name=article["source_name"],
                    regions=[item.value for item in article["regions"]],
                    url=article["url"],
                    title=article["title"],
                    content=article["content"],
                )
                for article in extracted_articles["articles"]
            ],
            sources=[
                _ExtractArticleSourceWire(
                    source_id=source_result["source_id"].value,
                    name=source_result["name"],
                    base_url=source_result["base_url"],
                    regions=[item.value for item in source_result["regions"]],
                    comment=source_result.get("comment"),
                )
                for source_result in extracted_articles["sources"]
            ],
        )
        return Response(ExtractArticleResponseSerializer(payload).data)
