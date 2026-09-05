"""Gameball — customer loyalty and gamification integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GAMEBALL_BASE = "https://gb-api.gameball.co/api/v3.0"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "APIKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("gameball.track_event")
async def gameball_track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track a custom event for a player in Gameball.

    config/input_data:
      api_key          — Gameball API key
      player_id        — unique player identifier (required)
      event_name       — name of the event to track (required)
      event_properties — optional dict of event properties
    """
    player_id = config.get("player_id") or input_data.get("player_id")
    event_name = config.get("event_name") or input_data.get("event_name")
    event_properties = config.get("event_properties") or input_data.get("event_properties") or {}

    if not player_id:
        raise ValueError("player_id is required for gameball.track_event")
    if not event_name:
        raise ValueError("event_name is required for gameball.track_event")

    payload = {
        "events": {event_name: event_properties},
        "playerUniqueId": player_id,
    }

    async with httpx.AsyncClient(base_url=GAMEBALL_BASE, timeout=30) as client:
        r = await client.post("/transaction/event", json=payload, headers=_headers(config))
        r.raise_for_status()
        result = r.json()

    log.info("gameball.track_event", player_id=player_id, event_name=event_name)
    return {"result": result, "player_id": player_id, "event_name": event_name}


@register_node("gameball.get_player")
async def gameball_get_player(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Gameball player profile.

    config/input_data:
      api_key   — Gameball API key
      player_id — unique player identifier (required)
    """
    player_id = config.get("player_id") or input_data.get("player_id")
    if not player_id:
        raise ValueError("player_id is required for gameball.get_player")

    async with httpx.AsyncClient(base_url=GAMEBALL_BASE, timeout=30) as client:
        r = await client.get(
            "/player",
            params={"playerUniqueId": player_id},
            headers=_headers(config),
        )
        r.raise_for_status()
        player = r.json()

    log.info("gameball.get_player", player_id=player_id)
    return {"player": player, "player_id": player_id}


@register_node("gameball.create_player")
async def gameball_create_player(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create or update a player in Gameball.

    config/input_data:
      api_key   — Gameball API key
      player_id — unique player identifier (required)
      name      — player display name (required)
      email     — player email address (optional)
    """
    player_id = config.get("player_id") or input_data.get("player_id")
    name = config.get("name") or input_data.get("name")
    email = config.get("email") or input_data.get("email", "")

    if not player_id:
        raise ValueError("player_id is required for gameball.create_player")
    if not name:
        raise ValueError("name is required for gameball.create_player")

    payload: dict = {"playerUniqueId": player_id, "displayName": name}
    if email:
        payload["email"] = email

    async with httpx.AsyncClient(base_url=GAMEBALL_BASE, timeout=30) as client:
        r = await client.post("/player", json=payload, headers=_headers(config))
        r.raise_for_status()
        player = r.json()

    log.info("gameball.create_player", player_id=player_id, name=name)
    return {"player": player, "player_id": player_id, "name": name}
