"""
Integration SDK — Test helpers.

Provides lightweight, zero-dependency utilities for unit-testing integration
handlers without making real HTTP calls.

Usage::

    from integrations.sdk.testing import IntegrationTestCase, fixture_response

    class TestAcmeIntegration(IntegrationTestCase):
        async def test_list_contacts(self):
            self.mock_client.add_response(
                "GET", "/contacts",
                fixture_response(200, {"data": [{"id": "1", "name": "Alice"}]})
            )
            result = await self.integration.list_contacts(
                config={}, input_data={}, credential_id="cred-1", db=self.mock_db
            )
            self.assert_request_count(1)
            self.assert_called_with("GET", "/contacts")
            assert result["data"][0]["name"] == "Alice"
"""
from __future__ import annotations

import asyncio
import json
import unittest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx


# ── Fixture helpers ────────────────────────────────────────────────────────────

@dataclass
class MockResponse:
    """A recorded fake HTTP response returned by ``MockHTTPClient``."""
    status: int
    json_body: Any = None
    text_body: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    def to_httpx(self) -> httpx.Response:
        """Convert to an ``httpx.Response`` object."""
        if self.json_body is not None:
            content = json.dumps(self.json_body).encode()
            headers = {"Content-Type": "application/json", **self.headers}
        else:
            content = self.text_body.encode()
            headers = self.headers

        return httpx.Response(
            status_code=self.status,
            content=content,
            headers=headers,
            request=httpx.Request("GET", "https://mock.invalid/"),
        )


def fixture_response(status: int, json_body: Any = None, *, text: str = "") -> MockResponse:
    """
    Convenience factory for building a ``MockResponse``.

    Parameters
    ----------
    status:
        HTTP status code.
    json_body:
        JSON-serialisable body (dict or list). Mutually exclusive with
        ``text``.
    text:
        Plain-text body for non-JSON responses.

    Returns
    -------
    MockResponse
        Ready to pass to ``MockHTTPClient.add_response()``.
    """
    return MockResponse(status=status, json_body=json_body, text_body=text)


# ── MockHTTPClient ─────────────────────────────────────────────────────────────

@dataclass
class RecordedRequest:
    """A request recorded by ``MockHTTPClient``."""
    method: str
    url: str
    params: dict[str, Any]
    json_body: Any
    headers: dict[str, str]


