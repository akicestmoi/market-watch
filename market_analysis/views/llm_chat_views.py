"""API views for market-analysis chat."""

from rest_framework import status
from rest_framework.response import Response

from core.open_api import ApiTags, CreatedOpenApiResponse, open_api
from core.views import BaseAPIView
from market_analysis.open_api.request_serializers import ChatAskSerializer
from market_analysis.open_api.response_serializers import ChatResponseSerializer
from market_analysis.services import llm_interaction_services


class AnalysisChatView(BaseAPIView):
    """Chat with the market-analysis agent; prior messages are passed for continuity."""

    @open_api(
        tags=[ApiTags.MARKET_ANALYSIS],
        summary="Ask the market analysis agent",
        description=(
            "One-shot or multi-turn chat. Send prior turns in `messages` "
            "when you want continuity."
        ),
        request_serializer=ChatAskSerializer,
        response=CreatedOpenApiResponse(ChatResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Ask the market-analysis agent; optional prior messages for continuity."""
        result = llm_interaction_services.ask(
            validated_data["question"],
            messages=validated_data.get("messages") or [],
        )
        return Response(
            ChatResponseSerializer(result).data, status=status.HTTP_201_CREATED
        )
