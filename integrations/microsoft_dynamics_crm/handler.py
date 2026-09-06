"""Microsoft Dynamics CRM integration — accounts, contacts, and leads via Dataverse API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _crm_base(org: str) -> str:
    return f"https://{org}.api.crm.dynamics.com/api/data/v9.2"


def _crm_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
    }


@register_node("dynamics_crm.list_accounts")
async def dynamics_crm_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List accounts in Dynamics CRM.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      org          — CRM organization name, e.g. "myorg" (required)
      top          — maximum number of records to return (optional)
      filter       — OData filter expression (optional)
      select       — comma-separated list of fields to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    org = merged.get("org")
    if not org:
        raise ValueError("org is required for dynamics_crm.list_accounts")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]
    if merged.get("select"):
        params["$select"] = merged["select"]

    base = _crm_base(org)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.get("/accounts", headers=_crm_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    accounts = data.get("value", [])
    log.info("dynamics_crm.list_accounts", org=org, count=len(accounts))
    return {"accounts": accounts, "count": len(accounts)}


@register_node("dynamics_crm.create_account")
async def dynamics_crm_create_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new account in Dynamics CRM.

    config/input_data:
      access_token  — Microsoft OAuth2 bearer token (required)
      org           — CRM organization name, e.g. "myorg" (required)
      name          — account name (required)
      email_address — primary email address (optional)
      telephone1    — primary phone number (optional)
      websiteurl    — account website URL (optional)
      address1_city — city (optional)
      revenue       — annual revenue (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    org = merged.get("org")
    name = merged.get("name")
    if not org:
        raise ValueError("org is required for dynamics_crm.create_account")
    if not name:
        raise ValueError("name is required for dynamics_crm.create_account")

    payload: dict = {"name": name}
    for field in ("email_address", "telephone1", "websiteurl", "address1_city", "revenue"):
        if merged.get(field) is not None:
            crm_field = field.replace("_", "")
            payload[crm_field] = merged[field]

    base = _crm_base(org)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post("/accounts", headers=_crm_headers(access_token), json=payload)
        r.raise_for_status()
        account_id = r.headers.get("OData-EntityId", "")

    log.info("dynamics_crm.create_account", org=org, name=name)
    return {"account_id": account_id, "name": name, "created": True}


@register_node("dynamics_crm.list_contacts")
async def dynamics_crm_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts in Dynamics CRM.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      org          — CRM organization name, e.g. "myorg" (required)
      top          — maximum number of records to return (optional)
      filter       — OData filter expression (optional)
      select       — comma-separated list of fields to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    org = merged.get("org")
    if not org:
        raise ValueError("org is required for dynamics_crm.list_contacts")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]
    if merged.get("select"):
        params["$select"] = merged["select"]

    base = _crm_base(org)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.get("/contacts", headers=_crm_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("value", [])
    log.info("dynamics_crm.list_contacts", org=org, count=len(contacts))
    return {"contacts": contacts, "count": len(contacts)}


@register_node("dynamics_crm.create_contact")
async def dynamics_crm_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in Dynamics CRM.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      org          — CRM organization name, e.g. "myorg" (required)
      firstname    — contact first name (required)
      lastname     — contact last name (required)
      emailaddress1 — primary email address (optional)
      telephone1   — primary phone number (optional)
      jobtitle     — job title (optional)
      accountid    — associated account ID (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    org = merged.get("org")
    firstname = merged.get("firstname")
    lastname = merged.get("lastname")
    if not org:
        raise ValueError("org is required for dynamics_crm.create_contact")
    if not firstname:
        raise ValueError("firstname is required for dynamics_crm.create_contact")
    if not lastname:
        raise ValueError("lastname is required for dynamics_crm.create_contact")

    payload: dict = {"firstname": firstname, "lastname": lastname}
    for field in ("emailaddress1", "telephone1", "jobtitle"):
        if merged.get(field):
            payload[field] = merged[field]
    if merged.get("accountid"):
        payload["_parentcustomerid_value"] = merged["accountid"]

    base = _crm_base(org)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post("/contacts", headers=_crm_headers(access_token), json=payload)
        r.raise_for_status()
        contact_id = r.headers.get("OData-EntityId", "")

    log.info("dynamics_crm.create_contact", org=org, firstname=firstname, lastname=lastname)
    return {"contact_id": contact_id, "firstname": firstname, "lastname": lastname, "created": True}


@register_node("dynamics_crm.list_leads")
async def dynamics_crm_list_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List leads in Dynamics CRM.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token (required)
      org          — CRM organization name, e.g. "myorg" (required)
      top          — maximum number of records to return (optional)
      filter       — OData filter expression (optional)
      select       — comma-separated list of fields to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    org = merged.get("org")
    if not org:
        raise ValueError("org is required for dynamics_crm.list_leads")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]
    if merged.get("select"):
        params["$select"] = merged["select"]

    base = _crm_base(org)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.get("/leads", headers=_crm_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    leads = data.get("value", [])
    log.info("dynamics_crm.list_leads", org=org, count=len(leads))
    return {"leads": leads, "count": len(leads)}


@register_node("dynamics_crm.create_lead")
async def dynamics_crm_create_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new lead in Dynamics CRM.

    config/input_data:
      access_token  — Microsoft OAuth2 bearer token (required)
      org           — CRM organization name, e.g. "myorg" (required)
      firstname     — lead first name (required)
      lastname      — lead last name (required)
      emailaddress1 — primary email address (optional)
      telephone1    — primary phone number (optional)
      companyname   — company name (optional)
      jobtitle      — job title (optional)
      subject       — lead subject/topic (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    org = merged.get("org")
    firstname = merged.get("firstname")
    lastname = merged.get("lastname")
    if not org:
        raise ValueError("org is required for dynamics_crm.create_lead")
    if not firstname:
        raise ValueError("firstname is required for dynamics_crm.create_lead")
    if not lastname:
        raise ValueError("lastname is required for dynamics_crm.create_lead")

    payload: dict = {"firstname": firstname, "lastname": lastname}
    for field in ("emailaddress1", "telephone1", "companyname", "jobtitle", "subject"):
        if merged.get(field):
            payload[field] = merged[field]

    base = _crm_base(org)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post("/leads", headers=_crm_headers(access_token), json=payload)
        r.raise_for_status()
        lead_id = r.headers.get("OData-EntityId", "")

    log.info("dynamics_crm.create_lead", org=org, firstname=firstname, lastname=lastname)
    return {"lead_id": lead_id, "firstname": firstname, "lastname": lastname, "created": True}
