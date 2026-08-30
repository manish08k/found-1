"""
Xero accounting integration.

Credential fields:
  - access_token: OAuth2 Bearer token
  - refresh_token: OAuth2 refresh token (stored for reference)
  - tenant_id: Xero tenant/organisation ID

Auth: Authorization: Bearer {access_token}, Xero-tenant-id: {tenant_id}
Base URL: https://api.xero.com/api.xro/2.0
Response format: JSON (Accept: application/json)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

XERO_BASE = "https://api.xero.com/api.xro/2.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    tenant_id = creds.get("tenant_id")
    if not access_token:
        raise ValueError("Xero credential is missing 'access_token'")
    if not tenant_id:
        raise ValueError("Xero credential is missing 'tenant_id'")
    return httpx.AsyncClient(
        base_url=XERO_BASE,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Xero-tenant-id": tenant_id,
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
        raise ValueError(f"Xero API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("xero.get_contacts")
async def xero_get_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Contacts — list/filter contacts."""
    params: dict = {}
    where = config.get("where") or input_data.get("where")
    if where:
        params["where"] = where
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    include_archived = config.get("include_archived")
    if include_archived is None:
        include_archived = input_data.get("include_archived")
    if include_archived:
        params["includeArchived"] = "true"
    async with await _client(credential_id, db) as client:
        r = await client.get("/Contacts", params=params)
    return _check(r)


@register_node("xero.create_contact")
async def xero_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Contacts — create a new contact."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("xero.create_contact requires 'name'")
    contact: dict = {"Name": name}
    email = config.get("email") or input_data.get("email")
    if email:
        contact["EmailAddress"] = email
    phone = config.get("phone") or input_data.get("phone")
    if phone:
        contact["Phones"] = [{"PhoneType": "DEFAULT", "PhoneNumber": phone}]
    is_supplier = config.get("is_supplier")
    if is_supplier is None:
        is_supplier = input_data.get("is_supplier")
    if is_supplier is not None:
        contact["IsSupplier"] = bool(is_supplier)
    is_customer = config.get("is_customer")
    if is_customer is None:
        is_customer = input_data.get("is_customer")
    if is_customer is not None:
        contact["IsCustomer"] = bool(is_customer)
    addresses = config.get("addresses") or input_data.get("addresses")
    if addresses:
        contact["Addresses"] = addresses
    async with await _client(credential_id, db) as client:
        r = await client.post("/Contacts", json={"Contacts": [contact]})
    return _check(r)


@register_node("xero.update_contact")
async def xero_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Contacts/{id} — update an existing contact."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not contact_id:
        raise ValueError("xero.update_contact requires 'contact_id'")
    contact: dict = {"ContactID": contact_id}
    for src_field, xero_field in [("name", "Name"), ("email", "EmailAddress")]:
        v = config.get(src_field) or input_data.get(src_field)
        if v is not None:
            contact[xero_field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/Contacts/{contact_id}", json={"Contacts": [contact]})
    return _check(r)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@register_node("xero.get_invoices")
async def xero_get_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Invoices — list/filter invoices."""
    params: dict = {}
    status = config.get("status") or input_data.get("status")
    if status:
        params["Statuses"] = status
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if contact_id:
        params["ContactIDs"] = contact_id
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/Invoices", params=params)
    return _check(r)


@register_node("xero.create_invoice")
async def xero_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Invoices — create a new invoice (ACCREC or ACCPAY)."""
    invoice_type = config.get("type") or input_data.get("type", "ACCREC")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    line_items_raw = config.get("line_items") or input_data.get("line_items")
    if not contact_id:
        raise ValueError("xero.create_invoice requires 'contact_id'")
    if not line_items_raw:
        raise ValueError("xero.create_invoice requires 'line_items'")

    # Map user-facing keys to Xero field names
    line_items = []
    for item in line_items_raw:
        li: dict = {}
        if "description" in item:
            li["Description"] = item["description"]
        if "quantity" in item:
            li["Quantity"] = item["quantity"]
        if "unit_amount" in item:
            li["UnitAmount"] = item["unit_amount"]
        if "account_code" in item:
            li["AccountCode"] = item["account_code"]
        line_items.append(li)

    invoice: dict = {
        "Type": invoice_type,
        "Contact": {"ContactID": contact_id},
        "LineItems": line_items,
    }
    due_date = config.get("due_date") or input_data.get("due_date")
    if due_date:
        invoice["DueDate"] = due_date
    reference = config.get("reference") or input_data.get("reference")
    if reference:
        invoice["Reference"] = reference
    currency_code = config.get("currency_code") or input_data.get("currency_code")
    if currency_code:
        invoice["CurrencyCode"] = currency_code

    async with await _client(credential_id, db) as client:
        r = await client.post("/Invoices", json={"Invoices": [invoice]})
    return _check(r)


@register_node("xero.update_invoice")
async def xero_update_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Invoices/{id} — update an invoice (e.g. change status to AUTHORISED)."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("xero.update_invoice requires 'invoice_id'")
    invoice: dict = {"InvoiceID": invoice_id}
    status = config.get("status") or input_data.get("status")
    if status:
        invoice["Status"] = status
    for field in ("reference", "due_date", "currency_code"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            xero_key = {"reference": "Reference", "due_date": "DueDate", "currency_code": "CurrencyCode"}[field]
            invoice[xero_key] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/Invoices/{invoice_id}", json={"Invoices": [invoice]})
    return _check(r)


@register_node("xero.get_invoice")
async def xero_get_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Invoices/{id} — fetch a single invoice."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("xero.get_invoice requires 'invoice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/Invoices/{invoice_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@register_node("xero.create_payment")
async def xero_create_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Payments — record a payment against an invoice."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    account_id = config.get("account_id") or input_data.get("account_id")
    date = config.get("date") or input_data.get("date")
    amount = config.get("amount") or input_data.get("amount")
    if not invoice_id or not account_id or not date or amount is None:
        raise ValueError("xero.create_payment requires 'invoice_id', 'account_id', 'date', and 'amount'")
    payment = {
        "Invoice": {"InvoiceID": invoice_id},
        "Account": {"AccountID": account_id},
        "Date": date,
        "Amount": float(amount),
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/Payments", json={"Payments": [payment]})
    return _check(r)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@register_node("xero.get_accounts")
async def xero_get_accounts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Accounts — list chart-of-accounts entries."""
    params: dict = {}
    where = config.get("where") or input_data.get("where")
    if where:
        params["where"] = where
    account_type = config.get("type") or input_data.get("type")
    if account_type:
        params["Type"] = account_type
    async with await _client(credential_id, db) as client:
        r = await client.get("/Accounts", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Organisation
# ---------------------------------------------------------------------------

@register_node("xero.get_organisation")
async def xero_get_organisation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Organisation — fetch organisation details."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/Organisation")
    return _check(r)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@register_node("xero.get_reports_profit_and_loss")
async def xero_get_reports_profit_and_loss(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Reports/ProfitAndLoss — profit and loss report."""
    params: dict = {}
    from_date = config.get("from_date") or input_data.get("from_date")
    if from_date:
        params["fromDate"] = from_date
    to_date = config.get("to_date") or input_data.get("to_date")
    if to_date:
        params["toDate"] = to_date
    periods = config.get("periods") or input_data.get("periods")
    if periods:
        params["periods"] = int(periods)
    timeframe = config.get("timeframe") or input_data.get("timeframe")
    if timeframe:
        params["timeframe"] = timeframe
    async with await _client(credential_id, db) as client:
        r = await client.get("/Reports/ProfitAndLoss", params=params)
    return _check(r)


@register_node("xero.get_reports_balance_sheet")
async def xero_get_reports_balance_sheet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Reports/BalanceSheet — balance sheet report."""
    params: dict = {}
    date = config.get("date") or input_data.get("date")
    if date:
        params["date"] = date
    async with await _client(credential_id, db) as client:
        r = await client.get("/Reports/BalanceSheet", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Credit Notes
# ---------------------------------------------------------------------------

@register_node("xero.create_credit_note")
async def xero_create_credit_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /CreditNotes — create a credit note."""
    note_type = config.get("type") or input_data.get("type", "ACCRECCREDIT")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    line_items_raw = config.get("line_items") or input_data.get("line_items")
    if not contact_id:
        raise ValueError("xero.create_credit_note requires 'contact_id'")
    if not line_items_raw:
        raise ValueError("xero.create_credit_note requires 'line_items'")

    line_items = []
    for item in line_items_raw:
        li: dict = {}
        if "description" in item:
            li["Description"] = item["description"]
        if "quantity" in item:
            li["Quantity"] = item["quantity"]
        if "unit_amount" in item:
            li["UnitAmount"] = item["unit_amount"]
        if "account_code" in item:
            li["AccountCode"] = item["account_code"]
        line_items.append(li)

    credit_note = {
        "Type": note_type,
        "Contact": {"ContactID": contact_id},
        "LineItems": line_items,
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/CreditNotes", json={"CreditNotes": [credit_note]})
    return _check(r)
