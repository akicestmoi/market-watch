"""Base API view classes shared by domain endpoints."""

from typing import NotRequired, TypedDict

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services import logger


class _FieldValidationError(TypedDict):
    """One field-level validation error (field name + message)."""

    field: str
    message: str


class _ErrorResponseDetail(TypedDict, total=False):
    """Optional structured error detail."""

    exception: str
    field_errors: list[_FieldValidationError]


class _ErrorResponseBody(TypedDict):
    """Standardized API error response body."""

    error: str
    message: str
    status_code: int
    detail: NotRequired[_ErrorResponseDetail | None]


class BaseErrorResponseModel:
    """Factory for standardized error response dictionaries."""

    @classmethod
    def create_error_response(
        cls,
        error_type: str,
        message: str,
        status_code: int,
        detail: _ErrorResponseDetail | None = None,
    ) -> _ErrorResponseBody:
        """Create a standardized error response dictionary."""
        body: _ErrorResponseBody = {
            "error": error_type,
            "message": message,
            "status_code": status_code,
        }
        if detail is not None:
            body["detail"] = detail
        return body


class BaseAPIView(APIView):
    """Base API View."""

    def handle_exception(self, exc: Exception) -> Response:
        """
        Handle any exception that occurs in the view.
        Always returns a JSON response instead of HTML.
        """
        detail: _ErrorResponseDetail | None = None
        if isinstance(exc, Http404):
            error_type = "Not Found"
            message = str(exc) if str(exc) else "The requested resource was not found."
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, APIException):
            error_type = exc.__class__.__name__.replace("Exception", "").replace(
                "Error", ""
            )
            status_code = exc.status_code
            # Field-level ValidationError uses a dict; a bare string becomes a list.
            if isinstance(exc, ValidationError) and isinstance(exc.detail, dict):
                field_errors: list[_FieldValidationError] = []
                for field, value in exc.detail.items():
                    if isinstance(value, list):
                        field_message = "; ".join(str(item) for item in value)
                    else:
                        field_message = str(value)
                    field_errors.append(
                        _FieldValidationError(field=str(field), message=field_message)
                    )
                message = "; ".join(
                    f"{error['field']}: {error['message']}" for error in field_errors
                )
                detail = _ErrorResponseDetail(field_errors=field_errors)
            elif isinstance(exc, ValidationError) and isinstance(exc.detail, list):
                message = "; ".join(str(item) for item in exc.detail)
            else:
                message = str(exc.detail) if hasattr(exc, "detail") else str(exc)
        elif isinstance(exc, (TypeError, ValueError, KeyError, AttributeError)):
            error_type = exc.__class__.__name__.replace("Error", "")
            message = "Invalid request data. Please check your input."
            status_code = status.HTTP_400_BAD_REQUEST
            detail = _ErrorResponseDetail(exception=str(exc))
        else:
            error_type = "Internal Server Error"
            message = "An unexpected error occurred. Please try again later."
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if hasattr(exc, "__dict__"):
                detail = _ErrorResponseDetail(exception=str(exc))

        logger.error(
            f"{error_type}: {exc}",
            exc_info=True,
            extra={"path": self.request.path, "method": self.request.method},
        )

        error_data = BaseErrorResponseModel.create_error_response(
            error_type=error_type,
            message=message,
            status_code=status_code,
            detail=detail,
        )
        return Response(error_data, status=status_code)

    def finalize_response(self, request, response, *args, **kwargs):
        """Ensure all responses are JSON format."""
        response = super().finalize_response(request, response, *args, **kwargs)
        if hasattr(response, "data") and not response.get(
            "Content-Type", ""
        ).startswith("application/json"):
            response["Content-Type"] = "application/json"

        return response
