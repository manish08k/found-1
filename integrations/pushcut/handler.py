"""
Pushcut iOS notifications integration.

Provides triggering Pushcut notifications and listing configured
notifications via the Pushcut API v1.

Credential fields:
  - api_key : Pushcut API Key (found in the Pushcut app under Account > API Key).

Auth: api_key sent in the API-Key request header.
Base URL: https://api.pushcut.io/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.pushcut.io/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Pushcut credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "API-Key": api_key,
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
        raise ValueError(f"Pushcut API error {r.status_code}: {detail}")


@register_node("pushcut.send_notification")
async def pushcut_send_notification(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Trigger a Pushcut notification by name.

    Params:
      - notification_name (required): Name of the notification as configured in the
        Pushcut app (URL-safe name).
      - title: Override the notification title.
      - text: Override the notification body text.
      - input: Input value made available to Shortcuts/automations triggered by the notification.
      - actions: List of action dicts to override the notification's actions.
        Each action: {"label": str, "url": str, "shortcut": str, "homescreen": bool}
      - devices: List of device names to target. Omit to target all devices.
      - sound: Sound name to override the default notification sound.
      - image_url: URL of an image to attach to the notification.
      - is_time_sensitive: bool — mark the notification as time-sensitive (bypasses Focus modes).
    """
    notification_name = config.get("notification_name") or input_data.get("notification_name")
    if not notification_name:
        raise ValueError("pushcut.send_notification requires 'notification_name'")

    payload: dict = {}

    for field in ("title", "text", "input", "sound", "image_url"):
        val = config.get(field) or input_data.get(field)
        if val is not None:
            payload[field] = val

    actions = config.get("actions") or input_data.get("actions")
    if actions:
        payload["actions"] = actions

    devices = config.get("devices") or input_data.get("devices")
    if devices:
        payload["devices"] = devices if isinstance(devices, list) else [devices]

    is_time_sensitive = config.get("is_time_sensitive")
    if is_time_sensitive is None:
        is_time_sensitive = input_data.get("is_time_sensitive")
    if is_time_sensitive is not None:
        payload["isTimeSensitive"] = bool(is_time_sensitive)

    import urllib.parse
    encoded_name = urllib.parse.quote(notification_name, safe="")

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/notifications/{encoded_name}", json=payload)
        _raise_for_status(r)
        # Pushcut returns 200 with minimal body on success
        try:
            data = r.json()
        except Exception:
            data = {}

    log.info("pushcut.send_notification", notification_name=notification_name)
    return {"success": True, "notification_name": notification_name, "response": data}


@register_node("pushcut.list_notifications")
async def pushcut_list_notifications(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all notifications configured in the Pushcut account.

    No parameters required.
    """
    async with await _client(credential_id, db) as client:
        r = await client.get("/notifications")
        _raise_for_status(r)
        data = r.json()

    notifications = data if isinstance(data, list) else data.get("notifications", data)
    log.info("pushcut.list_notifications", count=len(notifications) if isinstance(notifications, list) else None)
    return {"notifications": notifications}
