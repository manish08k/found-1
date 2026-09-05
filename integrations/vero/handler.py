"""Vero customer messaging integration — identify users, track events, manage subscriptions."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VERO_BASE = "https://api.getvero.com/api/v2"


@register_node("vero.identify_user")
async def vero_identify_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create or update a user profile in Vero.

    config/input_data:
      auth_token — Vero API auth token
      id         — user identifier
      email      — user email address
      data       — optional dict of additional user properties
      channels   — optional list of channel objects
    """
    merged = {**config, **input_data}
    auth_token = merged.get("auth_token")
    user_id = merged.get("id")
    if not auth_token:
        raise ValueError("auth_token is required for vero.identify_user")
    if not user_id:
        raise ValueError("id is required for vero.identify_user")

    payload: dict = {"auth_token": auth_token, "id": user_id}
    if merged.get("email"):
        payload["email"] = merged["email"]
    if merged.get("data"):
        payload["data"] = merged["data"]
    if merged.get("channels"):
        payload["channels"] = merged["channels"]

    async with httpx.AsyncClient(base_url=VERO_BASE, timeout=30) as client:
        r = await client.post("/users/track", json=payload)
        r.raise_for_status()
        result = r.json() if r.content else {"status": r.status_code}

    log.info("vero.identify_user", user_id=user_id)
    return result


@register_node("vero.track_event")
async def vero_track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track a custom event for a user in Vero.

    config/input_data:
      auth_token  — Vero API auth token
      identity    — dict with "id" or "email" to identify the user
      event_name  — name of the event to track
      data        — optional dict of event properties
    """
    merged = {**config, **input_data}
    auth_token = merged.get("auth_token")
    identity = merged.get("identity", {})
    event_name = merged.get("event_name")
    if not auth_token:
        raise ValueError("auth_token is required for vero.track_event")
    if not identity:
        raise ValueError("identity is required for vero.track_event")
    if not event_name:
        raise ValueError("event_name is required for vero.track_event")

    payload: dict = {
        "auth_token": auth_token,
        "identity": identity,
        "event_name": event_name,
    }
    if merged.get("data"):
        payload["data"] = merged["data"]

    async with httpx.AsyncClient(base_url=VERO_BASE, timeout=30) as client:
        r = await client.post("/events/track", json=payload)
        r.raise_for_status()
        result = r.json() if r.content else {"status": r.status_code}

    log.info("vero.track_event", event_name=event_name, identity=identity)
    return result


@register_node("vero.unsubscribe_user")
async def vero_unsubscribe_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Unsubscribe a user from Vero emails.

    config/input_data:
      auth_token — Vero API auth token
      id         — user identifier
    """
    merged = {**config, **input_data}
    auth_token = merged.get("auth_token")
    user_id = merged.get("id")
    if not auth_token:
        raise ValueError("auth_token is required for vero.unsubscribe_user")
    if not user_id:
        raise ValueError("id is required for vero.unsubscribe_user")

    payload = {"auth_token": auth_token, "id": user_id}

    async with httpx.AsyncClient(base_url=VERO_BASE, timeout=30) as client:
        r = await client.post("/users/unsubscribe", json=payload)
        r.raise_for_status()
        result = r.json() if r.content else {"status": r.status_code}

    log.info("vero.unsubscribe_user", user_id=user_id)
    return result


@register_node("vero.resubscribe_user")
async def vero_resubscribe_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Resubscribe a user to Vero emails.

    config/input_data:
      auth_token — Vero API auth token
      id         — user identifier
    """
    merged = {**config, **input_data}
    auth_token = merged.get("auth_token")
    user_id = merged.get("id")
    if not auth_token:
        raise ValueError("auth_token is required for vero.resubscribe_user")
    if not user_id:
        raise ValueError("id is required for vero.resubscribe_user")

    payload = {"auth_token": auth_token, "id": user_id}

    async with httpx.AsyncClient(base_url=VERO_BASE, timeout=30) as client:
        r = await client.post("/users/resubscribe", json=payload)
        r.raise_for_status()
        result = r.json() if r.content else {"status": r.status_code}

    log.info("vero.resubscribe_user", user_id=user_id)
    return result


@register_node("vero.delete_user")
async def vero_delete_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a user from Vero.

    config/input_data:
      auth_token — Vero API auth token
      id         — user identifier
    """
    merged = {**config, **input_data}
    auth_token = merged.get("auth_token")
    user_id = merged.get("id")
    if not auth_token:
        raise ValueError("auth_token is required for vero.delete_user")
    if not user_id:
        raise ValueError("id is required for vero.delete_user")

    payload = {"auth_token": auth_token, "id": user_id}

    async with httpx.AsyncClient(base_url=VERO_BASE, timeout=30) as client:
        r = await client.post("/users/delete", json=payload)
        r.raise_for_status()
        result = r.json() if r.content else {"status": r.status_code}

    log.info("vero.delete_user", user_id=user_id)
    return result
