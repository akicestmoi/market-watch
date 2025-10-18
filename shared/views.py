from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAcceptable,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.utils import logger


class BaseAPIView(APIView):
    """Base API View with comprehensive error handling."""

    def handle_exception(self, exc):
        """
        Handle any exception that occurs in the view.
        Always returns a JSON response instead of HTML.
        """
        if isinstance(exc, Http404):
            return self._handle_not_found(exc)
        elif isinstance(exc, APIException):
            return self._handle_api_exception(exc)
        else:
            return self._handle_generic_exception(exc)

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add request logging and error handling."""
        try:
            response = super().dispatch(request, *args, **kwargs)
            return response
        except Exception as exc:
            # Log the exception for debugging
            logger.error(
                f"Exception in {self.__class__.__name__}: {str(exc)}",
                exc_info=True,
                extra={
                    "request_path": request.path,
                    "request_method": request.method,
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                },
            )
            # Let the handle_exception method deal with it
            return self.handle_exception(exc)

    def _handle_not_found(self, exc: Http404) -> Response:
        """Handle 404 Not Found errors."""
        return Response(
            {
                "error": "Not Found",
                "message": (
                    str(exc) if str(exc) else "The requested resource was not found."
                ),
                "status_code": status.HTTP_404_NOT_FOUND,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    def _handle_api_exception(self, exc: APIException) -> Response:
        """Handle DRF API exceptions."""
        error_data = {
            "error": exc.__class__.__name__,
            "message": str(exc.detail) if hasattr(exc, "detail") else str(exc),
            "status_code": exc.status_code,
        }

        # Add additional context for specific exception types
        if isinstance(exc, ValidationError):
            error_data["error"] = "Validation Error"
            error_data["details"] = exc.detail
        elif isinstance(exc, AuthenticationFailed):
            error_data["error"] = "Authentication Failed"
        elif isinstance(exc, PermissionDenied):
            error_data["error"] = "Permission Denied"
        elif isinstance(exc, ParseError):
            error_data["error"] = "Parse Error"
            error_data["message"] = "Invalid JSON in request body"
        elif isinstance(exc, MethodNotAllowed):
            error_data["error"] = "Method Not Allowed"
        elif isinstance(exc, NotAcceptable):
            error_data["error"] = "Not Acceptable"
        elif isinstance(exc, UnsupportedMediaType):
            error_data["error"] = "Unsupported Media Type"
        elif isinstance(exc, Throttled):
            error_data["error"] = "Request Throttled"

        return Response(error_data, status=exc.status_code)

    def _handle_generic_exception(self, exc: Exception) -> Response:
        """Handle unexpected exceptions."""
        logger.error(
            f"Unexpected error in {self.__class__.__name__}: {str(exc)}", exc_info=True
        )

        return Response(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "detail": str(exc) if hasattr(exc, "__dict__") else None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        """Ensure all responses are JSON format."""
        response = super().finalize_response(request, response, *args, **kwargs)

        # Force JSON content type for API responses
        if hasattr(response, "data") and not response.get(
            "Content-Type", ""
        ).startswith("application/json"):
            response["Content-Type"] = "application/json"

        return response
