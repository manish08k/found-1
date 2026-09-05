"""
Gotify push notification integration.

Provides message sending, listing, deletion, and application management
via the Gotify REST API.

Credential fields:
  - server_url : Gotify server base URL, e.g. http://gotify.example.com
  - token      : App token (for sending messages) or Client token
                 (for reading/deleting messages and managing apps)

Auth: X-Gotify-Key header with the provided token.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    server_url = creds.get("server_url", "").rstrip("/")
    token = creds.get("token")
    if not server_url:
        raise ValueError("Gotify credential missing 'server_url'")
    if not token:
        raise ValueError("Gotify credential missing 'token'")
    return httpx.AsyncClient(
        base_url=server_url,
        headers={
            "X-Gotify-Key": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=20.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"Gotify API error {r.status_code}: {detail}")


@register_node("gotify.send_message")
async def send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a push notification message via Gotify.
    Requires an app token with message:create scope.
    """
    title = config.get("title") or input_data.get("title", "Notification")
    message = config.get("message") or input_data.get("message")
    if not message:
        raise ValueError("'message' is required in config or input_data")

    priority = int(config.get("priority", 5))  # 1-10, higher = more urgent
    extras = config.get("extras") or input_data.get("extras")

    body: dict = {
        "title": title,
        "message": message,
        "priority": priority,
    }
    if extras:
        body["extras"] = extras

    log.info("gotify.send_message", title=title, priority=priority)

    async with await _client(credential_id, db) as client:
        r = await client.post("/message", json=body)
        _raise_for_status(r)
        sent = r.json()

    log.info("gotify.send_message.done", message_id=sent.get("id"))
    return {
        "sent": True,
        "message_id": sent.get("id"),
        "message": sent,
    }


@register_node("gotify.list_messages")
async def list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve messages from Gotify.
    Requires a client token with message:read scope.
    """
    limit = int(config.get("limit", 25))
    since = config.get("since") or input_data.get("since")  # message ID cursor
    app_id = config.get("app_id") or input_data.get("app_id")

    params: dict = {"limit": limit}
    if since:
        params["since"] = since

    log.info("gotify.list_messages", limit=limit, app_id=app_id)

    async with await _client(credential_id, db) as client:
        if app_id:
            r = await client.get(f"/application/{app_id}/message", params=params)
        else:
            r = await client.get("/message", params=params)
        _raise_for_status(r)
        data = r.json()

    messages = data.get("messages", data if isinstance(data, list) else [])
    paging = data.get("paging", {}) if isinstance(data, dict) else {}

    log.info("gotify.list_messages.done", count=len(messages))
    return {
        "messages": messages,
        "count": len(messages),
        "paging": paging,
    }


@register_node("gotify.delete_message")
async def delete_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Delete a specific message or all messages from Gotify.
    Requires a client token with message:delete scope.
    """
    message_id = config.get("message_id") or input_data.get("message_id")
    delete_all = config.get("delete_all", False)
    app_id = config.get("app_id") or input_data.get("app_id")

    log.info(
        "gotify.delete_message",
        message_id=message_id,
        delete_all=delete_all,
        app_id=app_id,
    )

    async with await _client(credential_id, db) as client:
        if delete_all:
            if app_id:
                r = await client.delete(f"/application/{app_id}/message")
            else:
                r = await client.delete("/message")
            _raise_for_status(r)
            log.info("gotify.delete_message.done", delete_all=True)
            return {"deleted": True, "delete_all": True, "app_id": app_id}
        else:
            if not message_id:
                raise ValueError("'message_id' is required when 'delete_all' is False")
            r = await client.delete(f"/message/{message_id}")
            _raise_for_status(r)
            log.info("gotify.delete_message.done", message_id=message_id)
            return {"deleted": True, "message_id": message_id}


@register_node("gotify.list_applications")
async def list_applications(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all applications registered in Gotify.
    Requires a client token with app:read scope.
    """
    log.info("gotify.list_applications")

    async with await _client(credential_id, db) as client:
        r = await client.get("/application")
        _raise_for_status(r)
        apps = r.json()

    if not isinstance(apps, list):
        apps = apps.get("applications", [])

    log.info("gotify.list_applications.done", count=len(apps))
    return {"applications": apps, "count": len(apps)}