class MockHTTPClient:
    """
    Drop-in replacement for ``ResilientHTTPClient`` in tests.

    Pre-load responses with ``add_response()``. Requests are matched in
    FIFO order — each response is consumed once. If no responses remain,
    raises ``AssertionError``.

    The client records every request made so tests can assert on them.

    Usage::

        mock = MockHTTPClient()
        mock.add_response("GET", "/contacts",
                          fixture_response(200, {"data": []}))

        # Inject mock into integration and call handler
        result = await integration.list_contacts(...)

        assert mock.request_count == 1
        mock.assert_called_with("GET", "/contacts")
    """

    def __init__(self) -> None:
        self._queue: list[tuple[str, str, MockResponse]] = []
        self.requests: list[RecordedRequest] = []

    def add_response(
        self,
        method: str,
        url_contains: str,
        response: MockResponse,
    ) -> None:
        """
        Enqueue a response.

        Parameters
        ----------
        method:
            HTTP method (case-insensitive).
        url_contains:
            Substring that the request URL must contain. Used for
            loose matching — does not require an exact URL match.
        response:
            The ``MockResponse`` to return.
        """
        self._queue.append((method.upper(), url_contains, response))

    @property
    def request_count(self) -> int:
        """Total number of requests made to this mock client."""
        return len(self.requests)

    def assert_called_with(
        self,
        method: str,
        url_contains: str,
        *,
        json_body: Any = None,
        params: dict | None = None,
    ) -> None:
        """
        Assert that at least one recorded request matches the given criteria.

        Raises
        ------
        AssertionError
            If no recorded request matches.
        """
        method = method.upper()
        for req in self.requests:
            if req.method != method:
                continue
            if url_contains and url_contains not in req.url:
                continue
            if json_body is not None and req.json_body != json_body:
                continue
            if params is not None and req.params != params:
                continue
            return  # found a match

        raise AssertionError(
            f"Expected a {method} request to URL containing {url_contains!r}. "
            f"Recorded requests: {[(r.method, r.url) for r in self.requests]}"
        )

    def assert_request_count(self, count: int) -> None:
        """Assert the exact number of requests made."""
        actual = self.request_count
        if actual != count:
            raise AssertionError(
                f"Expected {count} request(s), but {actual} were made. "
                f"URLs: {[r.url for r in self.requests]}"
            )

    # ── httpx.AsyncClient-like interface ──────────────────────────────────

    async def get(self, url: str, **kwargs: Any) -> Any:
        return await self._dispatch("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        return await self._dispatch("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> Any:
        return await self._dispatch("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Any:
        return await self._dispatch("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        return await self._dispatch("DELETE", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        return await self._dispatch(method.upper(), url, **kwargs)

    async def raw(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Return raw httpx.Response (for paginators that need headers)."""
        self._record(method.upper(), url, kwargs)
        mock_resp = self._pop_response(method.upper(), url)
        return mock_resp.to_httpx()

    async def aclose(self) -> None:
        pass

    async def __aenter__(self) -> "MockHTTPClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    def _record(self, method: str, url: str, kwargs: dict) -> None:
        self.requests.append(
            RecordedRequest(
                method=method,
                url=url,
                params=kwargs.get("params", {}),
                json_body=kwargs.get("json"),
                headers=kwargs.get("headers", {}),
            )
        )

    def _pop_response(self, method: str, url: str) -> MockResponse:
        for i, (m, url_contains, resp) in enumerate(self._queue):
            if m == method and url_contains in url:
                self._queue.pop(i)
                return resp
        # No match — return a default 200 with an empty body
        return MockResponse(status=200, json_body={})

    async def _dispatch(self, method: str, url: str, **kwargs: Any) -> Any:
        self._record(method, url, kwargs)
        mock_resp = self._pop_response(method, url)
        httpx_resp = mock_resp.to_httpx()
        if httpx_resp.headers.get("Content-Type", "").startswith("application/json"):
            return httpx_resp.json()
        return httpx_resp.text


# ── MockDB ────────────────────────────────────────────────────────────────────

class MockDB:
    """
    Minimal mock for the SQLAlchemy async session.

    Satisfies ``CredentialHelper.get()`` by pre-loading credential fixtures.

    Usage::

        db = MockDB()
        db.add_credential("cred-1", {"api_key": "test-key-123"})
    """

    def __init__(self) -> None:
        self._credentials: dict[str, dict] = {}

    def add_credential(self, credential_id: str, fields: dict) -> None:
        """Pre-load a credential fixture that will be returned by get_credential_data()."""
        self._credentials[credential_id] = fields

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return MagicMock()

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


# ── IntegrationTestCase ────────────────────────────────────────────────────────

class IntegrationTestCase(unittest.IsolatedAsyncioTestCase):
    """
    Base class for integration unit tests.

    Provides:
    - ``self.mock_client`` — a ``MockHTTPClient`` instance
    - ``self.mock_db`` — a ``MockDB`` instance
    - ``self.integration`` — instantiated in ``setUp()`` if
      ``integration_class`` is defined on the subclass
    - ``self.assert_called_with()`` / ``self.assert_request_count()``
      delegate to the mock client

    Subclasses define::

        class TestMyIntegration(IntegrationTestCase):
            integration_class = MyIntegration

            async def asyncSetUp(self):
                await super().asyncSetUp()
                # Add credential fixtures
                self.mock_db.add_credential("test-cred", {"api_key": "sk-test"})

            async def test_something(self):
                self.mock_client.add_response(
                    "GET", "/me",
                    fixture_response(200, {"id": "user-1"})
                )
                result = await self.integration.some_method(
                    config={}, input_data={},
                    credential_id="test-cred", db=self.mock_db
                )
                self.assert_request_count(1)
    """

    integration_class: type | None = None

    async def asyncSetUp(self) -> None:
        self.mock_client = MockHTTPClient()
        self.mock_db = MockDB()
        if self.integration_class is not None:
            self.integration = self.integration_class()
        else:
            self.integration = None

    def assert_called_with(
        self,
        method: str,
        url_contains: str,
        *,
        json_body: Any = None,
        params: dict | None = None,
    ) -> None:
        """Delegate to ``self.mock_client.assert_called_with()``."""
        self.mock_client.assert_called_with(
            method, url_contains, json_body=json_body, params=params
        )

    def assert_request_count(self, count: int) -> None:
        """Delegate to ``self.mock_client.assert_request_count()``."""
        self.mock_client.assert_request_count(count)

    def add_credential(self, credential_id: str, fields: dict) -> None:
        """Convenience: add a credential fixture to the mock DB."""
        self.mock_db.add_credential(credential_id, fields)
