"""
Integration SDK — ResilientHTTPClient.

Wraps httpx.AsyncClient with:
  - Automatic retries with exponential backoff (tenacity)
  - Rate-limit handling (429 + Retry-After header)
  - Per-request timeout enforcement
  - SSRF protection via core.ssrf_guard
  - Structured request/response logging (structlog)
  - Error normalization → raises typed IntegrationError subclasses
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    RetryError,
)

from core.ssrf_guard import assert_safe_url, SSRFSafeTransport
from integrations.sdk.errors import (
    IntegrationError,
    RateLimitError,
    ServerError,
    _classify_error,
)

log = structlog.get_logger(__name__)

# Default retry / timeout configuration — may be overridden per-client.
_DEFAULT_TIMEOUT = 30.0       # seconds
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_WAIT_MIN = 1.0       # seconds — tenacity exponential backoff floor
_DEFAULT_WAIT_MAX = 60.0      # seconds — tenacity exponential backoff ceiling


class ResilientHTTPClient:
    """
    Production-grade HTTP client for integration handlers.

    Intended to be used as an async context manager so the underlying
    ``httpx.AsyncClient`` is properly closed:

        async with ResilientHTTPClient(provider="stripe", base_url=...) as client:
            data = await client.get("/v1/customers")

    Parameters
    ----------
    provider:
        Human-readable provider name used in error messages and log
        fields (e.g. ``"stripe"``, ``"github"``).
    base_url:
        Base URL prepended to every relative path.
    headers:
        Default headers merged into every request.
    auth:
        An ``httpx.Auth`` instance (e.g. ``BearerAuth``, ``ApiKeyAuth``).
    timeout:
        Per-request timeout in seconds. Default 30 s.
    max_retries:
        Maximum number of retry attempts on retryable errors. Default 3.
    wait_min / wait_max:
        Exponential backoff range in seconds. Defaults 1–60 s.
    verify_ssl:
        Whether to verify TLS certificates. Defaults True.
    """

    def __init__(
        self,
        *,
        provider: str = "",
        base_url: str = "",
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        wait_min: float = _DEFAULT_WAIT_MIN,
        wait_max: float = _DEFAULT_WAIT_MAX,
        verify_ssl: bool = True,
    ) -> None:
        self.provider = provider
        self.base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._wait_min = wait_min
        self._wait_max = wait_max

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers or {},
            auth=auth,
            timeout=httpx.Timeout(timeout),
            transport=SSRFSafeTransport(verify=verify_ssl),
            follow_redirects=True,
        )

    # ── Context manager ────────────────────────────────────────────────────

    async def __aenter__(self) -> "ResilientHTTPClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── Public HTTP verbs ──────────────────────────────────────────────────

    async def get(self, url: str, **kwargs: Any) -> dict | list | Any:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> dict | list | Any:
        return await self._request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> dict | list | Any:
        return await self._request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> dict | list | Any:
        return await self._request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> dict | list | Any:
        return await self._request("DELETE", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> dict | list | Any:
        """Low-level method for any HTTP verb."""
        return await self._request(method.upper(), url, **kwargs)

    # ── Raw response (for callers that need headers/status) ───────────────

    async def raw(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """
        Like ``request()`` but returns the raw ``httpx.Response`` rather
        than the parsed JSON body. Useful when the caller needs access to
        response headers (e.g. pagination ``Link`` headers).
        """
        return await self._request_raw(method.upper(), url, **kwargs)

    # ── Internal implementation ────────────────────────────────────────────

    def _build_full_url(self, url: str) -> str:
        """
        Construct the full URL so SSRF checks can resolve hostnames even
        for relative paths. When base_url is set on the httpx client,
        relative paths are resolved internally — we just need the
        absolute form for assert_safe_url.
        """
        if url.startswith(("http://", "https://")):
            return url
        base = self.base_url.rstrip("/")
        path = url.lstrip("/")
        return f"{base}/{path}" if base else url

    async def _request_raw(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Perform the HTTP request with retries; return raw response."""
        full_url = self._build_full_url(url)

        # SSRF guard — raises ValueError for private/loopback/metadata IPs
        try:
            assert_safe_url(full_url)
        except ValueError as exc:
            raise IntegrationError(
                str(exc),
                provider=self.provider,
                retryable=False,
            ) from exc

        logger = log.bind(provider=self.provider, method=method, url=url)

        last_exc: Exception | None = None

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(ServerError),
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(
                    multiplier=1, min=self._wait_min, max=self._wait_max
                ),
                reraise=True,
            ):
                with attempt:
                    t0 = time.monotonic()
                    try:
                        response = await self._client.request(method, url, **kwargs)
                    except httpx.TimeoutException as exc:
                        logger.warning("request_timeout", error=str(exc))
                        raise IntegrationError(
                            f"Request timed out after {self._timeout}s",
                            provider=self.provider,
                            retryable=True,
                        ) from exc
                    except httpx.TransportError as exc:
                        logger.warning("request_transport_error", error=str(exc))
                        raise IntegrationError(
                            f"Transport error: {exc}",
                            provider=self.provider,
                            retryable=True,
                        ) from exc

                    duration_ms = int((time.monotonic() - t0) * 1000)
                    logger.info(
                        "http_response",
                        status=response.status_code,
                        duration_ms=duration_ms,
                    )

                    if response.is_success:
                        return response

                    # Handle rate limit — honour Retry-After before re-raising
                    if response.status_code == 429:
                        retry_after = _parse_retry_after(response)
                        if retry_after and retry_after > 0:
                            logger.warning("rate_limited", retry_after=retry_after)
                            await asyncio.sleep(retry_after)
                        raise RateLimitError(
                            _response_message(response),
                            provider=self.provider,
                            retry_after=retry_after,
                            raw_response=_safe_response_body(response),
                        )

                    # Raise typed error; ServerError will be retried by tenacity
                    exc = _classify_error(
                        provider=self.provider,
                        status_code=response.status_code,
                        message=_response_message(response),
                        raw_response=_safe_response_body(response),
                    )
                    logger.error(
                        "http_error",
                        status=response.status_code,
                        error=str(exc),
                    )
                    raise exc

        except RetryError as retry_exc:
            # tenacity exhausted all attempts; re-raise the last real error
            cause = retry_exc.__cause__
            if isinstance(cause, IntegrationError):
                raise cause
            raise IntegrationError(
                f"Request failed after {self._max_retries} attempts",
                provider=self.provider,
                retryable=False,
            ) from retry_exc

        # Should be unreachable, but appease type-checkers
        raise IntegrationError(
            "Unexpected error in ResilientHTTPClient",
            provider=self.provider,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform request and return parsed JSON body (or raw text)."""
        response = await self._request_raw(method, url, **kwargs)
        return _parse_response(response)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse the Retry-After header as seconds (float) or None."""
    value = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        # Could be an HTTP-date — fall back to a safe default
        return 60.0


def _response_message(response: httpx.Response) -> str:
    """Extract a human-readable error message from a response."""
    try:
        body = response.json()
        if isinstance(body, dict):
            # Common error message field names across providers
            for field in ("message", "error", "detail", "error_description", "msg"):
                if field in body:
                    val = body[field]
                    if isinstance(val, str):
                        return val
                    if isinstance(val, dict):
                        return str(val)
            return str(body)
        return str(body)
    except Exception:
        return response.text[:500] or f"HTTP {response.status_code}"


def _safe_response_body(response: httpx.Response) -> Any:
    """Return parsed JSON body or raw text; never raises."""
    try:
        return response.json()
    except Exception:
        return response.text[:2000]


def _parse_response(response: httpx.Response) -> Any:
    """
    Attempt JSON decode; fall back to text for non-JSON responses
    (e.g. plain-text health checks, CSV exports).
    """
    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type or not content_type:
        try:
            return response.json()
        except Exception:
            pass
    return response.text
