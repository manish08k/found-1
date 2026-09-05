"""SyncroMSP integration — IT management (API key header auth)."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db):
    creds = await get_credential_data(credential_id, db)
    subdomain = creds["subdomain"]
    api_key = creds["api_key"]
    base_url = f"https://{subdomain}.syncromsp.com/api/v1/"
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=30,
    )
    return client, subdomain


@register_node("syncromsp.list_tickets")
async def syncromsp_list_tickets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page = config.get("page", 1)
    status = config.get("status") or input_data.get("status")
    customer_id = config.get("customer_id") or input_data.get("customer_id")

    params: dict = {"page": page}
    if status:
        params["status"] = status
    if customer_id:
        params["customer_id"] = customer_id

    log.info("syncromsp.list_tickets", page=page, status=status)
    client, subdomain = await _client(credential_id, db)
    async with client as c:
        r = await c.get("tickets", params=params)
        r.raise_for_status()
        data = r.json()

    return {"tickets": data.get("tickets", data), "subdomain": subdomain}


@register_node("syncromsp.create_ticket")
async def syncromsp_create_ticket(config: dict, input_data: dict, credential_id: str, db) -> dict:
    subject = config.get("subject") or input_data.get("subject", "")
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    problem_type = config.get("problem_type") or input_data.get("problem_type", "")
    status = config.get("status") or input_data.get("status", "New")
    priority = config.get("priority") or input_data.get("priority", "Medium")
    body = config.get("body") or input_data.get("body", "")

    payload: dict = {
        "subject": subject,
        "problem_type": problem_type,
        "status": status,
        "priority": priority,
        "body": body,
    }
    if customer_id:
        payload["customer_id"] = customer_id

    log.info("syncromsp.create_ticket", subject=subject, status=status)
    client, subdomain = await _client(credential_id, db)
    async with client as c:
        r = await c.post("tickets", json={"ticket": payload})
        r.raise_for_status()
        data = r.json()

    ticket = data.get("ticket", data)
    return {"ticket_id": ticket.get("id"), "subject": ticket.get("subject"), "status": ticket.get("status")}


@register_node("syncromsp.list_customers")
async def syncromsp_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page = config.get("page", 1)
    query = config.get("query") or input_data.get("query")

    params: dict = {"page": page}
    if query:
        params["q"] = query

    log.info("syncromsp.list_customers", page=page)
    client, subdomain = await _client(credential_id, db)
    async with client as c:
        r = await c.get("customers", params=params)
        r.raise_for_status()
        data = r.json()

    return {"customers": data.get("customers", data), "subdomain": subdomain}


@register_node("syncromsp.create_customer")
async def syncromsp_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    firstname = config.get("firstname") or input_data.get("firstname", "")
    lastname = config.get("lastname") or input_data.get("lastname", "")
    email = config.get("email") or input_data.get("email", "")
    phone = config.get("phone") or input_data.get("phone", "")
    address = config.get("address") or input_data.get("address", "")
    city = config.get("city") or input_data.get("city", "")
    state = config.get("state") or input_data.get("state", "")
    zip_code = config.get("zip") or input_data.get("zip", "")

    payload = {
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
    }

    log.info("syncromsp.create_customer", email=email)
    client, subdomain = await _client(credential_id, db)
    async with client as c:
        r = await c.post("customers", json={"customer": payload})
        r.raise_for_status()
        data = r.json()

    customer = data.get("customer", data)
    return {
        "customer_id": customer.get("id"),
        "firstname": customer.get("firstname"),
        "lastname": customer.get("lastname"),
        "email": customer.get("email"),
    }
