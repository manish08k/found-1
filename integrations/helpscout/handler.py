"""
Help Scout customer support integration.

Credential fields:
  - api_key: Help Scout API key

Auth: HTTP Basic auth with api_key as username and "X" as password
Base URL: https://api.helpscout.net/v2
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.helpscout.net/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Help Scout credential is missing 'api_key'")
    raw = f"{api_key}:X"
    encoded = base64.b64encode(raw.encode()).decode()
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Help Scout API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@register_node("helpscout.list_conversations")
async def helpscout_list_conversations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /conversations — list conversations."""
    params = {}
    for field in ("mailboxId", "folderId", "status", "tag", "assigned_to",
                  "modifiedSince", "number", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/conversations", params=params)
    return _check(r)


@register_node("helpscout.get_conversation")
async def helpscout_get_conversation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /conversations/{conversation_id} — get a conversation by ID."""
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    if not conversation_id:
        raise ValueError("helpscout.get_conversation requires 'conversation_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/conversations/{conversation_id}")
    return _check(r)


@register_node("helpscout.create_conversation")
async def helpscout_create_conversation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /conversations — create a new conversation."""
    subject = config.get("subject") or input_data.get("subject")
    mailbox_id = config.get("mailboxId") or input_data.get("mailboxId")
    customer = config.get("customer") or input_data.get("customer")
    threads = config.get("threads") or input_data.get("threads")
    if not subject:
        raise ValueError("helpscout.create_conversation requires 'subject'")
    if not mailbox_id:
        raise ValueError("helpscout.create_conversation requires 'mailboxId'")
    if not customer:
        raise ValueError("helpscout.create_conversation requires 'customer'")
    body: dict = {
        "subject": subject,
        "mailboxId": mailbox_id,
        "customer": customer,
    }
    if threads:
        body["threads"] = threads
    for field in ("type", "status", "assignTo", "tags"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/conversations", json=body)
    return _check(r)


@register_node("helpscout.update_conversation")
async def helpscout_update_conversation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /conversations/{conversation_id} — update a conversation."""
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    if not conversation_id:
        raise ValueError("helpscout.update_conversation requires 'conversation_id'")
    body: dict = {}
    for field in ("op", "path", "value"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    # Support patch list format
    patches = config.get("patches") or input_data.get("patches")
    if patches:
        async with await _client(credential_id, db) as client:
            r = await client.patch(f"/conversations/{conversation_id}", json=patches)
    else:
        async with await _client(credential_id, db) as client:
            r = await client.patch(f"/conversations/{conversation_id}", json=[body])
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Help Scout API error {r.status_code}: {detail}")
    return {"ok": True, "conversation_id": conversation_id}


@register_node("helpscout.create_reply")
async def helpscout_create_reply(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /conversations/{conversation_id}/reply — create a reply thread."""
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    text = config.get("text") or input_data.get("text")
    if not conversation_id:
        raise ValueError("helpscout.create_reply requires 'conversation_id'")
    if not text:
        raise ValueError("helpscout.create_reply requires 'text'")
    body: dict = {"type": "reply", "text": text}
    for field in ("customer", "cc", "bcc", "attachments", "imported", "status"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/conversations/{conversation_id}/reply", json=body)
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Help Scout API error {r.status_code}: {detail}")
    return {"ok": True, "conversation_id": conversation_id}


@register_node("helpscout.list_threads")
async def helpscout_list_threads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /conversations/{conversation_id}/threads — list threads in a conversation."""
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    if not conversation_id:
        raise ValueError("helpscout.list_threads requires 'conversation_id'")
    params = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = page
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/conversations/{conversation_id}/threads", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("helpscout.list_customers")
async def helpscout_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers — list customers."""
    params = {}
    for field in ("firstName", "lastName", "email", "modifiedSince", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/customers", params=params)
    return _check(r)


@register_node("helpscout.get_customer")
async def helpscout_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers/{customer_id} — get a customer by ID."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("helpscout.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customers/{customer_id}")
    return _check(r)


@register_node("helpscout.create_customer")
async def helpscout_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /customers — create a new customer."""
    body: dict = {}
    for field in ("firstName", "lastName", "organization", "jobTitle", "background",
                  "location", "gender", "age", "emails", "phones", "social_profiles", "websites"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    if not body:
        raise ValueError("helpscout.create_customer requires at least one customer field")
    async with await _client(credential_id, db) as client:
        r = await client.post("/customers", json=body)
    return _check(r)


@register_node("helpscout.update_customer")
async def helpscout_update_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /customers/{customer_id} — update a customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("helpscout.update_customer requires 'customer_id'")
    body: dict = {}
    for field in ("firstName", "lastName", "organization", "jobTitle", "background",
                  "location", "gender", "age"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/customers/{customer_id}", json=body)
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Help Scout API error {r.status_code}: {detail}")
    return {"ok": True, "customer_id": customer_id}


# ---------------------------------------------------------------------------
# Mailboxes
# ---------------------------------------------------------------------------

@register_node("helpscout.list_mailboxes")
async def helpscout_list_mailboxes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /mailboxes — list all mailboxes."""
    params = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = page
    async with await _client(credential_id, db) as client:
        r = await client.get("/mailboxes", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Help Scout connection by listing mailboxes."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    raw = f"{api_key}:X"
    encoded = base64.b64encode(raw.encode()).decode()
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Basic {encoded}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.get("/mailboxes")
    if not r.is_success:
        raise ValueError(f"Help Scout connection failed: {r.status_code} {r.text}")
    return {"ok": True}
