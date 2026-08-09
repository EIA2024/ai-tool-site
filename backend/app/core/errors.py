"""Application error types and response envelope helpers.

Tools raise typed errors for expected business failures (validation,
not-found, upstream provider errors). The API layer converts them into a
uniform JSON envelope so clients never see raw exception text.

Expected errors keep HTTP 200 with ``success: false`` (matching the
existing frontend contract); genuine server failures return HTTP 500
with a generic message and a full traceback in server logs only.
"""

from typing import Any


class AppError(Exception):
    """Base class for expected application errors."""

    code: str = "APP_ERROR"
    status_code: int = 200
    message: str = "Application error"

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def to_envelope(self) -> dict[str, Any]:
        return {
            "success": False,
            "error": {"code": self.code, "message": self.message},
        }


class ToolError(AppError):
    """Expected business error raised by a tool."""

    code = "TOOL_ERROR"


class ValidationError(ToolError):
    code = "VALIDATION_ERROR"


class NotFoundError(ToolError):
    code = "NOT_FOUND"


class ProviderError(ToolError):
    """Upstream provider failure (e.g. DeepSeek API error)."""

    code = "PROVIDER_ERROR"


class RateLimitError(AppError):
    code = "RATE_LIMITED"
    status_code = 429
    message = "Too many requests, please slow down"


class InternalError(AppError):
    """Unexpected server failure. The message is intentionally generic."""

    code = "INTERNAL_ERROR"
    status_code = 500
    message = "Internal server error"


def ok(data: dict[str, Any] | list[Any]) -> dict[str, Any]:
    """Build a success envelope from a tool's returned ``data`` payload."""
    return {"success": True, "data": data}
