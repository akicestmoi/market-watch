"""Shared OpenAPI / drf-spectacular helpers and API tag definitions."""

import functools
from enum import Enum
from typing import TypeVar

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import serializers, status
from rest_framework.response import Response


class ApiTags(str, Enum):
    """API Tags for OpenAPI documentation."""

    ASSETS = "Assets"
    ASSET_PRICES = "Asset Prices"
    ECONOMIC_INDICATOR_INFORMATION = "Economic Indicator Information"
    ECONOMIC_DATA = "Economic Data"
    PUBLICATION_SCHEDULE = "Publication Schedule"
    CENTRAL_BANKS = "Central Banks"
    LOGS = "Logs"
    HOLIDAYS = "Holidays"
    MARKET_ANALYSIS = "Market Analysis"


# Stock OpenAPI example messages for known client-error status codes.
DEFAULT_ERROR_MESSAGE_BY_STATUS_CODE: dict[int, str] = {
    400: "Bad Request - The request could not be understood by the server",
    404: "Not Found - The requested resource was not found",
    409: (
        "Conflict - The resource is locked or the operation conflicts "
        "with current state"
    ),
    422: (
        "Unprocessable Entity - The request was well-formed but " "semantically invalid"
    ),
}


class _MessageOpenApiResponse(OpenApiResponse):
    """OpenAPI error response with a single ``message`` example body."""

    def __init__(
        self,
        *,
        status_code: int,
        example_name: str,
        message: str | None = None,
    ):
        """Initialize the OpenApiResponse."""
        resolved_message = (
            message
            or DEFAULT_ERROR_MESSAGE_BY_STATUS_CODE.get(status_code)
            or example_name
        )
        super().__init__(
            response=status_code,
            examples=[
                OpenApiExample(name=example_name, value={"message": resolved_message})
            ],
        )


class BadRequestOpenApiResponse(_MessageOpenApiResponse):
    """400 Bad Request OpenAPI response."""

    def __init__(self, message: str):
        """Initialize the OpenApiResponse with an explicit error message example."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            example_name="Bad Request",
            message=message,
        )


class NotFoundOpenApiResponse(_MessageOpenApiResponse):
    """404 Not Found OpenAPI response."""

    def __init__(self, message: str):
        """Initialize the OpenApiResponse with an explicit error message example."""
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            example_name="Not Found",
            message=message,
        )


class ConflictOpenApiResponse(_MessageOpenApiResponse):
    """409 Conflict OpenAPI response (e.g. Redis lock held)."""

    def __init__(self, message: str):
        """Initialize the OpenApiResponse with an explicit error message example."""
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            example_name="Conflict",
            message=message,
        )


class UnprocessableEntityOpenApiResponse(_MessageOpenApiResponse):
    """422 Unprocessable Entity OpenAPI response."""

    def __init__(self, message: str):
        """Initialize the OpenApiResponse with an explicit error message example."""
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            example_name="Unprocessable Entity",
            message=message,
        )


S = TypeVar("S", bound=serializers.Serializer | serializers.ListSerializer)


class SuccessResponse:
    """Base Success Response class for OpenAPI documentation."""

    def __init__(
        self,
        response_serializer: type[S],
        status_code: int = status.HTTP_200_OK,
    ):
        self.response_serializer = response_serializer
        self.status_code = status_code


class DefaultOpenApiResponseSerializer(serializers.Serializer):
    """Default OpenApi Response Serializer."""

    message = serializers.CharField()


class OkOpenApiResponse(SuccessResponse):
    """200 OK Response."""

    def __init__(self, response_serializer: type[S] | None = None):
        super().__init__(
            response_serializer=response_serializer or DefaultOpenApiResponseSerializer,
            status_code=status.HTTP_200_OK,
        )


class CreatedOpenApiResponse(SuccessResponse):
    """201 Created Response."""

    def __init__(self, response_serializer: type[S] | None = None):
        super().__init__(
            response_serializer=response_serializer or DefaultOpenApiResponseSerializer,
            status_code=status.HTTP_201_CREATED,
        )


def _build_parameters_for_get_requests(
    request_serializer: type[serializers.Serializer | serializers.ListSerializer],
):
    """Build parameters for GET requests in OpenAPI documentation."""
    parameters = []

    serializer_instance = request_serializer()
    fields = getattr(serializer_instance, "fields", {})
    for field_name, field in fields.items():
        if hasattr(field, "choices") and field.choices:
            parameters.append(
                OpenApiParameter(
                    name=field_name,
                    type=str,
                    location=OpenApiParameter.QUERY,
                    required=field.required,
                    enum=list(field.choices.keys()),
                    description=f"Filter by {field_name}",
                )
            )
        else:
            field_type = OpenApiTypes.STR
            if hasattr(field, "input_type"):
                if field.input_type == "date":
                    field_type = OpenApiTypes.DATE
                elif field.input_type == "datetime":
                    field_type = OpenApiTypes.DATE
                else:
                    field_type = OpenApiTypes.STR

            parameters.append(
                OpenApiParameter(
                    name=field_name,
                    type=field_type,
                    location=OpenApiParameter.QUERY,
                    required=field.required,
                    description=f"Filter by {field_name}",
                )
            )

    return parameters


def _build_responses(
    response: SuccessResponse | None = None,
    error_responses: list[OpenApiResponse] = [],
):
    """Build responses dictionary for OpenAPI documentation."""
    responses_dict = {}

    if response and hasattr(response, "response_serializer"):
        responses_dict[response.status_code] = response.response_serializer
    else:
        responses_dict[status.HTTP_200_OK] = DefaultOpenApiResponseSerializer()

    if error_responses:
        for error_response in error_responses:
            responses_dict[error_response.response] = error_response

    return responses_dict


def open_api(
    tags: list[ApiTags],
    summary: str,
    description: str,
    request_serializer: (
        type[serializers.Serializer | serializers.ListSerializer] | None
    ) = None,
    response: SuccessResponse | None = None,
    error_responses: list[OpenApiResponse] = [],
):
    """Open API Decorator."""

    def decorator(func):
        """Wrap a view method with OpenAPI schema and request validation."""
        if func.__name__ in {"get", "delete"} and request_serializer:
            parameters = _build_parameters_for_get_requests(request_serializer)
            request = None
        else:
            parameters = []
            request = request_serializer

        @extend_schema(
            tags=[tag.value for tag in tags],
            summary=summary,
            description=description,
            parameters=parameters,
            request=request,
            responses=_build_responses(
                response or None,
                error_responses,
            ),
        )
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            """Validate the request and forward validated data to the view."""
            method = request.method
            if (method == "POST" or method == "PATCH") and request_serializer:
                serializer = request_serializer(data=request.data)
                if not serializer.is_valid():
                    return Response(
                        data={"error_message": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return func(self, serializer.validated_data, *args, **kwargs)
            elif (method == "GET" or method == "DELETE") and request_serializer:
                serializer = request_serializer(data=request.query_params)
                if not serializer.is_valid():
                    return Response(
                        data={"error_message": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return func(self, serializer.validated_data, *args, **kwargs)
            else:
                return func(self, request, *args, **kwargs)

        return wrapper

    return decorator
