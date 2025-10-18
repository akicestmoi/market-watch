import functools
from enum import Enum
from typing import List, Optional

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers


class ApiTags(str, Enum):
    """API Tags for OpenAPI documentation."""

    MARKET_DATA = "Market Data"
    ECONOMIC_DATA = "Economic Data"


class OpenApiBaseRequest:
    """Open API Base Request."""

    def __init__(
        self,
        tags: List[ApiTags],
        summary: str,
        description: str,
        responses: List[OpenApiResponse],
        parameters: Optional[List[OpenApiParameter]] = None,
        request: Optional[serializers.Serializer] = None,
    ):
        self.tags = tags
        self.summary = summary
        self.description = description
        self.responses = responses
        self.parameters = parameters or []
        self.request = request or None


def open_api(schema: OpenApiBaseRequest):
    """Open API Decorator."""

    def decorator(func):
        @extend_schema(
            tags=[tag.value for tag in schema.tags],
            summary=schema.summary,
            description=schema.description,
            parameters=schema.parameters,
            request=schema.request,
            responses={response.response: response for response in schema.responses},
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator
