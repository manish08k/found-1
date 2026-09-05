"""Kustomer customer service CRM integration — customers and conversations."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

KUSTOMER_BASE = "https://api.kustomerapp.com/v1"


@register_node("kustomer.list_customers")
async def kustomer_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers from Kustomer.

    config/input_data:
      api_key   — Kustomer API key (required)
      page      — page number (default 1)
      page_size — results per page (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    page = int(merged.get("page", 1))
    page_size = int(merged.get("page_size", 25))

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{KUSTOMER_BASE}/customers"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"page": page, "pageSize": page_size})
        r.raise_for_status()
        data = r.json()

    customers = data.get("data", data)
    log.info("kustomer.list_customers", page=page, count=len(customers) if isinstance(customers, list) else None)
    return {"customers": customers, "page": page}


@register_node("kustomer.get_customer")
async def kustomer_get_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Kustomer customer by ID.

    config/input_data:
      api_key — Kustomer API key (required)
      id      — customer ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    customer_id = merged.get("id") or merged.get("customer_id") or ""

    if not customer_id:
        raise ValueError("id is required for kustomer.get_customer")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{KUSTOMER_BASE}/customers/{customer_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    customer = data.get("data", data)
    log.info("kustomer.get_customer", id=customer_id)
    return {"customer": customer}


@register_node("kustomer.create_customer")
async def kustomer_create_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new customer in Kustomer.

    config/input_data:
      api_key — Kustomer API key (required)
      name    — customer display name (required)
      email   — customer email address (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    name = merged.get("name") or ""
    email = merged.get("email") or ""

    if not name:
        raise ValueError("name is required for kustomer.create_customer")
    if not email:
        raise ValueError("email is required for kustomer.create_customer")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{KUSTOMER_BASE}/customers"
    payload = {
        "name": name,
        "emails": [{"email": email, "type": "home"}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    customer = data.get("data", data)
    log.info("kustomer.create_customer", name=name, email=email)
    return {"customer": customer}


@register_node("kustomer.list_conversations")
async def kustomer_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List conversations from Kustomer.

    config/input_data:
      api_key   — Kustomer API key (required)
      page      — page number (default 1)
      page_size — results per page (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    page = int(merged.get("page", 1))
    page_size = int(merged.get("page_size", 25))

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{KUSTOMER_BASE}/conversations"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"page": page, "pageSize": page_size})
        r.raise_for_status()
        data = r.json()

    conversations = data.get("data", data)
    log.info("kustomer.list_conversations", page=page, count=len(conversations) if isinstance(conversations, list) else None)
    return {"conversations": conversations, "page": page}
