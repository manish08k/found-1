"""
Zendesk integration — tickets, users, search, comments, satisfaction ratings.
Nodes: zendesk.create_ticket, zendesk.update_ticket, zendesk.get_ticket,
       zendesk.list_tickets, zendesk.search, zendesk.add_comment,
       zendesk.get_user, zendesk.create_user
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


def _client(config):
    subdomain = config.get("subdomain") or getattr(settings, "ZENDESK_SUBDOMAIN", "")
    email = config.get("email") or getattr(settings, "ZENDESK_EMAIL", "")
    token = config.get("api_token") or getattr(settings, "ZENDESK_API_TOKEN", "")
    if not subdomain or not email or not token:
        raise ValueError("Zendesk requires subdomain, email, and api_token")
    base_url = f"https://{subdomain}.zendesk.com/api/v2"
    auth = (f"{email}/token", token)
    return base_url, auth


@register_node("zendesk.create_ticket")
async def zendesk_create_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_url, auth = _client({**config, **input_data})
    ticket = {
        "subject": config.get("subject") or input_data.get("subject", "New Ticket"),
        "comment": {"body": config.get("body") or input_data.get("body", "")},
        "priority": config.get("priority", "normal"),
        "type": config.get("type", "question"),
        "tags": config.get("tags") or input_data.get("tags") or [],
    }
    if config.get("requester_email") or input_data.get("requester_email"):
        ticket["requester"] = {"email": config.get("requester_email") or input_data.get("requester_email")}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/tickets.json", json={"ticket": ticket}, auth=auth)
        r.raise_for_status()
        return {"ticket": r.json()["ticket"], "ok": True}


@register_node("zendesk.update_ticket")
async def zendesk_update_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_url, auth = _client({**config, **input_data})
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    if not ticket_id:
        raise ValueError("zendesk.update_ticket requires 'ticket_id'")

    updates = {}
    for field in ("status", "priority", "subject", "tags", "assignee_id"):
        val = config.get(field) or input_data.get(field)
        if val is not None:
            updates[field] = val

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{base_url}/tickets/{ticket_id}.json", json={"ticket": updates}, auth=auth)
        r.raise_for_status()
        return {"ticket": r.json()["ticket"], "ok": True}


@register_node("zendesk.get_ticket")
async def zendesk_get_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_url, auth = _client({**config, **input_data})
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    if not ticket_id:
        raise ValueError("zendesk.get_ticket requires 'ticket_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/tickets/{ticket_id}.json", auth=auth)
        r.raise_for_status()
        return {"ticket": r.json()["ticket"]}


@register_node("zendesk.list_tickets")
async def zendesk_list_tickets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_url, auth = _client({**config, **input_data})
    status = config.get("status", "open")
    per_page = min(int(config.get("per_page", 25)), 100)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/tickets.json", params={"status": status, "per_page": per_page}, auth=auth)
        r.raise_for_status()
        data = r.json()
    return {"tickets": data.get("tickets", []), "count": data.get("count", 0)}


@register_node("zendesk.search")
async def zendesk_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_url, auth = _client({**config, **input_data})
    query = config.get("query") or input_data.get("query", "")
    if not query:
        raise ValueError("zendesk.search requires 'query'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/search.json", params={"query": query}, auth=auth)
        r.raise_for_status()
        data = r.json()
    return {"results": data.get("results", []), "count": data.get("count", 0)}


@register_node("zendesk.add_comment")
async def zendesk_add_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_url, auth = _client({**config, **input_data})
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    body = config.get("body") or input_data.get("body", "")
    public = config.get("public", True)

    if not ticket_id:
        raise ValueError("zendesk.add_comment requires 'ticket_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(
            f"{base_url}/tickets/{ticket_id}.json",
            json={"ticket": {"comment": {"body": body, "public": public}}},
            auth=auth,
        )
        r.raise_for_status()
        return {"ok": True, "ticket_id": ticket_id}
