"""Gorgias — ecommerce customer support integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _client(config: dict) -> httpx.AsyncClient:
    domain = config.get("domain", "")
    email = config.get("email", "")
    api_key = config.get("api_key", "")
    base_url = f"https://{domain}.gorgias.com/api"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(email, api_key),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("gorgias.list_tickets")
async def gorgias_list_tickets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tickets from Gorgias.

    config:
      domain  — Gorgias subdomain (e.g. "mystore")
      email   — account email for HTTP Basic auth
      api_key — Gorgias API key for HTTP Basic auth
      limit   — number of tickets to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with _client(config) as client:
        r = await client.get("/tickets", params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    tickets = data.get("data", data if isinstance(data, list) else [])
    log.info("gorgias.list_tickets", count=len(tickets))
    return {"tickets": tickets, "count": len(tickets)}


@register_node("gorgias.get_ticket")
async def gorgias_get_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Gorgias ticket by ID.

    config/input_data:
      domain  — Gorgias subdomain
      email   — account email
      api_key — Gorgias API key
      id      — ticket ID (required)
    """
    ticket_id = config.get("id") or input_data.get("id")
    if not ticket_id:
        raise ValueError("id is required for gorgias.get_ticket")

    async with _client(config) as client:
        r = await client.get(f"/tickets/{ticket_id}")
        r.raise_for_status()
        ticket = r.json()

    log.info("gorgias.get_ticket", ticket_id=ticket_id)
    return {"ticket": ticket, "id": ticket_id}


@register_node("gorgias.create_ticket")
async def gorgias_create_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new ticket in Gorgias.

    config/input_data:
      domain  — Gorgias subdomain
      email   — account email
      api_key — Gorgias API key
      customer_email — customer email address (required)
      body    — ticket message body HTML (required)
    """
    customer_email = config.get("customer_email") or input_data.get("customer_email")
    body = config.get("body") or input_data.get("body")

    if not customer_email:
        raise ValueError("customer_email is required for gorgias.create_ticket")
    if not body:
        raise ValueError("body is required for gorgias.create_ticket")

    payload = {
        "customer": {"email": customer_email},
        "messages": [
            {
                "channel": "email",
                "via": "api",
                "body_html": body,
                "from_agent": False,
            }
        ],
    }

    async with _client(config) as client:
        r = await client.post("/tickets", json=payload)
        r.raise_for_status()
        ticket = r.json()

    log.info("gorgias.create_ticket", customer_email=customer_email)
    return {"ticket": ticket, "id": ticket.get("id")}


@register_node("gorgias.list_customers")
async def gorgias_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers from Gorgias.

    config:
      domain  — Gorgias subdomain
      email   — account email
      api_key — Gorgias API key
      limit   — number of customers to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with _client(config) as client:
        r = await client.get("/customers", params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    customers = data.get("data", data if isinstance(data, list) else [])
    log.info("gorgias.list_customers", count=len(customers))
    return {"customers": customers, "count": len(customers)}
