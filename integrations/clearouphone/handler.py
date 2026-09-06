"""ClearoutPhone integration — phone number verification."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CLEAROUPHONE_BASE = "https://api.clearoutphone.io/v1"


def _clearouphone_headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


@register_node("clearouphone.verify_phone")
async def clearouphone_verify_phone(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify a single phone number using ClearoutPhone.

    config:
      api_key      — ClearoutPhone API key (required)
      phone_number — phone number to verify (required)
      country_code — ISO country code hint e.g. "US" (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    phone_number = merged.get("phone_number")
    if not api_key or not phone_number:
        raise ValueError("api_key and phone_number are required for clearouphone.verify_phone")

    payload: dict = {"number": phone_number}
    if merged.get("country_code"):
        payload["country_code"] = merged["country_code"]

    async with httpx.AsyncClient(base_url=CLEAROUPHONE_BASE, timeout=30) as client:
        r = await client.post("/phone_verify/instant", headers=_clearouphone_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()

    status = data.get("data", {}).get("status", data.get("status"))
    log.info("clearouphone.verify_phone", phone_number=phone_number, status=status)
    return {"result": data, "phone_number": phone_number, "status": status}


@register_node("clearouphone.batch_verify")
async def clearouphone_batch_verify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Batch verify multiple phone numbers using ClearoutPhone.

    config:
      api_key       — ClearoutPhone API key (required)
      phone_numbers — list of phone numbers to verify (required)
      country_code  — ISO country code hint e.g. "US" (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    phone_numbers = merged.get("phone_numbers", [])
    if not api_key:
        raise ValueError("api_key is required for clearouphone.batch_verify")
    if not phone_numbers:
        raise ValueError("phone_numbers list is required for clearouphone.batch_verify")

    payload: dict = {"numbers": [{"number": n} for n in phone_numbers]}
    if merged.get("country_code"):
        for item in payload["numbers"]:
            item["country_code"] = merged["country_code"]

    async with httpx.AsyncClient(base_url=CLEAROUPHONE_BASE, timeout=60) as client:
        r = await client.post("/phone_verify/batch", headers=_clearouphone_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("clearouphone.batch_verify", count=len(phone_numbers))
    return {"result": data, "submitted_count": len(phone_numbers)}
