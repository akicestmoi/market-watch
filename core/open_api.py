import functools
from enum import Enum
from typing import List, Optional, Type, TypeVar, Union

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
    PRICE_LOGS = "Price Logs"
    ECONOMIC_INDICATOR_INFORMATION = "Economic Indicator Information"
    ECONOMIC_DATA = "Economic Data"
    PUBLICATION_SCHEDULE = "Publication Schedule"


DEFAULT_ERROR_MESSAGES = {
    400: "Bad Request - The request could not be understood by the server",
    401: "Unauthorized - Authentication is required",
    403: "Forbidden - Access to this resource is denied",
    404: "Not Found - The requested resource was not found",
    405: "Method Not Allowed - The HTTP method is not supported",
}


class BadRequestOpenApiResponse(OpenApiResponse):
    """Bad Request OpenApi Response for OpenAPI documentation."""

    def __init__(
        self,
        message: Optional[str] = None,
    ):
        """Initialize the OpenApiResponse."""
        message = message or DEFAULT_ERROR_MESSAGES.get(status.HTTP_400_BAD_REQUEST)
        super().__init__(
            response=status.HTTP_400_BAD_REQUEST,
            examples=[OpenApiExample(name="Bad Request", value={"message": message})],
        )


class UnauthorizedOpenApiResponse(OpenApiResponse):
    """Unauthorized OpenApi Response for OpenAPI documentation."""

    def __init__(
        self,
        message: Optional[str] = None,
    ):
        """Initialize the OpenApiResponse."""
        message = message or DEFAULT_ERROR_MESSAGES.get(status.HTTP_401_UNAUTHORIZED)
        super().__init__(
            response=status.HTTP_401_UNAUTHORIZED,
            examples=[OpenApiExample(name="Unauthorized", value={"message": message})],
        )


class ForbiddenOpenApiResponse(OpenApiResponse):
    """Forbidden OpenApi Response for OpenAPI documentation."""

    def __init__(
        self,
        message: Optional[str] = None,
    ):
        """Initialize the OpenApiResponse."""
        message = message or DEFAULT_ERROR_MESSAGES.get(status.HTTP_403_FORBIDDEN)
        super().__init__(
            response=status.HTTP_403_FORBIDDEN,
            examples=[OpenApiExample(name="Forbidden", value={"message": message})],
        )


class NotFoundOpenApiResponse(OpenApiResponse):
    """NotFound OpenApi Response for OpenAPI documentation."""

    def __init__(
        self,
        message: Optional[str] = None,
    ):
        """Initialize the OpenApiResponse."""
        message = message or DEFAULT_ERROR_MESSAGES.get(status.HTTP_404_NOT_FOUND)
        super().__init__(
            response=status.HTTP_404_NOT_FOUND,
            examples=[OpenApiExample(name="NotFound", value={"message": message})],
        )


class MethodNotAllowedOpenApiResponse(OpenApiResponse):
    """MethodNotAllowed OpenApi Response for OpenAPI documentation."""

    def __init__(
        self,
        message: Optional[str] = None,
    ):
        """Initialize the OpenApiResponse."""
        message = message or DEFAULT_ERROR_MESSAGES.get(
            status.HTTP_405_METHOD_NOT_ALLOWED
        )
        super().__init__(
            response=status.HTTP_405_METHOD_NOT_ALLOWED,
            examples=[
                OpenApiExample(name="MethodNotAllowed", value={"message": message})
            ],
        )


S = TypeVar("S", bound=Union[serializers.Serializer, serializers.ListSerializer])


class SuccessResponse:
    """Base Success Response class for OpenAPI documentation."""

    def __init__(
        self,
        response_serializer: Type[S],
        status_code: int = status.HTTP_200_OK,
    ):
        self.response_serializer = response_serializer
        self.status_code = status_code

    def to_dict(self) -> dict:
        """Convert to dictionary for OpenAPI documentation."""
        return {
            "response_serializer": self.response_serializer,
            "status_code": self.status_code,
        }


class DefaultOpenApiResponseSerializer(serializers.Serializer):
    """Default OpenApi Response Serializer."""

    message = serializers.CharField()


class OkOpenApiResponse(SuccessResponse):
    """200 OK Response."""

    def __init__(self, response_serializer: Type[S]):
        super().__init__(response_serializer, status.HTTP_200_OK)


class CreatedOpenApiResponse(SuccessResponse):
    """201 Created Response."""

    def __init__(self, response_serializer: Type[S]):
        super().__init__(response_serializer, status.HTTP_201_CREATED)


class AcceptedOpenApiResponse(SuccessResponse):
    """202 Accepted Response."""

    def __init__(self, response_serializer: Type[S]):
        super().__init__(response_serializer, status.HTTP_202_ACCEPTED)


class NoContentOpenApiResponse(SuccessResponse):
    """204 No Content Response."""

    def __init__(self, response_serializer: Type[S]):
        super().__init__(response_serializer, status.HTTP_204_NO_CONTENT)


def _build_parameters_for_get_requests(
    request_serializer: Type[Union[serializers.Serializer, serializers.ListSerializer]],
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
    response: Optional[SuccessResponse] = None,
    error_responses: List[OpenApiResponse] = [],
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
    tags: List[ApiTags],
    summary: str,
    description: str,
    request_serializer: Optional[
        Type[Union[serializers.Serializer, serializers.ListSerializer]]
    ] = None,
    response: Optional[SuccessResponse] = None,
    error_responses: List[OpenApiResponse] = [],
):
    """Open API Decorator."""

    def decorator(func):
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
