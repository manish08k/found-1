"""Home Assistant integration — entity states, services, IoT control."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _ha_base_url(creds: dict) -> str:
    """Construct the Home Assistant API base URL from credential fields.

    Credential fields:
      host  — HA hostname or IP (e.g. homeassistant.local or 192.168.1.10)
      port  — HA HTTP port (default 8123)
      token — long-lived access token
    """
    host = creds.get("host", "homeassistant.local").rstrip("/")
    port = int(creds.get("port", 8123))

    # If host already includes a scheme, use it; otherwise default to http
    if host.startswith("http://") or host.startswith("https://"):
        return f"{host}:{port}/api/"
    return f"http://{host}:{port}/api/"


@register_node("home_assistant.get_states")
async def ha_get_states(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch all entity states from Home Assistant.

    config:
      domain   — filter by domain (e.g. 'light', 'switch', 'sensor') — optional
      limit    — max entities to return (default: all)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token") or creds.get("long_lived_access_token", "")
    base_url = _ha_base_url(creds)

    domain_filter = config.get("domain") or input_data.get("domain")
    limit = config.get("limit") or input_data.get("limit")

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get("states")
        r.raise_for_status()
        states = r.json()

    if domain_filter:
        states = [s for s in states if s.get("entity_id", "").startswith(f"{domain_filter}.")]

    if limit:
        states = states[:int(limit)]

    log.info("home_assistant.get_states", count=len(states), domain=domain_filter)
    return {
        "states": states,
        "count": len(states),
        "domain": domain_filter,
    }


@register_node("home_assistant.get_entity")
async def ha_get_entity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch state of a single Home Assistant entity.

    config/input_data:
      entity_id — full entity ID (e.g. 'light.living_room') (required)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token") or creds.get("long_lived_access_token", "")
    base_url = _ha_base_url(creds)

    entity_id = config.get("entity_id") or input_data.get("entity_id")
    if not entity_id:
        raise ValueError("entity_id is required for home_assistant.get_entity")

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get(f"states/{entity_id}")
        r.raise_for_status()
        state = r.json()

    log.info("home_assistant.get_entity", entity_id=entity_id, state=state.get("state"))
    return {
        "entity_id": entity_id,
        "state": state.get("state"),
        "attributes": state.get("attributes", {}),
        "last_changed": state.get("last_changed"),
        "last_updated": state.get("last_updated"),
        "entity": state,
    }


@register_node("home_assistant.set_state")
async def ha_set_state(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Set (or create) the state of a Home Assistant entity via the REST API.

    Note: This updates the state object in the state machine directly, which is
    different from calling a service. Use call_service for controlling actual devices.

    config/input_data:
      entity_id   — full entity ID (required)
      state       — state value string (required)
      attributes  — dict of additional state attributes (optional)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token") or creds.get("long_lived_access_token", "")
    base_url = _ha_base_url(creds)

    entity_id = config.get("entity_id") or input_data.get("entity_id")
    state_val = config.get("state") or input_data.get("state")
    attributes = config.get("attributes") or input_data.get("attributes", {})

    if not entity_id or state_val is None:
        raise ValueError("entity_id and state are required for home_assistant.set_state")

    payload: dict = {"state": str(state_val)}
    if attributes:
        payload["attributes"] = attributes

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post(f"states/{entity_id}", json=payload)
        r.raise_for_status()
        result = r.json()

    log.info("home_assistant.set_state", entity_id=entity_id, state=state_val)
    return {
        "entity_id": entity_id,
        "state": result.get("state"),
        "attributes": result.get("attributes", {}),
        "created": r.status_code == 201,
        "entity": result,
    }


@register_node("home_assistant.call_service")
async def ha_call_service(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Call a Home Assistant service (e.g. turn on a light, lock a door).

    config/input_data:
      domain      — service domain (e.g. 'light', 'switch', 'lock') (required)
      service     — service name (e.g. 'turn_on', 'turn_off', 'toggle') (required)
      entity_id   — target entity ID or list of entity IDs (optional)
      service_data — additional service data dict (optional)

    Examples:
      domain=light, service=turn_on, entity_id=light.living_room,
        service_data={"brightness": 200, "color_temp": 4000}
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token") or creds.get("long_lived_access_token", "")
    base_url = _ha_base_url(creds)

    domain = config.get("domain") or input_data.get("domain")
    service = config.get("service") or input_data.get("service")
    entity_id = config.get("entity_id") or input_data.get("entity_id")
    service_data = config.get("service_data") or input_data.get("service_data") or {}

    if not domain or not service:
        raise ValueError("domain and service are required for home_assistant.call_service")

    # Build payload: merge entity_id into service_data if provided
    payload: dict = {**service_data}
    if entity_id:
        payload["entity_id"] = entity_id

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post(f"services/{domain}/{service}", json=payload)
        r.raise_for_status()
        result = r.json()

    affected = result if isinstance(result, list) else []
    log.info(
        "home_assistant.call_service",
        domain=domain,
        service=service,
        entity_id=entity_id,
        affected_states=len(affected),
    )
    return {
        "domain": domain,
        "service": service,
        "entity_id": entity_id,
        "affected_states": affected,
        "success": True,
    }
