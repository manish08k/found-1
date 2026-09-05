"""Quaderno integration — tax compliance, contacts, and invoices."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

QUADERNO_BASE = "https://quadernoapp.com/api/v1"


@register_node("quaderno.list_contacts")
async def quaderno_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Quaderno contacts.

    config:
      api_key — Quaderno API key (required, used as HTTP Basic username)
      page    — Page number (default 1)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for quaderno.list_contacts")
    page = int(config.get("page", 1))

    async with httpx.AsyncClient(base_url=QUADERNO_BASE, timeout=30) as client:
        r = await client.get("/contacts.json", auth=(api_key, ""), params={"page": page})
        r.raise_for_status()
        contacts = r.json()

    if not isinstance(contacts, list):
        contacts = []
    log.info("quaderno.list_contacts", count=len(contacts), page=page)
    return {"contacts": contacts, "count": len(contacts), "page": page}


@register_node("quaderno.create_contact")
async def quaderno_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Quaderno contact.

    config/input_data:
      api_key      — Quaderno API key (required)
      first_name   — First name (required)
      last_name    — Last name (required)
      email        — Email address (required)
      contact_type — Contact type (default "individual")
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    first_name = config.get("first_name") or input_data.get("first_name")
    last_name = config.get("last_name") or input_data.get("last_name")
    email = config.get("email") or input_data.get("email")

    if not api_key:
        raise ValueError("api_key is required for quaderno.create_contact")
    if not first_name:
        raise ValueError("first_name is required for quaderno.create_contact")
    if not last_name:
        raise ValueError("last_name is required for quaderno.create_contact")
    if not email:
        raise ValueError("email is required for quaderno.create_contact")

    contact_type = config.get("contact_type", "individual")
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "contact_type": contact_type,
    }

    async with httpx.AsyncClient(base_url=QUADERNO_BASE, timeout=30) as client:
        r = await client.post("/contacts.json", auth=(api_key, ""), json=payload)
        r.raise_for_status()
        contact = r.json()

    log.info("quaderno.create_contact", contact_id=contact.get("id"), email=email)
    return {"contact": contact, "id": contact.get("id"), "email": email}


@register_node("quaderno.list_invoices")
async def quaderno_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Quaderno invoices.

    config:
      api_key — Quaderno API key (required)
      page    — Page number (default 1)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for quaderno.list_invoices")
    page = int(config.get("page", 1))

    async with httpx.AsyncClient(base_url=QUADERNO_BASE, timeout=30) as client:
        r = await client.get("/invoices.json", auth=(api_key, ""), params={"page": page})
        r.raise_for_status()
        invoices = r.json()

    if not isinstance(invoices, list):
        invoices = []
    log.info("quaderno.list_invoices", count=len(invoices), page=page)
    return {"invoices": invoices, "count": len(invoices), "page": page}


@register_node("quaderno.create_invoice")
async def quaderno_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Quaderno invoice.

    config/input_data:
      api_key     — Quaderno API key (required)
      contact_id  — Contact ID (required)
      currency    — Currency code (default "USD")
      description — Line item description (required)
      unit_price  — Unit price (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    description = config.get("description") or input_data.get("description")
    unit_price = config.get("unit_price") or input_data.get("unit_price")

    if not api_key:
        raise ValueError("api_key is required for quaderno.create_invoice")
    if not contact_id:
        raise ValueError("contact_id is required for quaderno.create_invoice")
    if not description:
        raise ValueError("description is required for quaderno.create_invoice")
    if not unit_price:
        raise ValueError("unit_price is required for quaderno.create_invoice")

    currency = config.get("currency", "USD")
    payload = {
        "contact_id": contact_id,
        "currency": currency,
        "items_attributes": [
            {"description": description, "quantity": 1, "unit_price": float(unit_price)}
        ],
    }

    async with httpx.AsyncClient(base_url=QUADERNO_BASE, timeout=30) as client:
        r = await client.post("/invoices.json", auth=(api_key, ""), json=payload)
        r.raise_for_status()
        invoice = r.json()

    log.info("quaderno.create_invoice", invoice_id=invoice.get("id"), contact_id=contact_id)
    return {"invoice": invoice, "id": invoice.get("id"), "status": invoice.get("state")}
