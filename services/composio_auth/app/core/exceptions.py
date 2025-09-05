"""
Custom exception classes for the application.
Handles specific error scenarios for Composio and other modules.
"""

from fastapi import HTTPException, status


class ComposioError(HTTPException):
    """Base exception for Composio-related errors."""

    def __init__(
        self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        super().__init__(status_code=status_code, detail=detail)


class ToolNotFoundError(ComposioError):
    """Raised when a requested tool is not found."""

    def __init__(self, tool_id: str):
        super().__init__(
            detail=f"Tool '{tool_id}' not found", status_code=status.HTTP_404_NOT_FOUND
        )


class ToolNotConnectedError(ComposioError):
    """Raised when trying to execute a tool that is not connected."""

    def __init__(self, tool_id: str):
        super().__init__(
            detail=f"Tool '{tool_id}' is not connected. Please connect your account first.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ToolExecutionError(ComposioError):
    """Raised when tool execution fails."""

    def __init__(self, tool_id: str = None, error: str = None):
        super().__init__(
            detail=f"Failed to execute tool '{tool_id}': {error}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class NaturalLanguageProcessingError(ComposioError):
    """Raised when natural language processing fails."""

    def __init__(self, error: str):
        super().__init__(
            detail=f"Failed to process natural language: {error}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AccountConnectionError(ComposioError):
    """Raised when account connection fails."""

    def __init__(self, tool_id: str, error: str):
        super().__init__(
            detail=f"Failed to connect account for tool '{tool_id}': {error}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ContentModerationError(ComposioError):
    """Raised when content is flagged by moderation."""

    def __init__(self, hostilities: str):
        super().__init__(
            detail=f"Your query has been flagged as {hostilities}. Please revise your request and try again.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ValidationError(Exception):
    """Custom validation error."""

    pass


class ConfigurationError(Exception):
    """Custom configuration error."""

    pass


class ExternalServiceError(Exception):
    """Custom external service error."""

    pass


class InternalServerError(Exception):
    """Custom internal server error."""

    pass
