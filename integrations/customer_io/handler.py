"""Customer.io (Activepieces variant) — handler for customer_io integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://track.customer.io/api/v1"


@register_node("customer_io.identify")
async def customer_io_identify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Identify a customer.

    config/input_data:
      api_key — API key or token (required)
      customer_id — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    customer_id = merged.get("customer_id") or ""
    if not customer_id:
        raise ValueError("customer_id required for customer_io.identify")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{BASE_URL}/customers/{customer_id}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("customer_io.identify")
    return {"data": data}

@register_node("customer_io.track_event")
async def customer_io_track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track an event.

    config/input_data:
      api_key — API key or token (required)
      customer_id — (required)
      name — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    customer_id = merged.get("customer_id") or ""
    name = merged.get("name") or ""
    if not customer_id or not name:
        raise ValueError("customer_id, name required for customer_io.track_event")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/customers/{customer_id}/events", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("customer_io.track_event")
    return {"data": data}

@register_node("customer_io.delete_customer")
async def customer_io_delete_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a customer.

    config/input_data:
      api_key — API key or token (required)
      customer_id — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    customer_id = merged.get("customer_id") or ""
    if not customer_id:
        raise ValueError("customer_id required for customer_io.delete_customer")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}/customers/{customer_id}", headers=headers)
        r.raise_for_status()
    log.info("customer_io.delete_customer")
    return {"ok": True}
