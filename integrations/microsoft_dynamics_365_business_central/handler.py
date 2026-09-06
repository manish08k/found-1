"""Microsoft Dynamics 365 Business Central integration — companies, customers, and invoices."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BC_BASE_TEMPLATE = "https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/api/v2.0"


def _bc_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _bc_base(tenant_id: str) -> str:
    return BC_BASE_TEMPLATE.format(tenant_id=tenant_id)


@register_node("dynamics_365_bc.list_companies")
async def dynamics_365_bc_list_companies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List companies available in Dynamics 365 Business Central.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      tenant_id    — Azure AD tenant ID (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    tenant_id = merged.get("tenant_id")
    if not tenant_id:
        raise ValueError("tenant_id is required for dynamics_365_bc.list_companies")

    base = _bc_base(tenant_id)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.get("/companies", headers=_bc_headers(access_token))
        r.raise_for_status()
        data = r.json()

    companies = data.get("value", [])
    log.info("dynamics_365_bc.list_companies", tenant_id=tenant_id, count=len(companies))
    return {"companies": companies, "count": len(companies)}


@register_node("dynamics_365_bc.list_customers")
async def dynamics_365_bc_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers in a Dynamics 365 Business Central company.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      tenant_id    — Azure AD tenant ID (required)
      company_id   — Business Central company ID (required)
      top          — maximum number of records to return (optional)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    tenant_id = merged.get("tenant_id")
    company_id = merged.get("company_id")
    if not tenant_id:
        raise ValueError("tenant_id is required for dynamics_365_bc.list_customers")
    if not company_id:
        raise ValueError("company_id is required for dynamics_365_bc.list_customers")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    base = _bc_base(tenant_id)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.get(
            f"/companies({company_id})/customers",
            headers=_bc_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    customers = data.get("value", [])
    log.info("dynamics_365_bc.list_customers", company_id=company_id, count=len(customers))
    return {"customers": customers, "count": len(customers)}


@register_node("dynamics_365_bc.create_customer")
async def dynamics_365_bc_create_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new customer in Dynamics 365 Business Central.

    config/input_data:
      access_token      — Microsoft OAuth2 bearer token (required)
      tenant_id         — Azure AD tenant ID (required)
      company_id        — Business Central company ID (required)
      display_name      — customer display name (required)
      email             — customer email address (optional)
      phone_number      — customer phone number (optional)
      address           — address object with city, street, etc. (optional)
      currency_code     — ISO currency code, e.g. "USD" (optional)
      payment_terms_id  — payment terms ID (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    tenant_id = merged.get("tenant_id")
    company_id = merged.get("company_id")
    display_name = merged.get("display_name")
    if not tenant_id:
        raise ValueError("tenant_id is required for dynamics_365_bc.create_customer")
    if not company_id:
        raise ValueError("company_id is required for dynamics_365_bc.create_customer")
    if not display_name:
        raise ValueError("display_name is required for dynamics_365_bc.create_customer")

    payload: dict = {"displayName": display_name}
    if merged.get("email"):
        payload["email"] = merged["email"]
    if merged.get("phone_number"):
        payload["phoneNumber"] = merged["phone_number"]
    if merged.get("address"):
        payload["address"] = merged["address"]
    if merged.get("currency_code"):
        payload["currencyCode"] = merged["currency_code"]
    if merged.get("payment_terms_id"):
        payload["paymentTermsId"] = merged["payment_terms_id"]

    base = _bc_base(tenant_id)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post(
            f"/companies({company_id})/customers",
            headers=_bc_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        customer = r.json()

    log.info("dynamics_365_bc.create_customer", company_id=company_id, customer_id=customer.get("id"))
    return {"customer": customer, "customer_id": customer.get("id")}


@register_node("dynamics_365_bc.list_invoices")
async def dynamics_365_bc_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List sales invoices in a Dynamics 365 Business Central company.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      tenant_id    — Azure AD tenant ID (required)
      company_id   — Business Central company ID (required)
      top          — maximum number of records to return (optional)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    tenant_id = merged.get("tenant_id")
    company_id = merged.get("company_id")
    if not tenant_id:
        raise ValueError("tenant_id is required for dynamics_365_bc.list_invoices")
    if not company_id:
        raise ValueError("company_id is required for dynamics_365_bc.list_invoices")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    base = _bc_base(tenant_id)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.get(
            f"/companies({company_id})/salesInvoices",
            headers=_bc_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    invoices = data.get("value", [])
    log.info("dynamics_365_bc.list_invoices", company_id=company_id, count=len(invoices))
    return {"invoices": invoices, "count": len(invoices)}


@register_node("dynamics_365_bc.create_invoice")
async def dynamics_365_bc_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new sales invoice in Dynamics 365 Business Central.

    config/input_data:
      access_token    — Microsoft OAuth2 bearer token (required)
      tenant_id       — Azure AD tenant ID (required)
      company_id      — Business Central company ID (required)
      customer_id     — customer ID for the invoice (required)
      invoice_date    — invoice date in YYYY-MM-DD format (optional)
      due_date        — payment due date in YYYY-MM-DD format (optional)
      currency_code   — ISO currency code, e.g. "USD" (optional)
      external_doc_no — external document number (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    tenant_id = merged.get("tenant_id")
    company_id = merged.get("company_id")
    customer_id = merged.get("customer_id")
    if not tenant_id:
        raise ValueError("tenant_id is required for dynamics_365_bc.create_invoice")
    if not company_id:
        raise ValueError("company_id is required for dynamics_365_bc.create_invoice")
    if not customer_id:
        raise ValueError("customer_id is required for dynamics_365_bc.create_invoice")

    payload: dict = {"customerId": customer_id}
    if merged.get("invoice_date"):
        payload["invoiceDate"] = merged["invoice_date"]
    if merged.get("due_date"):
        payload["dueDate"] = merged["due_date"]
    if merged.get("currency_code"):
        payload["currencyCode"] = merged["currency_code"]
    if merged.get("external_doc_no"):
        payload["externalDocumentNumber"] = merged["external_doc_no"]

    base = _bc_base(tenant_id)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post(
            f"/companies({company_id})/salesInvoices",
            headers=_bc_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        invoice = r.json()

    log.info("dynamics_365_bc.create_invoice", company_id=company_id, invoice_id=invoice.get("id"))
    return {"invoice": invoice, "invoice_id": invoice.get("id")}
