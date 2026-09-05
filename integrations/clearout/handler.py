"""Clearout email verification integration — instant and bulk verification."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CLEAROUT_BASE = "https://api.clearout.io/v2"


@register_node("clearout.verify_email")
async def clearout_verify_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify a single email address using Clearout.

    config/input_data:
      api_token — Clearout API token (required)
      email     — email address to verify (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token") or merged.get("api_key") or ""
    email = merged.get("email") or ""

    if not email:
        raise ValueError("email is required for clearout.verify_email")

    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{CLEAROUT_BASE}/email_verify/instant"
    payload = {"email": email}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("clearout.verify_email", email=email, status=data.get("data", {}).get("status"))
    return {"result": data, "email": email}


@register_node("clearout.bulk_verify")
async def clearout_bulk_verify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Bulk verify a list of email addresses using Clearout.

    config/input_data:
      api_token — Clearout API token (required)
      emails    — list of email addresses to verify (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token") or merged.get("api_key") or ""
    emails = merged.get("emails") or []

    if not emails:
        raise ValueError("emails list is required for clearout.bulk_verify")

    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{CLEAROUT_BASE}/email_verify/bulk"
    payload = {"emails": emails}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("clearout.bulk_verify", count=len(emails))
    return {"result": data, "count": len(emails)}
