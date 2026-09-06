"""ClearoutPhone phone validation (Activepieces piece name) — handler for clearoutphone_ap integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.clearoutphone.io/v1"


@register_node("clearoutphone_ap.validate_phone")
async def clearoutphone_ap_validate_phone(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate a phone number.

    config/input_data:
      api_key — API key or token (required)
      phone_number — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    phone_number = merged.get("phone_number") or ""
    if not phone_number:
        raise ValueError("phone_number required for clearoutphone_ap.validate_phone")
    payload = {"phone_number": phone_number}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/phonenumber/validate", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("clearoutphone_ap.validate_phone")
    return {"data": data}

@register_node("clearoutphone_ap.bulk_validate")
async def clearoutphone_ap_bulk_validate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Bulk validate phone numbers.

    config/input_data:
      api_key — API key or token (required)
      phone_numbers — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    phone_numbers = merged.get("phone_numbers") or ""
    if not phone_numbers:
        raise ValueError("phone_numbers required for clearoutphone_ap.bulk_validate")
    payload = {"phone_numbers": phone_numbers}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/phonenumber/bulk", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("clearoutphone_ap.bulk_validate")
    return {"data": data}
