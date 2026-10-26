"""API views for market-analysis chat."""

from typing import Literal, NotRequired, TypedDict

from rest_framework import status
from rest_framework.response import Response

from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    CreatedOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_analysis.open_api.request_serializers import ChatAskSerializer
from market_analysis.open_api.response_serializers import ChatResponseSerializer
from market_analysis.services import llm_interaction
from market_analysis.services.llm_interaction import ChatMessage


class ChatMessageValidatedData(TypedDict):
    """Validated data for one prior chat turn."""

    role: Literal["user", "assistant"]
    content: str


class ChatAskValidatedData(TypedDict):
    """Validated data for ``ChatAskSerializer``."""

    question: str
    messages: NotRequired[list[ChatMessageValidatedData]]


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
        error_responses=[
            BadRequestOpenApiResponse(
                "question is required | role is required | content is required"
            )
        ],
    )
    def post(self, validated_data: ChatAskValidatedData) -> Response:
        """Ask the market-analysis agent; optional prior messages for continuity."""
        prior_messages = [
            ChatMessage(role=message["role"], content=message["content"])
            for message in (validated_data.get("messages") or [])
        ]
        result = llm_interaction.ask(
            validated_data["question"],
            messages=prior_messages,
        )
        return Response(
            ChatResponseSerializer(result).data, status=status.HTTP_201_CREATED
        )
