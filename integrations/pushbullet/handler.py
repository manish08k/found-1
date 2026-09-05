"""
Pushbullet push notifications integration.

Provides push creation (notes and links), listing pushes, and
listing linked devices via the Pushbullet API v2.

Credential fields:
  - api_key : Pushbullet Access Token (found in Account Settings > Access Tokens).

Auth: Bearer token via Authorization header.
Base URL: https://api.pushbullet.com/v2/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.pushbullet.com/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Pushbullet credential missing 'api_key'")
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
        raise ValueError(f"Pushbullet API error {r.status_code}: {detail}")


@register_node("pushbullet.send_note")
async def pushbullet_send_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a note push to a device or all devices.

    Params:
      - title (required): Title of the note.
      - body (required): Body text of the note.
      - device_iden: Target a specific device by its identifier. Omit to push to all devices.
      - email: Send to a specific Pushbullet user by email address.
      - channel_tag: Publish the push to a channel (identified by tag).
    """
    title = config.get("title") or input_data.get("title")
    body = config.get("body") or input_data.get("body")
    if not title:
        raise ValueError("pushbullet.send_note requires 'title'")
    if not body:
        raise ValueError("pushbullet.send_note requires 'body'")

    payload: dict = {"type": "note", "title": title, "body": body}

    for field in ("device_iden", "email", "channel_tag"):
        val = config.get(field) or input_data.get(field)
        if val:
            payload[field] = val

    async with await _client(credential_id, db) as client:
        r = await client.post("/pushes", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("pushbullet.send_note", iden=data.get("iden"), title=title)
    return {"push": data, "iden": data.get("iden")}


@register_node("pushbullet.send_link")
async def pushbullet_send_link(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a link push to a device or all devices.

    Params:
      - url (required): URL to push.
      - title: Title of the link push.
      - body: Optional description/body text.
      - device_iden: Target a specific device by identifier.
      - email: Send to a specific Pushbullet user by email.
      - channel_tag: Publish to a channel.
    """
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("pushbullet.send_link requires 'url'")

    payload: dict = {"type": "link", "url": url}

    for field in ("title", "body", "device_iden", "email", "channel_tag"):
        val = config.get(field) or input_data.get(field)
        if val:
            payload[field] = val

    async with await _client(credential_id, db) as client:
        r = await client.post("/pushes", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("pushbullet.send_link", iden=data.get("iden"), url=url)
    return {"push": data, "iden": data.get("iden")}


@register_node("pushbullet.list_pushes")
async def pushbullet_list_pushes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List recent pushes.

    Params:
      - modified_after: Unix timestamp — only return pushes modified after this time.
      - active: bool — only return active (non-deleted) pushes (default True).
      - cursor: Pagination cursor from a previous response.
      - limit: Maximum number of pushes to return (max 500, default 100).
    """
    params: dict = {}

    modified_after = config.get("modified_after") or input_data.get("modified_after")
    if modified_after is not None:
        params["modified_after"] = float(modified_after)

    active = config.get("active")
    if active is None:
        active = input_data.get("active", True)
    params["active"] = str(active).lower()

    cursor = config.get("cursor") or input_data.get("cursor")
    if cursor:
        params["cursor"] = cursor

    limit = config.get("limit") or input_data.get("limit", 100)
    params["limit"] = min(int(limit), 500)

    async with await _client(credential_id, db) as client:
        r = await client.get("/pushes", params=params)
        _raise_for_status(r)
        data = r.json()

    pushes = data.get("pushes", [])
    log.info("pushbullet.list_pushes", count=len(pushes))
    return {
        "pushes": pushes,
        "cursor": data.get("cursor"),
    }


@register_node("pushbullet.list_devices")
async def pushbullet_list_devices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all devices linked to the Pushbullet account.

    Params:
      - active: bool — only return active devices (default True).
      - cursor: Pagination cursor.
      - limit: Max devices to return (max 500, default 100).
    """
    params: dict = {}

    active = config.get("active")
    if active is None:
        active = input_data.get("active", True)
    params["active"] = str(active).lower()

    cursor = config.get("cursor") or input_data.get("cursor")
    if cursor:
        params["cursor"] = cursor

    limit = config.get("limit") or input_data.get("limit", 100)
    params["limit"] = min(int(limit), 500)

    async with await _client(credential_id, db) as client:
        r = await client.get("/devices", params=params)
        _raise_for_status(r)
        data = r.json()

    devices = data.get("devices", [])
    log.info("pushbullet.list_devices", count=len(devices))
    return {
        "devices": devices,
        "cursor": data.get("cursor"),
    }
