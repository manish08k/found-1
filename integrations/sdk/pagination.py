"""
Integration SDK — Pagination helpers.

All paginators are async generators that yield individual items (not pages).
They accept a ``ResilientHTTPClient`` instance and fetch pages lazily —
each subsequent page is only fetched after the caller has consumed the
previous batch.

Usage example:
    async with ResilientHTTPClient(...) as client:
        async for item in CursorPaginator(client, "/contacts",
                                          cursor_field="next_cursor",
                                          items_field="data"):
            process(item)
"""
from __future__ import annotations

import re
from typing import Any, AsyncGenerator, Optional

from integrations.sdk.http import ResilientHTTPClient


class CursorPaginator:
    """
    Cursor-based pagination.

    The API returns a cursor value in the response body (e.g. ``next_cursor``).
    We pass it as a query parameter on the next request until it is absent or
    ``null``.

    Parameters
    ----------
    client:
        A ``ResilientHTTPClient`` instance (already authenticated).
    url:
        The endpoint path or full URL.
    cursor_field:
        Key in the response body that contains the next-page cursor.
    items_field:
        Key in the response body that contains the list of items.
    cursor_param:
        Query-parameter name used to pass the cursor to the API.
        Defaults to the same value as ``cursor_field``.
    params:
        Additional query parameters to include in every request.
    max_pages:
        Safety ceiling to avoid infinite loops. Default 1000.
    """

    def __init__(
        self,
        client: ResilientHTTPClient,
        url: str,
        *,
        cursor_field: str,
        items_field: str,
        cursor_param: str | None = None,
        params: dict[str, Any] | None = None,
        max_pages: int = 1_000,
    ) -> None:
        self._client = client
        self._url = url
        self._cursor_field = cursor_field
        self._items_field = items_field
        self._cursor_param = cursor_param or cursor_field
        self._params = dict(params or {})
        self._max_pages = max_pages

    def __aiter__(self) -> AsyncGenerator[Any, None]:
        return self._generate()

    async def _generate(self) -> AsyncGenerator[Any, None]:
        cursor: str | None = None
        for _ in range(self._max_pages):
            params = dict(self._params)
            if cursor:
                params[self._cursor_param] = cursor

            data = await self._client.get(self._url, params=params)
            items = _extract_field(data, self._items_field, [])

            for item in items:
                yield item

            cursor = _extract_field(data, self._cursor_field, None)
            if not cursor:
                break


class OffsetPaginator:
    """
    Offset / limit pagination.

    Increments the offset by ``page_size`` on each request.

    Parameters
    ----------
    client:
        Authenticated ``ResilientHTTPClient``.
    url:
        The endpoint path or full URL.
    items_field:
        Key in the response body containing the item list.
    limit_param:
        Query-parameter name for the page size. Default ``"limit"``.
    offset_param:
        Query-parameter name for the offset. Default ``"offset"``.
    page_size:
        Number of items per page. Default 100.
    params:
        Additional query parameters to include in every request.
    max_pages:
        Safety ceiling to avoid infinite loops. Default 1000.
    """

    def __init__(
        self,
        client: ResilientHTTPClient,
        url: str,
        *,
        items_field: str,
        limit_param: str = "limit",
        offset_param: str = "offset",
        page_size: int = 100,
        params: dict[str, Any] | None = None,
        max_pages: int = 1_000,
    ) -> None:
        self._client = client
        self._url = url
        self._items_field = items_field
        self._limit_param = limit_param
        self._offset_param = offset_param
        self._page_size = page_size
        self._params = dict(params or {})
        self._max_pages = max_pages

    def __aiter__(self) -> AsyncGenerator[Any, None]:
        return self._generate()

    async def _generate(self) -> AsyncGenerator[Any, None]:
        offset = 0
        for _ in range(self._max_pages):
            params = {
                **self._params,
                self._limit_param: self._page_size,
                self._offset_param: offset,
            }

            data = await self._client.get(self._url, params=params)
            items = _extract_field(data, self._items_field, [])

            for item in items:
                yield item

            if len(items) < self._page_size:
                # Last page — fewer items than requested means no more data.
                break

            offset += len(items)


