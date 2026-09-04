"""
Invoice Ninja invoicing integration.

Credential fields:
  - api_key: Invoice Ninja API token
  - base_url: Self-hosted URL or https://app.invoiceninja.com

Auth: X-Api-Token header
Base URL: {base_url}/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    base_url = creds.get("base_url", "https://app.invoiceninja.com")
    if not api_key:
        raise ValueError("Invoice Ninja credential is missing 'api_key'")
    if not base_url:
        raise ValueError("Invoice Ninja credential is missing 'base_url'")
    base_url = base_url.rstrip("/")
    return httpx.AsyncClient(
        base_url=f"{base_url}/api/v1",
        headers={
            "X-Api-Token": api_key,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Invoice Ninja API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@register_node("invoiceninja.list_invoices")
async def invoiceninja_list_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /invoices — list all invoices."""
    params = {}
    for field in ("client_id", "status_id", "filter", "per_page", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/invoices", params=params)
    return _check(r)


@register_node("invoiceninja.create_invoice")
async def invoiceninja_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /invoices — create a new invoice."""
    client_id = config.get("client_id") or input_data.get("client_id")
    if not client_id:
        raise ValueError("invoiceninja.create_invoice requires 'client_id'")
    body: dict = {"client_id": client_id}
    for field in ("number", "po_number", "discount", "is_amount_discount",
                  "invoice_date", "due_date", "terms", "public_notes", "private_notes",
                  "tax_name1", "tax_rate1", "line_items", "status_id"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/invoices", json=body)
    return _check(r)


@register_node("invoiceninja.get_invoice")
async def invoiceninja_get_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /invoices/{invoice_id} — get an invoice by ID."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("invoiceninja.get_invoice requires 'invoice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/invoices/{invoice_id}")
    return _check(r)


@register_node("invoiceninja.update_invoice")
async def invoiceninja_update_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /invoices/{invoice_id} — update an invoice."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("invoiceninja.update_invoice requires 'invoice_id'")
    body: dict = {}
    for field in ("client_id", "number", "invoice_date", "due_date", "terms",
                  "public_notes", "private_notes", "line_items", "status_id"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/invoices/{invoice_id}", json=body)
    return _check(r)


@register_node("invoiceninja.delete_invoice")
async def invoiceninja_delete_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /invoices/{invoice_id} — delete an invoice."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("invoiceninja.delete_invoice requires 'invoice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/invoices/{invoice_id}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Invoice Ninja API error {r.status_code}: {detail}")
    return {"ok": True, "invoice_id": invoice_id}


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@register_node("invoiceninja.list_clients")
async def invoiceninja_list_clients(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /clients — list all clients."""
    params = {}
    for field in ("filter", "per_page", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/clients", params=params)
    return _check(r)


@register_node("invoiceninja.create_client")
async def invoiceninja_create_client(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /clients — create a new client."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("invoiceninja.create_client requires 'name'")
    body: dict = {"name": name}
    for field in ("email", "phone", "address1", "address2", "city", "state",
                  "postal_code", "country_id", "contacts", "website"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/clients", json=body)
    return _check(r)


@register_node("invoiceninja.get_client")
async def invoiceninja_get_client(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /clients/{client_id} — get a client by ID."""
    client_id = config.get("client_id") or input_data.get("client_id")
    if not client_id:
        raise ValueError("invoiceninja.get_client requires 'client_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/clients/{client_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@register_node("invoiceninja.list_products")
async def invoiceninja_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products — list all products."""
    params = {}
    for field in ("filter", "per_page", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/products", params=params)
    return _check(r)


@register_node("invoiceninja.create_product")
async def invoiceninja_create_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /products — create a new product."""
    product_key = config.get("product_key") or input_data.get("product_key")
    if not product_key:
        raise ValueError("invoiceninja.create_product requires 'product_key'")
    body: dict = {"product_key": product_key}
    for field in ("notes", "cost", "price", "quantity", "tax_name1", "tax_rate1",
                  "custom_value1", "custom_value2"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/products", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Quotes & Payments
# ---------------------------------------------------------------------------

@register_node("invoiceninja.list_quotes")
async def invoiceninja_list_quotes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /quotes — list all quotes."""
    params = {}
    for field in ("client_id", "filter", "per_page", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/quotes", params=params)
    return _check(r)


@register_node("invoiceninja.list_payments")
async def invoiceninja_list_payments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /payments — list all payments."""
    params = {}
    for field in ("client_id", "filter", "per_page", "page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/payments", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Invoice Ninja connection by fetching company info."""
    api_key = creds.get("api_key")
    base_url = creds.get("base_url", "https://app.invoiceninja.com").rstrip("/")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=f"{base_url}/api/v1",
        headers={
            "X-Api-Token": api_key,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30.0,
    ) as client:
        r = await client.get("/company_users")
    if not r.is_success:
        raise ValueError(f"Invoice Ninja connection failed: {r.status_code} {r.text}")
    return {"ok": True}
