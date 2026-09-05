"""Dropcontact integration — contact enrichment via the Dropcontact batch API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DROPCONTACT_BASE = "https://api.dropcontact.com/batch"


def _api_key(config: dict) -> str:
    key = config.get("api_key") or ""
    if not key:
        raise ValueError("dropcontact nodes require 'api_key' in config")
    return key


@register_node("dropcontact.enrich_contact")
async def dropcontact_enrich_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich a single contact via the Dropcontact batch API.

    Submits a one-contact batch and returns the request ID for polling.

    config:
      api_key    — Dropcontact API key (sent as X-Access-Token header)
      email      — contact email address (required)
      first_name — optional first name
      last_name  — optional last name
      company    — optional company name
    """
    merged = {**config, **input_data}
    email = merged.get("email")
    if not email:
        raise ValueError("dropcontact.enrich_contact requires 'email'")
    contact: dict = {"email": email}
    for field in ("first_name", "last_name", "company"):
        val = merged.get(field)
        if val:
            contact[field] = val
    payload = {"data": [contact], "siren": True, "language": "en"}
    headers = {
        "X-Access-Token": _api_key(merged),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(DROPCONTACT_BASE, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    request_id = data.get("request_id")
    log.info("dropcontact.enrich_contact", email=email, request_id=request_id)
    return {"request_id": request_id, "status": data.get("status"), "ok": True, "response": data}


@register_node("dropcontact.get_request_status")
async def dropcontact_get_request_status(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Poll the status (and enriched results) of a Dropcontact batch request.

    config:
      api_key    — Dropcontact API key
      request_id — request ID returned by dropcontact.enrich_contact
    """
    merged = {**config, **input_data}
    request_id = merged.get("request_id")
    if not request_id:
        raise ValueError("dropcontact.get_request_status requires 'request_id'")
    headers = {
        "X-Access-Token": _api_key(merged),
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DROPCONTACT_BASE}/{request_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    status = data.get("status") or data.get("request_status")
    contacts = data.get("data", [])
    log.info("dropcontact.get_request_status", request_id=request_id, status=status)
    return {"request_id": request_id, "status": status, "contacts": contacts, "response": data}
