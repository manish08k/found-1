"""
Freshdesk integration — tickets, contacts, agents, conversations.
Nodes: freshdesk.create_ticket, freshdesk.update_ticket, freshdesk.get_ticket,
       freshdesk.list_tickets, freshdesk.reply_ticket, freshdesk.get_contact,
       freshdesk.create_contact
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


def _client_info(config):
    domain = config.get("domain") or getattr(settings, "FRESHDESK_DOMAIN", "")
    api_key = config.get("api_key") or getattr(settings, "FRESHDESK_API_KEY", "")
    if not domain or not api_key:
        raise ValueError("freshdesk nodes require 'domain' and 'api_key'")
    base_url = f"https://{domain}.freshdesk.com/api/v2"
    auth = (api_key, "X")  # Freshdesk uses API key as password with any username
    return base_url, auth


@register_node("freshdesk.create_ticket")
async def freshdesk_create_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)

    payload = {
        "subject": merged.get("subject", "New Ticket"),
        "description": merged.get("description") or merged.get("body", ""),
        "email": merged.get("email"),
        "priority": int(merged.get("priority", 1)),
        "status": int(merged.get("status", 2)),
        "type": merged.get("type"),
        "tags": merged.get("tags") or [],
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/tickets", json=payload, auth=auth)
        r.raise_for_status()
        return {"ticket": r.json(), "ok": True}


@register_node("freshdesk.update_ticket")
async def freshdesk_update_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    ticket_id = merged.get("ticket_id")
    if not ticket_id:
        raise ValueError("freshdesk.update_ticket requires 'ticket_id'")

    payload = {}
    for field in ("subject", "status", "priority", "type", "tags", "group_id", "responder_id"):
        val = merged.get(field)
        if val is not None:
            payload[field] = val

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{base_url}/tickets/{ticket_id}", json=payload, auth=auth)
        r.raise_for_status()
        return {"ticket": r.json(), "ok": True}


@register_node("freshdesk.get_ticket")
async def freshdesk_get_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    ticket_id = merged.get("ticket_id")
    if not ticket_id:
        raise ValueError("freshdesk.get_ticket requires 'ticket_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/tickets/{ticket_id}", auth=auth)
        r.raise_for_status()
        return {"ticket": r.json()}


@register_node("freshdesk.list_tickets")
async def freshdesk_list_tickets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    per_page = min(int(merged.get("per_page", 30)), 100)
    params = {"per_page": per_page}
    if merged.get("filter"):
        params["filter"] = merged["filter"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/tickets", params=params, auth=auth)
        r.raise_for_status()
        tickets = r.json()

    return {"tickets": tickets, "count": len(tickets)}


@register_node("freshdesk.reply_ticket")
async def freshdesk_reply_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    ticket_id = merged.get("ticket_id")
    body = merged.get("body") or merged.get("reply", "")
    if not ticket_id:
        raise ValueError("freshdesk.reply_ticket requires 'ticket_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/tickets/{ticket_id}/reply",
            json={"body": body},
            auth=auth,
        )
        r.raise_for_status()
        return {"conversation": r.json(), "ok": True}


@register_node("freshdesk.get_contact")
async def freshdesk_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    contact_id = merged.get("contact_id")
    if not contact_id:
        raise ValueError("freshdesk.get_contact requires 'contact_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/contacts/{contact_id}", auth=auth)
        r.raise_for_status()
        return {"contact": r.json()}


@register_node("freshdesk.create_contact")
async def freshdesk_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)

    payload = {k: merged.get(k) for k in ("name", "email", "phone", "mobile", "company_id", "description")
               if merged.get(k)}
    if not payload.get("name") and not payload.get("email"):
        raise ValueError("freshdesk.create_contact requires at least 'name' or 'email'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/contacts", json=payload, auth=auth)
        r.raise_for_status()
        return {"contact": r.json(), "ok": True}
