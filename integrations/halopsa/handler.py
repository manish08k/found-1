"""HaloPSA integration — tickets, clients, IT service management."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

# In-memory token cache keyed by credential_id to avoid hammering the token endpoint
_token_cache: dict[str, dict] = {}


async def _get_halo_token(creds: dict) -> str:
    """Obtain a client_credentials access token from HaloPSA.

    Credential fields:
      client_id     — HaloPSA application client ID
      client_secret — HaloPSA application client secret
      tenant        — HaloPSA tenant subdomain (used to build token URL)
      base_url      — HaloPSA base URL (e.g. https://yourco.halopsa.com)
      scope         — optional scope (default: 'all')
    """
    import time as _time

    client_id = creds.get("client_id", "")
    client_secret = creds.get("client_secret", "")
    base_url = creds.get("base_url", "").rstrip("/")
    tenant = creds.get("tenant", "")
    scope = creds.get("scope", "all")

    if not base_url and tenant:
        base_url = f"https://{tenant}.halopsa.com"
    if not base_url:
        raise ValueError("HaloPSA credential must supply base_url or tenant")

    token_url = f"{base_url}/auth/token"

    cache_key = f"{client_id}:{base_url}"
    cached = _token_cache.get(cache_key)
    if cached and cached.get("expires_at", 0) > _time.time() + 60:
        return cached["access_token"]

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        token_data = r.json()

    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 3600)
    _token_cache[cache_key] = {
        "access_token": access_token,
        "expires_at": _time.time() + expires_in,
    }
    log.info("halopsa.token_obtained", base_url=base_url, expires_in=expires_in)
    return access_token


@register_node("halopsa.list_tickets")
async def halopsa_list_tickets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List HaloPSA tickets with optional filtering.

    config:
      status_id   — filter by ticket status ID (optional)
      client_id   — filter by client ID (optional)
      agent_id    — filter by assigned agent ID (optional)
      category    — filter by ticket category (optional)
      page_size   — results per page (default 50)
      page_no     — page number starting from 1 (default 1)
      search      — search string (optional)
    """
    creds = await get_credential_data(credential_id, db)
    token = await _get_halo_token(creds)
    base_url = creds.get("base_url", "").rstrip("/")
    if not base_url and creds.get("tenant"):
        base_url = f"https://{creds['tenant']}.halopsa.com"

    params: dict = {
        "pagesize": int(config.get("page_size", 50)),
        "page_no": int(config.get("page_no", 1)),
    }
    for key, param in [
        ("status_id", "status_id"),
        ("client_id", "client_id"),
        ("agent_id", "agent_id"),
        ("category", "category"),
        ("search", "search"),
    ]:
        val = config.get(key) or input_data.get(key)
        if val:
            params[param] = val

    async with httpx.AsyncClient(
        base_url=f"{base_url}/api/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get("tickets", params=params)
        r.raise_for_status()
        data = r.json()

    tickets = data.get("tickets", data if isinstance(data, list) else [])
    total = data.get("record_count", len(tickets))
    log.info("halopsa.list_tickets", count=len(tickets), total=total)
    return {
        "tickets": tickets,
        "count": len(tickets),
        "total": total,
        "page_no": params["page_no"],
    }


@register_node("halopsa.create_ticket")
async def halopsa_create_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new HaloPSA ticket.

    config/input_data:
      summary     — ticket summary/title (required)
      details     — ticket details/description
      client_id   — client ID to associate the ticket with
      site_id     — site ID
      user_id     — end-user ID
      agent_id    — assigned agent ID
      status_id   — initial status ID (default 1 — New)
      priority_id — priority ID (default 1)
      tickettype_id — ticket type ID (default 1)
    """
    creds = await get_credential_data(credential_id, db)
    token = await _get_halo_token(creds)
    base_url = creds.get("base_url", "").rstrip("/")
    if not base_url and creds.get("tenant"):
        base_url = f"https://{creds['tenant']}.halopsa.com"

    summary = config.get("summary") or input_data.get("summary", "")
    if not summary:
        raise ValueError("summary is required for halopsa.create_ticket")

    payload = {
        "summary": summary,
        "details": config.get("details") or input_data.get("details", ""),
        "status_id": int(config.get("status_id") or input_data.get("status_id", 1)),
        "priority_id": int(config.get("priority_id") or input_data.get("priority_id", 1)),
        "tickettype_id": int(config.get("tickettype_id") or input_data.get("tickettype_id", 1)),
    }

    for key in ("client_id", "site_id", "user_id", "agent_id"):
        val = config.get(key) or input_data.get(key)
        if val:
            payload[key] = int(val)

    async with httpx.AsyncClient(
        base_url=f"{base_url}/api/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post("tickets", json=[payload])
        r.raise_for_status()
        data = r.json()

    ticket = data[0] if isinstance(data, list) and data else data
    ticket_id = ticket.get("id")
    log.info("halopsa.create_ticket", ticket_id=ticket_id, summary=summary)
    return {
        "ticket_id": ticket_id,
        "summary": summary,
        "status_id": payload["status_id"],
        "ticket": ticket,
    }


@register_node("halopsa.update_ticket")
async def halopsa_update_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing HaloPSA ticket.

    config/input_data:
      ticket_id   — ID of the ticket to update (required)
      summary     — new summary (optional)
      details     — new details/description (optional)
      status_id   — new status ID (optional)
      priority_id — new priority ID (optional)
      agent_id    — reassign to agent ID (optional)
      note        — add a note/action to the ticket (optional)
    """
    creds = await get_credential_data(credential_id, db)
    token = await _get_halo_token(creds)
    base_url = creds.get("base_url", "").rstrip("/")
    if not base_url and creds.get("tenant"):
        base_url = f"https://{creds['tenant']}.halopsa.com"

    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    if not ticket_id:
        raise ValueError("ticket_id is required for halopsa.update_ticket")

    payload: dict = {"id": int(ticket_id)}
    for key in ("summary", "details", "status_id", "priority_id", "agent_id"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            payload[key] = int(val) if key.endswith("_id") else val

    note = config.get("note") or input_data.get("note")
    if note:
        payload["actions"] = [{"note": note, "actionisoutcome": False}]

    async with httpx.AsyncClient(
        base_url=f"{base_url}/api/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post("tickets", json=[payload])
        r.raise_for_status()
        data = r.json()

    ticket = data[0] if isinstance(data, list) and data else data
    log.info("halopsa.update_ticket", ticket_id=ticket_id)
    return {
        "ticket_id": int(ticket_id),
        "updated": True,
        "ticket": ticket,
    }


@register_node("halopsa.list_clients")
async def halopsa_list_clients(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List HaloPSA clients/customers.

    config:
      search     — filter by name or partial match (optional)
      active     — bool, only return active clients (default True)
      page_size  — results per page (default 50)
      page_no    — page number starting at 1 (default 1)
    """
    creds = await get_credential_data(credential_id, db)
    token = await _get_halo_token(creds)
    base_url = creds.get("base_url", "").rstrip("/")
    if not base_url and creds.get("tenant"):
        base_url = f"https://{creds['tenant']}.halopsa.com"

    params: dict = {
        "pagesize": int(config.get("page_size", 50)),
        "page_no": int(config.get("page_no", 1)),
    }
    search = config.get("search") or input_data.get("search")
    if search:
        params["search"] = search

    active = config.get("active", True)
    if active is not None:
        params["isactive"] = "true" if active else "false"

    async with httpx.AsyncClient(
        base_url=f"{base_url}/api/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get("client", params=params)
        r.raise_for_status()
        data = r.json()

    clients = data.get("clients", data if isinstance(data, list) else [])
    total = data.get("record_count", len(clients))
    log.info("halopsa.list_clients", count=len(clients), total=total)
    return {
        "clients": clients,
        "count": len(clients),
        "total": total,
    }
