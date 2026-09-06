"""FreeAgent integration — accounting and invoicing for freelancers."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://api.freeagent.com/v2"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("free_agent.create_invoice")
async def free_agent_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/invoices", json={"invoice": {
            "contact": merged.get("contact_url", ""),
            "dated_on": merged.get("dated_on", ""),
            "due_on": merged.get("due_on", ""),
            "invoice_items": merged.get("items", []),
        }})
        r.raise_for_status()
    return r.json()


@register_node("free_agent.get_contacts")
async def free_agent_get_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/contacts")
        r.raise_for_status()
    return {"contacts": r.json().get("contacts", [])}
