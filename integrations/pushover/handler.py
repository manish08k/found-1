"""
Pushover push notifications integration.

Provides sending push notifications, listing available sounds, and
verifying a user/device key via the Pushover API.

Credential fields:
  - token : Pushover application API token.
  - user  : Pushover user key (or group key) of the message recipient.

Auth: token + user are sent as form/JSON body parameters on every request.
Base URL: https://api.pushover.net/1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.pushover.net/1"


async def _get_auth(credential_id: str, db) -> tuple[str, str]:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token")
    user = creds.get("user")
    if not token:
        raise ValueError("Pushover credential missing 'token'")
    if not user:
        raise ValueError("Pushover credential missing 'user'")
    return token, user


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Pushover API error {r.status_code}: {detail}")


@register_node("pushover.send_notification")
async def pushover_send_notification(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a push notification via Pushover.

    Params:
      - message (required): The notification message body.
      - title: Title of the notification (defaults to app name).
      - url: Supplementary URL to attach.
      - url_title: Title for the supplementary URL.
      - priority: -2 (lowest), -1 (low), 0 (normal, default), 1 (high), 2 (emergency).
      - retry: Required for priority=2 — seconds between retries (min 30).
      - expire: Required for priority=2 — seconds until the notification expires (max 10800).
      - sound: Sound name (see pushover.get_sounds for valid values).
      - device: Target a specific device name; omit for all devices.
      - timestamp: Unix timestamp to display instead of delivery time.
      - html: 1 to enable HTML formatting in message.
      - monospace: 1 to use monospace font.
    """
    token, user = await _get_auth(credential_id, db)

    message = config.get("message") or input_data.get("message")
    if not message:
        raise ValueError("pushover.send_notification requires 'message'")

    payload: dict = {"token": token, "user": user, "message": message}

    for field in ("title", "url", "url_title", "sound", "device"):
        val = config.get(field) or input_data.get(field)
        if val:
            payload[field] = val

    priority = config.get("priority")
    if priority is None:
        priority = input_data.get("priority")
    if priority is not None:
        payload["priority"] = int(priority)
        if int(priority) == 2:
            retry = config.get("retry") or input_data.get("retry", 60)
            expire = config.get("expire") or input_data.get("expire", 3600)
            payload["retry"] = int(retry)
            payload["expire"] = int(expire)

    for int_field in ("timestamp", "html", "monospace"):
        val = config.get(int_field) or input_data.get(int_field)
        if val is not None:
            payload[int_field] = int(val)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post("/messages.json", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("pushover.send_notification", status=data.get("status"), request=data.get("request"))
    return {
        "status": data.get("status"),
        "request": data.get("request"),
        "response": data,
    }


@register_node("pushover.get_sounds")
async def pushover_get_sounds(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve the list of valid notification sound names.

    No additional params required beyond credentials.
    """
    token, _ = await _get_auth(credential_id, db)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get("/sounds.json", params={"token": token})
        _raise_for_status(r)
        data = r.json()

    sounds = data.get("sounds", {})
    log.info("pushover.get_sounds", count=len(sounds))
    return {"sounds": sounds, "status": data.get("status")}


@register_node("pushover.verify_user")
async def pushover_verify_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Verify a user/group key and optionally a specific device.

    Params:
      - device: Optional device name to verify that the user has that device registered.
    """
    token, user = await _get_auth(credential_id, db)

    payload: dict = {"token": token, "user": user}

    device = config.get("device") or input_data.get("device")
    if device:
        payload["device"] = device

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post("/users/validate.json", json=payload)
        _raise_for_status(r)
        data = r.json()

    is_valid = data.get("status") == 1
    log.info("pushover.verify_user", valid=is_valid, devices=data.get("devices"))
    return {
        "valid": is_valid,
        "status": data.get("status"),
        "devices": data.get("devices", []),
        "licenses": data.get("licenses", []),
        "response": data,
    }
