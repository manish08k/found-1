"""Zammad integration — helpdesk tickets and user management."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _zammad_headers(merged: dict) -> dict:
    """Build Zammad auth headers — token preferred over Basic auth."""
    if token := merged.get("token"):
        return {"Authorization": f"Token token={token}", "Content-Type": "application/json"}
    email = merged.get("email", "")
    password = merged.get("password", "")
    creds = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


def _zammad_base(merged: dict) -> str:
    host = merged.get("host", "").rstrip("/")
    return f"{host}/api/v1"


@register_node("zammad.list_tickets")
async def zammad_list_tickets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Zammad tickets with pagination.

    config:
      host  — Zammad instance hostname e.g. https://helpdesk.example.com (required)
      token — API token (preferred) OR email+password
      page  — page number (default 1)
    """
    merged = {**config, **input_data}
    page = int(merged.get("page", 1))

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.get(
            "/tickets",
            headers=_zammad_headers(merged),
            params={"page": page, "per_page": 25},
        )
        r.raise_for_status()
        tickets = r.json()

    log.info("zammad.list_tickets", page=page, count=len(tickets))
    return {"tickets": tickets, "count": len(tickets), "page": page}


@register_node("zammad.get_ticket")
async def zammad_get_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Zammad ticket by ID.

    config:
      host      — Zammad instance hostname (required)
      token     — API token OR email+password
      ticket_id — ticket ID to retrieve (required)
    """
    merged = {**config, **input_data}
    ticket_id = merged.get("ticket_id")
    if not ticket_id:
        raise ValueError("ticket_id is required for zammad.get_ticket")

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.get(f"/tickets/{ticket_id}", headers=_zammad_headers(merged))
        r.raise_for_status()
        ticket = r.json()

    log.info("zammad.get_ticket", ticket_id=ticket_id)
    return {"ticket": ticket, "ticket_id": ticket_id}


@register_node("zammad.create_ticket")
async def zammad_create_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Zammad ticket.

    config:
      host     — Zammad instance hostname (required)
      token    — API token OR email+password
      title    — ticket title (required)
      group    — group name (required)
      customer — customer login/email (required)
      article  — dict with body, sender ("Customer"), type ("note")
    """
    merged = {**config, **input_data}
    title = merged.get("title")
    group = merged.get("group")
    customer = merged.get("customer")
    if not title or not group or not customer:
        raise ValueError("title, group, and customer are required for zammad.create_ticket")

    article = merged.get("article") or {}
    article.setdefault("sender", "Customer")
    article.setdefault("type", "note")

    payload = {
        "title": title,
        "group": group,
        "customer": customer,
        "article": article,
    }

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.post("/tickets", headers=_zammad_headers(merged), json=payload)
        r.raise_for_status()
        ticket = r.json()

    ticket_id = ticket.get("id")
    log.info("zammad.create_ticket", ticket_id=ticket_id, title=title)
    return {"ticket": ticket, "ticket_id": ticket_id}


@register_node("zammad.update_ticket")
async def zammad_update_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Zammad ticket.

    config:
      host      — Zammad instance hostname (required)
      token     — API token OR email+password
      ticket_id — ticket ID to update (required)
      updates   — dict of fields to update (required)
    """
    merged = {**config, **input_data}
    ticket_id = merged.get("ticket_id")
    updates = merged.get("updates", {})
    if not ticket_id:
        raise ValueError("ticket_id is required for zammad.update_ticket")

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.put(
            f"/tickets/{ticket_id}",
            headers=_zammad_headers(merged),
            json=updates,
        )
        r.raise_for_status()
        ticket = r.json()

    log.info("zammad.update_ticket", ticket_id=ticket_id)
    return {"ticket": ticket, "ticket_id": ticket_id}


@register_node("zammad.list_users")
async def zammad_list_users(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Zammad users (page 1, 25 per page).

    config:
      host  — Zammad instance hostname (required)
      token — API token OR email+password
    """
    merged = {**config, **input_data}

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.get(
            "/users",
            headers=_zammad_headers(merged),
            params={"page": 1, "per_page": 25},
        )
        r.raise_for_status()
        users = r.json()

    log.info("zammad.list_users", count=len(users))
    return {"users": users, "count": len(users)}


@register_node("zammad.get_user")
async def zammad_get_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Zammad user by ID.

    config:
      host    — Zammad instance hostname (required)
      token   — API token OR email+password
      user_id — user ID to retrieve (required)
    """
    merged = {**config, **input_data}
    user_id = merged.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for zammad.get_user")

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.get(f"/users/{user_id}", headers=_zammad_headers(merged))
        r.raise_for_status()
        user = r.json()

    log.info("zammad.get_user", user_id=user_id)
    return {"user": user, "user_id": user_id}


@register_node("zammad.search_tickets")
async def zammad_search_tickets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search Zammad tickets by query string.

    config:
      host  — Zammad instance hostname (required)
      token — API token OR email+password
      query — search query string (required)
    """
    merged = {**config, **input_data}
    query = merged.get("query")
    if not query:
        raise ValueError("query is required for zammad.search_tickets")

    async with httpx.AsyncClient(base_url=_zammad_base(merged), timeout=30) as client:
        r = await client.get(
            "/tickets/search",
            headers=_zammad_headers(merged),
            params={"query": query, "limit": 25},
        )
        r.raise_for_status()
        data = r.json()

    tickets = data.get("tickets_count") and data or data
    log.info("zammad.search_tickets", query=query)
    return {"results": data, "query": query}
