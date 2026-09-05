"""
Bitly URL shortener integration.

Provides link shortening, click analytics, Bitlink listing, and
Bitlink metadata updates via the Bitly API v4.

Credential fields:
  - api_key : Bitly Generic Access Token (found in Profile Settings > Developer settings).

Auth: Bearer token via Authorization header.
Base URL: https://api-ssl.bitly.com/v4/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api-ssl.bitly.com/v4"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Bitly credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Bitly API error {r.status_code}: {detail}")


@register_node("bitly.shorten_url")
async def bitly_shorten_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Shorten a long URL to a Bitlink.

    Params:
      - long_url (required): The URL to shorten (must be a valid URL with scheme).
      - domain: Custom domain to use (e.g. 'bit.ly'). Defaults to account default.
      - group_guid: GUID of the group to create the Bitlink under.
      - title: Custom title for the Bitlink.
      - tags: Comma-separated list of tags to assign.
    """
    long_url = config.get("long_url") or input_data.get("long_url")
    if not long_url:
        raise ValueError("bitly.shorten_url requires 'long_url'")

    payload: dict = {"long_url": long_url}

    domain = config.get("domain") or input_data.get("domain")
    if domain:
        payload["domain"] = domain

    group_guid = config.get("group_guid") or input_data.get("group_guid")
    if group_guid:
        payload["group_guid"] = group_guid

    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    tags_raw = config.get("tags") or input_data.get("tags")
    if tags_raw:
        payload["tags"] = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

    async with await _client(credential_id, db) as client:
        r = await client.post("/shorten", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bitly.shorten_url", link=data.get("link"))
    return {
        "link": data.get("link"),
        "id": data.get("id"),
        "long_url": data.get("long_url"),
        "created_at": data.get("created_at"),
        "bitlink": data,
    }


@register_node("bitly.get_link_clicks")
async def bitly_get_link_clicks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve click metrics for a Bitlink.

    Params:
      - bitlink_id (required): Bitlink ID in the form 'bit.ly/abc123'.
      - unit: Time unit — 'minute', 'hour', 'day', 'week', 'month' (default 'day').
      - units: Number of units back from now (-1 for all time, default 30).
      - size: Number of data points to return (max 1000, default 50).
      - unit_reference: ISO-8601 timestamp as reference point.
    """
    bitlink_id = config.get("bitlink_id") or input_data.get("bitlink_id")
    if not bitlink_id:
        raise ValueError("bitly.get_link_clicks requires 'bitlink_id'")

    # Strip scheme if user passed full URL
    bitlink_id = bitlink_id.removeprefix("https://").removeprefix("http://")

    unit = config.get("unit") or input_data.get("unit", "day")
    units = int(config.get("units") if config.get("units") is not None else input_data.get("units", 30))
    size = min(int(config.get("size") or input_data.get("size", 50)), 1000)

    params: dict = {"unit": unit, "units": units, "size": size}
    unit_reference = config.get("unit_reference") or input_data.get("unit_reference")
    if unit_reference:
        params["unit_reference"] = unit_reference

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/bitlinks/{bitlink_id}/clicks", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "link_clicks": data.get("link_clicks", []),
        "units": data.get("units"),
        "unit": data.get("unit"),
        "unit_reference": data.get("unit_reference"),
    }


@register_node("bitly.list_bitlinks")
async def bitly_list_bitlinks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List Bitlinks for a group.

    Params:
      - group_guid (required): The group GUID to list Bitlinks for.
      - size: Number of results per page (max 100, default 50).
      - page: Page number (default 1).
      - keyword: Filter by keyword in Bitlink.
      - query: Search query string.
      - archived: 'on', 'off', 'both' (default 'off').
      - deeplinks: 'on', 'off', 'both' (default 'both').
      - tags: Comma-separated list of tags to filter by.
      - created_before: Unix timestamp for upper bound on creation date.
      - created_after: Unix timestamp for lower bound on creation date.
      - modified_after: Unix timestamp for lower bound on modification date.
    """
    group_guid = config.get("group_guid") or input_data.get("group_guid")
    if not group_guid:
        raise ValueError("bitly.list_bitlinks requires 'group_guid'")

    size = min(int(config.get("size") or input_data.get("size", 50)), 100)
    page = int(config.get("page") or input_data.get("page", 1))

    params: dict = {"size": size, "page": page}

    for field in ("keyword", "query", "archived", "deeplinks", "created_before", "created_after", "modified_after"):
        val = config.get(field) or input_data.get(field)
        if val is not None:
            params[field] = val

    tags_raw = config.get("tags") or input_data.get("tags")
    if tags_raw:
        params["tags"] = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/groups/{group_guid}/bitlinks", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("bitly.list_bitlinks", group=group_guid, count=len(data.get("links", [])))
    return {
        "bitlinks": data.get("links", []),
        "pagination": data.get("pagination", {}),
    }


@register_node("bitly.update_bitlink")
async def bitly_update_bitlink(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update metadata of an existing Bitlink.

    Params:
      - bitlink_id (required): Bitlink ID (e.g. 'bit.ly/abc123').
      - title: New title.
      - archived: bool — archive or un-archive the Bitlink.
      - tags: Comma-separated list of tags (replaces existing tags).
      - long_url: Update the destination URL.
    """
    bitlink_id = config.get("bitlink_id") or input_data.get("bitlink_id")
    if not bitlink_id:
        raise ValueError("bitly.update_bitlink requires 'bitlink_id'")

    bitlink_id = bitlink_id.removeprefix("https://").removeprefix("http://")

    payload: dict = {}
    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    archived = config.get("archived")
    if archived is None:
        archived = input_data.get("archived")
    if archived is not None:
        payload["archived"] = bool(archived)

    long_url = config.get("long_url") or input_data.get("long_url")
    if long_url:
        payload["long_url"] = long_url

    tags_raw = config.get("tags") or input_data.get("tags")
    if tags_raw:
        payload["tags"] = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

    if not payload:
        raise ValueError("bitly.update_bitlink requires at least one field to update")

    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/bitlinks/{bitlink_id}", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bitly.update_bitlink", bitlink_id=bitlink_id)
    return {"bitlink": data, "link": data.get("link")}


@register_node("bitly.get_bitlink")
async def bitly_get_bitlink(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve details of a single Bitlink.

    Params:
      - bitlink_id (required): Bitlink ID (e.g. 'bit.ly/abc123').
    """
    bitlink_id = config.get("bitlink_id") or input_data.get("bitlink_id")
    if not bitlink_id:
        raise ValueError("bitly.get_bitlink requires 'bitlink_id'")

    bitlink_id = bitlink_id.removeprefix("https://").removeprefix("http://")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/bitlinks/{bitlink_id}")
        _raise_for_status(r)
        data = r.json()

    return {"bitlink": data, "link": data.get("link"), "long_url": data.get("long_url")}