class LinkHeaderPaginator:
    """
    RFC 5988 ``Link: <next>; rel="next"`` pagination (e.g. GitHub REST API).

    Follows the ``next`` link in the ``Link`` response header until there
    are no more pages.

    Parameters
    ----------
    client:
        Authenticated ``ResilientHTTPClient``.
    url:
        The initial endpoint path or full URL.
    items_field:
        Key in the response body containing the item list, or ``None`` if
        the response body itself is the list.
    params:
        Additional query parameters for the first request only.
    max_pages:
        Safety ceiling. Default 1000.
    """

    def __init__(
        self,
        client: ResilientHTTPClient,
        url: str,
        *,
        items_field: str | None = None,
        params: dict[str, Any] | None = None,
        max_pages: int = 1_000,
    ) -> None:
        self._client = client
        self._url = url
        self._items_field = items_field
        self._params = dict(params or {})
        self._max_pages = max_pages

    def __aiter__(self) -> AsyncGenerator[Any, None]:
        return self._generate()

    async def _generate(self) -> AsyncGenerator[Any, None]:
        url: str | None = self._url
        first = True

        for _ in range(self._max_pages):
            if url is None:
                break

            kwargs: dict[str, Any] = {}
            if first:
                kwargs["params"] = self._params
                first = False

            response = await self._client.raw("GET", url, **kwargs)

            # Parse items from body
            try:
                body = response.json()
            except Exception:
                body = []

            if self._items_field:
                items = _extract_field(body, self._items_field, [])
            else:
                items = body if isinstance(body, list) else []

            for item in items:
                yield item

            url = _parse_link_header_next(response.headers.get("Link", ""))


class PageNumberPaginator:
    """
    Page-number pagination (e.g. ``?page=1``, ``?page=2`` …).

    Parameters
    ----------
    client:
        Authenticated ``ResilientHTTPClient``.
    url:
        The endpoint path or full URL.
    items_field:
        Key in the response body containing the item list.
    total_pages_field:
        Key in the response body containing the total page count. If the
        API does not return this, we stop when we receive an empty page.
    page_param:
        Query-parameter name for the page number. Default ``"page"``.
    start_page:
        First page number. Default 1 (some APIs use 0).
    page_size_param:
        Optional query-parameter for the page size.
    page_size:
        Optional value to pass for ``page_size_param``.
    params:
        Additional query parameters included in every request.
    max_pages:
        Hard ceiling. Default 1000.
    """

    def __init__(
        self,
        client: ResilientHTTPClient,
        url: str,
        *,
        items_field: str,
        total_pages_field: str | None = None,
        page_param: str = "page",
        start_page: int = 1,
        page_size_param: str | None = None,
        page_size: int | None = None,
        params: dict[str, Any] | None = None,
        max_pages: int = 1_000,
    ) -> None:
        self._client = client
        self._url = url
        self._items_field = items_field
        self._total_pages_field = total_pages_field
        self._page_param = page_param
        self._start_page = start_page
        self._page_size_param = page_size_param
        self._page_size = page_size
        self._params = dict(params or {})
        self._max_pages = max_pages

    def __aiter__(self) -> AsyncGenerator[Any, None]:
        return self._generate()

    async def _generate(self) -> AsyncGenerator[Any, None]:
        total_pages: int | None = None

        for page_num in range(self._start_page, self._start_page + self._max_pages):
            params: dict[str, Any] = {**self._params, self._page_param: page_num}
            if self._page_size_param and self._page_size is not None:
                params[self._page_size_param] = self._page_size

            data = await self._client.get(self._url, params=params)
            items = _extract_field(data, self._items_field, [])

            for item in items:
                yield item

            # Determine total pages on the first response
            if total_pages is None and self._total_pages_field:
                total_pages = _extract_field(data, self._total_pages_field, None)
                if total_pages is not None:
                    total_pages = int(total_pages)

            # Stop conditions
            if not items:
                break
            if total_pages is not None and page_num >= (self._start_page + total_pages - 1):
                break


# ── Internal helpers ───────────────────────────────────────────────────────────

def _extract_field(data: Any, field: str, default: Any) -> Any:
    """
    Navigate a dot-separated field path into a nested dict/list structure.
    Returns ``default`` if any segment is missing or the wrong type.

    Example: ``_extract_field(data, "meta.pagination.cursor", None)``
    """
    parts = field.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        else:
            return default
    return current if current is not None else default


_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')


def _parse_link_header_next(link_header: str) -> str | None:
    """
    Extract the URL associated with ``rel="next"`` from a Link header.

    Returns ``None`` if there is no next link.

    Example::
        Link: <https://api.example.com/items?page=2>; rel="next",
              <https://api.example.com/items?page=5>; rel="last"
    """
    for url, rel in _LINK_RE.findall(link_header):
        if rel == "next":
            return url
    return None
