"""
Integration SDK — Error types.

All integration errors ultimately surface as one of these typed exceptions.
The `retryable` flag tells the execution engine whether a retry makes sense.
"""
from __future__ import annotations

from typing import Any


class IntegrationError(Exception):
    """Base class for all integration errors."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int | None = None,
        retryable: bool = False,
        raw_response: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable
        self.raw_response = raw_response

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"provider={self.provider!r}, "
            f"status_code={self.status_code}, "
            f"message={self.message!r}, "
            f"retryable={self.retryable})"
        )

    def to_dict(self) -> dict:
        return {
            "error_type": self.__class__.__name__,
            "provider": self.provider,
            "status_code": self.status_code,
            "message": self.message,
            "retryable": self.retryable,
        }


class AuthenticationError(IntegrationError):
    """
    Raised on HTTP 401 / 403 responses.

    Never retryable — if the credential is wrong, retrying the same
    request will just produce the same 401/403.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int = 401,
        raw_response: Any = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            status_code=status_code,
            retryable=False,
            raw_response=raw_response,
        )


class RateLimitError(IntegrationError):
    """
    Raised on HTTP 429 responses.

    Always retryable. `retry_after` is the number of seconds to wait
    (parsed from the Retry-After header, or None if not provided).
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int = 429,
        retry_after: float | None = None,
        raw_response: Any = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            status_code=status_code,
            retryable=True,
            raw_response=raw_response,
        )
        self.retry_after = retry_after

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["retry_after"] = self.retry_after
        return d


class NotFoundError(IntegrationError):
    """Raised on HTTP 404 responses. Not retryable."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        raw_response: Any = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            status_code=404,
            retryable=False,
            raw_response=raw_response,
        )


class ValidationError(IntegrationError):
    """Raised on HTTP 400 / 422 responses. Not retryable."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int = 400,
        raw_response: Any = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            status_code=status_code,
            retryable=False,
            raw_response=raw_response,
        )


class ServerError(IntegrationError):
    """
    Raised on HTTP 5xx responses.

    Retryable — transient server-side failures often resolve on retry.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int = 500,
        raw_response: Any = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            status_code=status_code,
            retryable=True,
            raw_response=raw_response,
        )


def _classify_error(
    provider: str,
    status_code: int,
    message: str,
    raw_response: Any = None,
    retry_after: float | None = None,
) -> IntegrationError:
    """
    Map an HTTP status code to the appropriate IntegrationError subclass.

    Called by ResilientHTTPClient after every non-2xx response.
    """
    if status_code in (401, 403):
        return AuthenticationError(
            message, provider=provider, status_code=status_code, raw_response=raw_response
        )
    if status_code == 404:
        return NotFoundError(message, provider=provider, raw_response=raw_response)
    if status_code in (400, 422):
        return ValidationError(
            message, provider=provider, status_code=status_code, raw_response=raw_response
        )
    if status_code == 429:
        return RateLimitError(
            message,
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
            raw_response=raw_response,
        )
    if status_code >= 500:
        return ServerError(
            message, provider=provider, status_code=status_code, raw_response=raw_response
        )
    # Fallback for unexpected codes
    return IntegrationError(
        message,
        provider=provider,
        status_code=status_code,
        retryable=False,
        raw_response=raw_response,
    )
