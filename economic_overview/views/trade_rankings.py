"""API views to trigger trade ranking ingestion."""

from typing import NotRequired, TypedDict

from rest_framework import status
from rest_framework.response import Response

from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    ConflictOpenApiResponse,
    CreatedOpenApiResponse,
    open_api,
)
from core.services.locks import acquire_redis_lock
from core.views import BaseAPIView
from economic_overview.models.trade_ranking import TradeTypeChoices
from economic_overview.open_api.request_serializers import (
    TradeRankingIngestionSerializer,
)
from economic_overview.open_api.response_serializers import (
    TradeRankingIngestionResponseSerializer,
)
from economic_overview.services import trade_ranking


class _TradeRankingIngestionValidatedData(TypedDict):
    """Validated data for 'TradeRankingIngestionSerializer'."""

    trade_type: NotRequired[str]
    full_history: NotRequired[bool]


class IngestTradeRankingsView(BaseAPIView):
    """Ingest customs trade rankings for US / FR / JP."""

    @open_api(
        tags=[ApiTags.ECONOMIC_DATA],
        summary="Ingest Trade Rankings",
        description=(
            "Scrape and upsert annual Top-N product and partner rankings plus "
            "product×partner cells for US, FR, and JP. Optional 'trade_type' "
            "selects one ranking family; omit it to ingest both. Manual trigger: "
            "runs immediately regardless of calendar day."
        ),
        request_serializer=TradeRankingIngestionSerializer,
        response=CreatedOpenApiResponse(TradeRankingIngestionResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("trade_type is not a valid choice"),
            ConflictOpenApiResponse("Trade ranking ingest is already in progress."),
        ],
    )
    def post(self, validated_data: _TradeRankingIngestionValidatedData) -> Response:
        """Ingest trade rankings for the requested type, or both when omitted."""
        trade_type_value = validated_data.get("trade_type")
        trade_type = (
            TradeTypeChoices(trade_type_value) if trade_type_value is not None else None
        )
        full_history = validated_data.get("full_history", False)
        with acquire_redis_lock(
            "economic_overview:trade_ranking_ingest",
            locked_detail="Trade ranking ingest is already in progress.",
        ):
            report = trade_ranking.ingest_trade_rankings(
                trade_type=trade_type,
                force=True,
                full_history=full_history,
            )
        return Response(
            data=TradeRankingIngestionResponseSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )
