"""
QuickBooks Online integration.

Credential fields:
  - access_token: OAuth2 Bearer token
  - realm_id: Company ID
  - sandbox: Boolean, use sandbox endpoint if true

Auth: Authorization: Bearer {access_token}
Base URL (live):    https://quickbooks.api.intuit.com/v3/company/{realm_id}
Base URL (sandbox): https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}

QuickBooks uses a SQL-like query language: POST /query?query=SELECT * FROM Invoice
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    realm_id = creds.get("realm_id")
    sandbox = creds.get("sandbox", False)
    if isinstance(sandbox, str):
        sandbox = sandbox.lower() in ("true", "1", "yes")
    if not access_token:
        raise ValueError("QuickBooks credential is missing 'access_token'")
    if not realm_id:
        raise ValueError("QuickBooks credential is missing 'realm_id'")
    if sandbox:
        base_url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}"
    else:
        base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
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
        raise ValueError(f"QuickBooks API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by querying the CompanyInfo entity."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/companyinfo/me", params={"minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Query (generic SQL-like)
# ---------------------------------------------------------------------------

@register_node("quickbooks.query")
async def quickbooks_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /query — run a QuickBooks SQL-like query."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("quickbooks.query requires 'query'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/query", params={"query": query, "minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@register_node("quickbooks.create_invoice")
async def quickbooks_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /invoice — create an invoice."""
    line = config.get("Line") or input_data.get("Line")
    customer_ref = config.get("CustomerRef") or input_data.get("CustomerRef")
    if not line or not customer_ref:
        raise ValueError("quickbooks.create_invoice requires 'Line' and 'CustomerRef'")
    body: dict = {"Line": line, "CustomerRef": customer_ref}
    for field in ("DueDate", "BillEmail", "CurrencyRef"):
        v = config.get(field) or input_data.get(field)
        if v:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/invoice", json=body, params={"minorversion": "65"})
    return _check(r)


@register_node("quickbooks.get_invoice")
async def quickbooks_get_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /invoice/{id} — get an invoice by ID."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("quickbooks.get_invoice requires 'invoice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/invoice/{invoice_id}", params={"minorversion": "65"})
    return _check(r)


@register_node("quickbooks.list_invoices")
async def quickbooks_list_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /query — list invoices via SQL query."""
    max_results = config.get("max_results") or input_data.get("max_results", 100)
    start_position = config.get("start_position") or input_data.get("start_position", 1)
    query = f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results}"
    async with await _client(credential_id, db) as client:
        r = await client.get("/query", params={"query": query, "minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("quickbooks.create_customer")
async def quickbooks_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /customer — create a customer."""
    display_name = config.get("DisplayName") or input_data.get("DisplayName")
    if not display_name:
        raise ValueError("quickbooks.create_customer requires 'DisplayName'")
    body: dict = {"DisplayName": display_name}
    for field in ("GivenName", "FamilyName", "CompanyName", "PrimaryEmailAddr", "PrimaryPhone"):
        v = config.get(field) or input_data.get(field)
        if v:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/customer", json=body, params={"minorversion": "65"})
    return _check(r)


@register_node("quickbooks.get_customer")
async def quickbooks_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customer/{id} — get a customer by ID."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("quickbooks.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customer/{customer_id}", params={"minorversion": "65"})
    return _check(r)


@register_node("quickbooks.list_customers")
async def quickbooks_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /query — list customers via SQL query."""
    max_results = config.get("max_results") or input_data.get("max_results", 100)
    start_position = config.get("start_position") or input_data.get("start_position", 1)
    query = f"SELECT * FROM Customer STARTPOSITION {start_position} MAXRESULTS {max_results}"
    async with await _client(credential_id, db) as client:
        r = await client.get("/query", params={"query": query, "minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@register_node("quickbooks.create_payment")
async def quickbooks_create_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /payment — create a payment."""
    total_amt = config.get("TotalAmt") or input_data.get("TotalAmt")
    customer_ref = config.get("CustomerRef") or input_data.get("CustomerRef")
    if total_amt is None or not customer_ref:
        raise ValueError("quickbooks.create_payment requires 'TotalAmt' and 'CustomerRef'")
    body: dict = {"TotalAmt": float(total_amt), "CustomerRef": customer_ref}
    line = config.get("Line") or input_data.get("Line")
    if line:
        body["Line"] = line
    async with await _client(credential_id, db) as client:
        r = await client.post("/payment", json=body, params={"minorversion": "65"})
    return _check(r)


@register_node("quickbooks.list_payments")
async def quickbooks_list_payments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /query — list payments via SQL query."""
    max_results = config.get("max_results") or input_data.get("max_results", 100)
    query = f"SELECT * FROM Payment MAXRESULTS {max_results}"
    async with await _client(credential_id, db) as client:
        r = await client.get("/query", params={"query": query, "minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@register_node("quickbooks.list_accounts")
async def quickbooks_list_accounts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /query — list chart of accounts."""
    max_results = config.get("max_results") or input_data.get("max_results", 100)
    query = f"SELECT * FROM Account MAXRESULTS {max_results}"
    async with await _client(credential_id, db) as client:
        r = await client.get("/query", params={"query": query, "minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------

@register_node("quickbooks.create_bill")
async def quickbooks_create_bill(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /bill — create a bill."""
    line = config.get("Line") or input_data.get("Line")
    vendor_ref = config.get("VendorRef") or input_data.get("VendorRef")
    if not line or not vendor_ref:
        raise ValueError("quickbooks.create_bill requires 'Line' and 'VendorRef'")
    body: dict = {"Line": line, "VendorRef": vendor_ref}
    async with await _client(credential_id, db) as client:
        r = await client.post("/bill", json=body, params={"minorversion": "65"})
    return _check(r)


@register_node("quickbooks.list_bills")
async def quickbooks_list_bills(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /query — list bills via SQL query."""
    max_results = config.get("max_results") or input_data.get("max_results", 100)
    query = f"SELECT * FROM Bill MAXRESULTS {max_results}"
    async with await _client(credential_id, db) as client:
        r = await client.get("/query", params={"query": query, "minorversion": "65"})
    return _check(r)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@register_node("quickbooks.get_profit_and_loss")
async def quickbooks_get_profit_and_loss(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /reports/ProfitAndLoss — retrieve profit and loss report."""
    params: dict = {"minorversion": "65"}
    start_date = config.get("start_date") or input_data.get("start_date")
    if start_date:
        params["start_date"] = start_date
    end_date = config.get("end_date") or input_data.get("end_date")
    if end_date:
        params["end_date"] = end_date
    date_macro = config.get("date_macro") or input_data.get("date_macro")
    if date_macro:
        params["date_macro"] = date_macro
    async with await _client(credential_id, db) as client:
        r = await client.get("/reports/ProfitAndLoss", params=params)
    return _check(r)
