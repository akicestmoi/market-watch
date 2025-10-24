from typing import Any, Dict, Optional

from django.http import Http404
from pydantic import BaseModel
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.utils import logger


class BaseErrorResponseModel(BaseModel):
    """Base Error Response Model."""

    error: str
    message: str
    status_code: int
    detail: Optional[Dict[str, Any]] = None

    @classmethod
    def create_error_response(
        cls,
        error_type: str,
        message: str,
        status_code: int,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a standardized error response dictionary."""
        return cls(
            error=error_type, message=message, status_code=status_code, detail=detail
        ).model_dump()


class BaseAPIView(APIView):
    """Base API View."""

    def handle_exception(self, exc):
        """
        Handle any exception that occurs in the view.
        Always returns a JSON response instead of HTML.
        """
        return self._handle_exception(exc)

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add request logging and error handling."""
        try:
            response = super().dispatch(request, *args, **kwargs)
            return response
        except Exception as exc:
            logger.error(
                f"Exception in {self.__class__.__name__}: {str(exc)}",
                exc_info=True,
                extra={
                    "request_path": request.path,
                    "request_method": request.method,
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                },
            )
            return self.handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> Response:
        """Handle all exceptions."""
        if isinstance(exc, Http404):
            error_type = "Not Found"
            message = str(exc) if str(exc) else "The requested resource was not found."
            status_code = status.HTTP_404_NOT_FOUND
            detail = None
        elif isinstance(exc, APIException):
            error_type = exc.__class__.__name__.replace("Exception", "").replace(
                "Error", ""
            )
            message = str(exc.detail) if hasattr(exc, "detail") else str(exc)
            status_code = exc.status_code
            detail = exc.detail if isinstance(exc, ValidationError) else None
        elif isinstance(exc, (TypeError, ValueError, KeyError, AttributeError)):
            error_type = exc.__class__.__name__.replace("Error", "")
            message = "Invalid request data. Please check your input."
            status_code = status.HTTP_400_BAD_REQUEST
            detail = {"exception": str(exc)}
        else:
            error_type = "Internal Server Error"
            message = "An unexpected error occurred. Please try again later."
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            detail = {"exception": str(exc)} if hasattr(exc, "__dict__") else None

        # Create and return standardized error response
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

        # Force JSON content type for API responses
        if hasattr(response, "data") and not response.get(
            "Content-Type", ""
        ).startswith("application/json"):
            response["Content-Type"] = "application/json"

        return response
