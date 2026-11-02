"""Exceptions for the Wise SDK and MCP server."""

from __future__ import annotations

from typing import Any


class WiseError(Exception):
    """Base exception for all Wise SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class AuthenticationError(WiseError):
    """Raised when authentication fails (HTTP 401)."""


class SCARequiredError(WiseError):
    """Raised when Strong Customer Authentication (2FA) is required and cannot be satisfied."""

    def __init__(
        self,
        message: str,
        *,
        one_time_token: str | None = None,
        approval_result: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(
            message,
            code="SCA_REQUIRED",
            status_code=403,
            details=details,
        )
        self.one_time_token = one_time_token
        self.approval_result = approval_result


class ForbiddenError(WiseError):
    """Raised when access is forbidden (HTTP 403) and not resolvable by SCA."""


class NotFoundError(WiseError):
    """Raised when a requested resource is not found (HTTP 404)."""


class ValidationError(WiseError):
    """Raised when input parameters fail API validation (HTTP 400 or 422)."""


class RateLimitError(WiseError):
    """Raised when API rate limits are exceeded (HTTP 429)."""


class PaymentError(WiseError):
    """Raised when a payout or funding operation fails."""


class HostSecurityError(WiseError):
    """Raised when an untrusted or non-whitelisted API host is specified."""
