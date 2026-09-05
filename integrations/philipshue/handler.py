"""
Philips Hue smart lights integration.

Auth: username (Hue developer token generated on the bridge).

Credential fields:
  - bridge_ip (str) : Local IP address of the Hue bridge, e.g. "192.168.1.2".
  - username (str)  : Hue application key / developer username.

Nodes:
  - philipshue.list_lights    : List all lights on the bridge.
  - philipshue.set_light_state: Update state of a specific light.
  - philipshue.list_rooms     : List all rooms/groups on the bridge.
  - philipshue.set_room_state : Update state of all lights in a room/group.

Base URL: http://{bridge_ip}/api/{username}/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    bridge_ip = creds.get("bridge_ip")
    username = creds.get("username")
    if not bridge_ip:
        raise ValueError("Philips Hue credential missing 'bridge_ip'")
    if not username:
        raise ValueError("Philips Hue credential missing 'username'")
    base_url = f"http://{bridge_ip}/api/{username}/"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"Content-Type": "application/json"},
        timeout=15.0,
        # Local LAN — skip SSL verification not needed (HTTP)
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Philips Hue API error {r.status_code}: {detail}")


def _check_hue_errors(data) -> None:
    """Hue returns HTTP 200 with error objects in the response body."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "error" in item:
                err = item["error"]
                raise ValueError(f"Philips Hue error {err.get('type')}: {err.get('description')}")


def _build_light_state(config: dict, input_data: dict) -> dict:
    """Parse light state fields from config/input."""
    state: dict = {}

    on_val = config.get("on") if config.get("on") is not None else input_data.get("on")
    if on_val is not None:
        state["on"] = str(on_val).lower() != "false" and on_val is not False

    for field in ("bri", "hue", "sat", "ct"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            state[field] = int(val)

    for field in ("xy", "effect", "alert", "transitiontime"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            state[field] = val

    return state


@register_node("philipshue.list_lights")
async def list_lights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all lights registered on the Hue bridge.

    Config / input keys: none required.

    Returns a dict of light_id -> light_info.
    """
    log.info("philipshue.list_lights")
    async with await _client(credential_id, db) as client:
        r = await client.get("lights")
        _raise_for_status(r)
        data = r.json()

    _check_hue_errors(data)
    lights = data if isinstance(data, dict) else {}
    return {
        "lights": lights,
        "count": len(lights),
    }


@register_node("philipshue.set_light_state")
async def set_light_state(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Set the state of a specific light.

    Config / input keys:
      - light_id (str|int, required) : Light ID as shown by the bridge.
      - on (bool)                    : Turn on (true) or off (false).
      - bri (int)                    : Brightness 1–254.
      - hue (int)                    : Hue 0–65535.
      - sat (int)                    : Saturation 0–254.
      - ct (int)                     : Color temperature in Mireds 153–500.
      - xy (list[float])             : CIE xy color space [x, y].
      - effect (str)                 : "none" | "colorloop".
      - alert (str)                  : "none" | "select" | "lselect".
      - transitiontime (int)         : Transition time in 1/10 seconds.
    """
    light_id = config.get("light_id") or input_data.get("light_id")
    if not light_id:
        raise ValueError("philipshue.set_light_state requires 'light_id'")

    state = _build_light_state(config, input_data)
    if not state:
        raise ValueError("philipshue.set_light_state requires at least one state field (on, bri, hue, etc.)")

    log.info("philipshue.set_light_state", light_id=light_id, state=state)
    async with await _client(credential_id, db) as client:
        r = await client.put(f"lights/{light_id}/state", json=state)
        _raise_for_status(r)
        data = r.json()

    _check_hue_errors(data)
    return {
        "light_id": light_id,
        "state_set": state,
        "response": data,
    }


@register_node("philipshue.list_rooms")
async def list_rooms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all rooms (groups) registered on the Hue bridge.

    Config / input keys: none required.

    Returns a dict of group_id -> group_info.
    """
    log.info("philipshue.list_rooms")
    async with await _client(credential_id, db) as client:
        r = await client.get("groups")
        _raise_for_status(r)
        data = r.json()

    _check_hue_errors(data)
    groups = data if isinstance(data, dict) else {}
    # Filter to only Room type groups
    rooms = {k: v for k, v in groups.items() if v.get("type") in ("Room", "Zone", "LightGroup")}
    return {
        "rooms": rooms,
        "all_groups": groups,
        "count": len(rooms),
    }


@register_node("philipshue.set_room_state")
async def set_room_state(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Set the state of all lights in a room/group.

    Config / input keys:
      - room_id (str|int, required) : Group ID.
      - on (bool)                   : Turn on (true) or off (false).
      - bri (int)                   : Brightness 1–254.
      - hue (int)                   : Hue 0–65535.
      - sat (int)                   : Saturation 0–254.
      - ct (int)                    : Color temperature in Mireds.
      - xy (list[float])            : CIE xy [x, y].
      - effect (str)                : "none" | "colorloop".
      - alert (str)                 : "none" | "select" | "lselect".
      - transitiontime (int)        : Transition time in 1/10 seconds.
      - scene (str)                 : Scene ID to activate (mutually exclusive with color fields).
    """
    room_id = config.get("room_id") or input_data.get("room_id")
    if not room_id:
        raise ValueError("philipshue.set_room_state requires 'room_id'")

    state = _build_light_state(config, input_data)
    scene = config.get("scene") or input_data.get("scene")
    if scene:
        state["scene"] = scene

    if not state:
        raise ValueError("philipshue.set_room_state requires at least one state field (on, bri, scene, etc.)")

    log.info("philipshue.set_room_state", room_id=room_id, state=state)
    async with await _client(credential_id, db) as client:
        r = await client.put(f"groups/{room_id}/action", json=state)
        _raise_for_status(r)
        data = r.json()

    _check_hue_errors(data)
    return {
        "room_id": room_id,
        "state_set": state,
        "response": data,
    }
