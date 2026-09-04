"""
Freshservice integration.

Credential fields:
  - api_key: Freshservice API key
  - domain: e.g. "mycompany.freshservice.com"

Auth: HTTP Basic with api_key + "X"
Base URL: https://{domain}/api/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    domain = creds.get("domain", "").rstrip("/")
    if not api_key:
        raise ValueError("Freshservice credential is missing 'api_key'")
    if not domain:
        raise ValueError("Freshservice credential is missing 'domain'")
    base_url = f"https://{domain}/api/v2"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(api_key, "X"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Freshservice API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by listing tickets."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/tickets", params={"per_page": 1})
    return _check(r)


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

@register_node("freshservice.list_tickets")
async def freshservice_list_tickets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tickets — list tickets."""
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    filter_name = config.get("filter") or input_data.get("filter")
    if filter_name:
        params["filter"] = filter_name
    order_type = config.get("order_type") or input_data.get("order_type")
    if order_type:
        params["order_type"] = order_type
    async with await _client(credential_id, db) as client:
        r = await client.get("/tickets", params=params)
    return _check(r)


@register_node("freshservice.get_ticket")
async def freshservice_get_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tickets/{id} — get a ticket by ID."""
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    if not ticket_id:
        raise ValueError("freshservice.get_ticket requires 'ticket_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/tickets/{ticket_id}")
    return _check(r)


@register_node("freshservice.create_ticket")
async def freshservice_create_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tickets — create a new ticket."""
    subject = config.get("subject") or input_data.get("subject")
    email = config.get("email") or input_data.get("email")
    description = config.get("description") or input_data.get("description")
    if not subject or not email:
        raise ValueError("freshservice.create_ticket requires 'subject' and 'email'")
    body: dict = {"subject": subject, "email": email}
    if description:
        body["description"] = description
    for field in ("priority", "status", "source", "category", "group_id", "responder_id"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/tickets", json=body)
    return _check(r)


@register_node("freshservice.update_ticket")
async def freshservice_update_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /tickets/{id} — update a ticket."""
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    if not ticket_id:
        raise ValueError("freshservice.update_ticket requires 'ticket_id'")
    body: dict = {}
    for field in ("subject", "description", "priority", "status", "group_id", "responder_id", "category"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/tickets/{ticket_id}", json=body)
    return _check(r)


@register_node("freshservice.delete_ticket")
async def freshservice_delete_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /tickets/{id} — delete a ticket."""
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    if not ticket_id:
        raise ValueError("freshservice.delete_ticket requires 'ticket_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/tickets/{ticket_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

@register_node("freshservice.list_agents")
async def freshservice_list_agents(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /agents — list agents."""
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/agents", params=params)
    return _check(r)


@register_node("freshservice.get_agent")
async def freshservice_get_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /agents/{id} — get an agent by ID."""
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    if not agent_id:
        raise ValueError("freshservice.get_agent requires 'agent_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/agents/{agent_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Requesters
# ---------------------------------------------------------------------------

@register_node("freshservice.list_requesters")
async def freshservice_list_requesters(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /requesters — list requesters."""
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/requesters", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------

@register_node("freshservice.list_problems")
async def freshservice_list_problems(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /problems — list problems."""
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/problems", params=params)
    return _check(r)


@register_node("freshservice.create_problem")
async def freshservice_create_problem(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /problems — create a new problem."""
    subject = config.get("subject") or input_data.get("subject")
    email = config.get("email") or input_data.get("email")
    if not subject or not email:
        raise ValueError("freshservice.create_problem requires 'subject' and 'email'")
    body: dict = {"subject": subject, "email": email}
    description = config.get("description") or input_data.get("description")
    if description:
        body["description_html"] = description
    for field in ("priority", "status", "category", "due_date"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/problems", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@register_node("freshservice.list_assets")
async def freshservice_list_assets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /assets — list assets."""
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/assets", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@register_node("freshservice.create_note")
async def freshservice_create_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tickets/{ticket_id}/notes — add a note to a ticket."""
    ticket_id = config.get("ticket_id") or input_data.get("ticket_id")
    body_text = config.get("body") or input_data.get("body")
    if not ticket_id or not body_text:
        raise ValueError("freshservice.create_note requires 'ticket_id' and 'body'")
    note_body: dict = {"body": body_text}
    private = config.get("private")
    if private is None:
        private = input_data.get("private", False)
    note_body["private"] = bool(private)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/tickets/{ticket_id}/notes", json=note_body)
    return _check(r)
