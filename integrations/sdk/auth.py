"""
Integration SDK — Auth helpers.

Each class is a callable that accepts an `httpx.Request` and returns a
modified copy with the appropriate credentials attached. They are designed
to be passed directly to `httpx.AsyncClient(auth=...)`.

Usage example:
    client = httpx.AsyncClient(auth=BearerAuth(token))
    client = httpx.AsyncClient(auth=ApiKeyAuth("X-API-Key", key=my_key))
"""
from __future__ import annotations

import base64
from typing import Generator

import httpx


class ApiKeyAuth(httpx.Auth):
    """
    Adds an API key to a request header.

    Parameters
    ----------
    header_name:
        The header to inject the key into (e.g. ``"X-API-Key"``).
    key:
        The raw API key value.
    prefix:
        Optional string prepended to the key with a space separator
        (e.g. ``prefix="Token"`` → ``"Token <key>"``).
    """

    def __init__(self, header_name: str, key: str, prefix: str = "") -> None:
        self.header_name = header_name
        self.key = key
        self.prefix = prefix

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        value = f"{self.prefix} {self.key}".strip() if self.prefix else self.key
        request.headers[self.header_name] = value
        yield request


class BearerAuth(httpx.Auth):
    """
    Adds a ``Authorization: Bearer <token>`` header.

    Parameters
    ----------
    token:
        The bearer token (raw, without the ``Bearer `` prefix).
    """

    def __init__(self, token: str) -> None:
        self.token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class BasicAuth(httpx.Auth):
    """
    HTTP Basic Authentication (RFC 7617).

    Base64-encodes ``username:password`` and adds the
    ``Authorization: Basic <credentials>`` header.

    Parameters
    ----------
    username:
        The basic-auth username.
    password:
        The basic-auth password.
    """

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        request.headers["Authorization"] = f"Basic {encoded}"
        yield request


class OAuthTokenAuth(httpx.Auth):
    """
    OAuth 2.0 Bearer token auth — semantically identical to
    :class:`BearerAuth` but documents the OAuth context explicitly.

    Parameters
    ----------
    access_token:
        The OAuth access token obtained from the token endpoint.
    """

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        yield request


class QueryParamAuth(httpx.Auth):
    """
    Passes an API key as a URL query parameter.

    Some APIs (e.g. certain weather APIs) require the key in the query
    string rather than a header.

    Parameters
    ----------
    param_name:
        The query-string parameter name (e.g. ``"api_key"``).
    key:
        The raw key value to inject.
    """

    def __init__(self, param_name: str, key: str) -> None:
        self.param_name = param_name
        self.key = key

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        # Merge the key into the existing query params without clobbering them
        params = dict(request.url.params)
        params[self.param_name] = self.key
        request.url = request.url.copy_with(params=params)
        yield request
