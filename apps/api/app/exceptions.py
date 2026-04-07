"""
Structured exception hierarchy for AnalystPro.

Every raised exception carries:
  - A user-friendly message (safe to show in the UI)
  - An HTTP status code
  - A machine-readable error code for the frontend to key off
  - An optional developer detail (logged server-side, never sent to client)

Usage in routes:
    from app.exceptions import NotFoundError, ValidationError, AIServiceError
    raise NotFoundError("Project not found.")
    raise ValidationError("Column 'revenue' must be numeric.")

The global exception handler in main.py converts these into consistent
JSON responses:  { "error": "...", "code": "...", "status": 4xx/5xx }
"""
from __future__ import annotations


class AppError(Exception):
    """Base for all application-level errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        user_message: str,
        *,
        dev_detail: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.dev_detail = dev_detail or user_message
        if error_code:
            self.error_code = error_code


# ── 400-level ─────────────────────────────────────────────────────────────────

class ValidationError(AppError):
    """Invalid input from the client (bad field values, missing params, etc.)."""
    status_code = 422
    error_code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    """Requested resource does not exist."""
    status_code = 404
    error_code = "NOT_FOUND"


class AuthenticationError(AppError):
    """Token missing, expired, or invalid."""
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    """Token is valid but the user does not have permission."""
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"


class ConflictError(AppError):
    """Resource already exists or state conflict."""
    status_code = 409
    error_code = "CONFLICT_ERROR"


class FileTooLargeError(AppError):
    """Uploaded file exceeds the size limit."""
    status_code = 413
    error_code = "FILE_TOO_LARGE"


class UnsupportedFileTypeError(AppError):
    """File extension not in the allow-list."""
    status_code = 415
    error_code = "UNSUPPORTED_FILE_TYPE"


class RateLimitError(AppError):
    """Client exceeded request rate limits."""
    status_code = 429
    error_code = "RATE_LIMIT_ERROR"


# ── 500-level ─────────────────────────────────────────────────────────────────

class DatabaseError(AppError):
    """Database operation failed."""
    status_code = 503
    error_code = "DATABASE_ERROR"


class FileStorageError(AppError):
    """Disk / object-storage operation failed."""
    status_code = 503
    error_code = "FILE_STORAGE_ERROR"


class AIServiceError(AppError):
    """Anthropic / OpenAI / external AI provider error."""
    status_code = 503
    error_code = "AI_SERVICE_ERROR"


class DatasetError(AppError):
    """Dataset is empty, corrupt, or cannot be parsed."""
    status_code = 422
    error_code = "DATASET_ERROR"


class AnalysisError(AppError):
    """Analysis pipeline encountered an unexpected error."""
    status_code = 500
    error_code = "ANALYSIS_ERROR"


class QueryError(AppError):
    """SQL query execution failed."""
    status_code = 422
    error_code = "QUERY_ERROR"


class TimeoutError(AppError):  # noqa: A001 (shadows built-in intentionally)
    """Operation exceeded its time limit."""
    status_code = 504
    error_code = "TIMEOUT_ERROR"
