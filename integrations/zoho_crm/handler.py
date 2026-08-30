"""Zoho CRM integration — records, leads, contacts, deals, notes, tasks, and token refresh."""
import structlog
import httpx

from core.execution_engine import register_node
from core.ssrf_guard import assert_safe_url
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)


async def _zoho_creds(credential_id: str, db) -> dict:
    """Decrypt and return Zoho CRM credential fields."""
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    cred = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    if not cred.get("access_token"):
        raise ValueError("Zoho CRM credential is missing 'access_token'")
    return cred


def _zoho_base(cred: dict) -> str:
    data_center = cred.get("data_center", "com")
    return f"https://www.zohoapis.{data_center}/crm/v3"


def _zoho_client(access_token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    """Raise descriptive errors on non-2xx, with special guidance for 401."""
    if r.status_code == 401:
        raise ValueError(
            "Zoho CRM returned 401 Unauthorized. The access token has likely expired. "
            "Use zoho_crm.refresh_token to obtain a new access token and update the credential."
        )
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Zoho CRM API error {r.status_code}: {detail}")
    # 204 No Content is valid for DELETE
    if r.status_code == 204:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Generic record operations
# ---------------------------------------------------------------------------

@register_node("zoho_crm.create_record")
async def zoho_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a record in any Zoho CRM module."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    if not module:
        raise ValueError("zoho_crm.create_record requires 'module'")
    data = config.get("data")
    if not data or not isinstance(data, dict):
        raise ValueError("zoho_crm.create_record requires 'data' (dict)")

    url = f"{_zoho_base(cred)}/{module}"
    assert_safe_url(url)

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.post(url, json={"data": [data]})
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {
        "id": result.get("details", {}).get("id"),
        "message": result.get("message"),
        "status": result.get("status"),
    }


@register_node("zoho_crm.get_record")
async def zoho_get_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a single record from a Zoho CRM module by ID."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    record_id = config.get("record_id")
    if not module or not record_id:
        raise ValueError("zoho_crm.get_record requires 'module' and 'record_id'")

    url = f"{_zoho_base(cred)}/{module}/{record_id}"
    assert_safe_url(url)

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.get(url)
    resp = _check(r)
    records = resp.get("data") or []
    return {"record": records[0] if records else {}}


@register_node("zoho_crm.update_record")
async def zoho_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing record in a Zoho CRM module."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    record_id = config.get("record_id")
    data = config.get("data")
    if not module or not record_id:
        raise ValueError("zoho_crm.update_record requires 'module' and 'record_id'")
    if not data or not isinstance(data, dict):
        raise ValueError("zoho_crm.update_record requires 'data' (dict)")

    url = f"{_zoho_base(cred)}/{module}/{record_id}"
    assert_safe_url(url)

    payload = dict(data)
    payload["id"] = record_id

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.put(url, json={"data": [payload]})
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {
        "id": result.get("details", {}).get("id"),
        "message": result.get("message"),
        "status": result.get("status"),
    }


@register_node("zoho_crm.delete_record")
async def zoho_delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a record from a Zoho CRM module."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    record_id = config.get("record_id")
    if not module or not record_id:
        raise ValueError("zoho_crm.delete_record requires 'module' and 'record_id'")

    url = f"{_zoho_base(cred)}/{module}/{record_id}"
    assert_safe_url(url)

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.delete(url)
    _check(r)
    return {"deleted": True, "record_id": record_id, "module": module}


@register_node("zoho_crm.list_records")
async def zoho_list_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List records from a Zoho CRM module with optional field selection and pagination."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    if not module:
        raise ValueError("zoho_crm.list_records requires 'module'")

    url = f"{_zoho_base(cred)}/{module}"
    assert_safe_url(url)

    params: dict = {}
    fields = config.get("fields")
    if fields:
        params["fields"] = fields if isinstance(fields, str) else ",".join(fields)
    per_page = config.get("per_page", 50)
    params["per_page"] = min(int(per_page), 200)
    page = config.get("page", 1)
    params["page"] = int(page)

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.get(url, params=params)
    resp = _check(r)
    return {
        "records": resp.get("data") or [],
        "info": resp.get("info", {}),
    }


@register_node("zoho_crm.search_records")
async def zoho_search_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search records in a Zoho CRM module by criteria or full-text word."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    if not module:
        raise ValueError("zoho_crm.search_records requires 'module'")

    url = f"{_zoho_base(cred)}/{module}/search"
    assert_safe_url(url)

    params: dict = {}
    criteria = config.get("criteria")
    word = config.get("word")
    if criteria:
        params["criteria"] = criteria
    elif word:
        params["word"] = word
    else:
        raise ValueError("zoho_crm.search_records requires 'criteria' or 'word'")

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.get(url, params=params)
    resp = _check(r)
    return {"records": resp.get("data") or [], "info": resp.get("info", {})}


@register_node("zoho_crm.upsert_record")
async def zoho_upsert_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Upsert a record — insert if not found, update if duplicate detected."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    data = config.get("data")
    if not module:
        raise ValueError("zoho_crm.upsert_record requires 'module'")
    if not data or not isinstance(data, dict):
        raise ValueError("zoho_crm.upsert_record requires 'data' (dict)")

    url = f"{_zoho_base(cred)}/{module}/upsert"
    assert_safe_url(url)

    body: dict = {"data": [data]}
    duplicate_check_fields = config.get("duplicate_check_fields")
    if duplicate_check_fields:
        if isinstance(duplicate_check_fields, list):
            body["duplicate_check_fields"] = duplicate_check_fields
        else:
            body["duplicate_check_fields"] = [duplicate_check_fields]

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {
        "id": result.get("details", {}).get("id"),
        "message": result.get("message"),
        "status": result.get("status"),
        "action": result.get("action"),
    }


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@register_node("zoho_crm.create_lead")
async def zoho_create_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convenience node to create a Zoho CRM Lead with standard fields."""
    cred = await _zoho_creds(credential_id, db)
    last_name = config.get("last_name")
    company = config.get("company")
    if not last_name:
        raise ValueError("zoho_crm.create_lead requires 'last_name'")
    if not company:
        raise ValueError("zoho_crm.create_lead requires 'company'")

    url = f"{_zoho_base(cred)}/Leads"
    assert_safe_url(url)

    record: dict = {"Last_Name": last_name, "Company": company}
    field_map = {
        "first_name": "First_Name",
        "email": "Email",
        "phone": "Phone",
        "lead_source": "Lead_Source",
        "annual_revenue": "Annual_Revenue",
    }
    for cfg_key, zoho_key in field_map.items():
        v = config.get(cfg_key)
        if v is not None:
            record[zoho_key] = v

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.post(url, json={"data": [record]})
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {
        "id": result.get("details", {}).get("id"),
        "message": result.get("message"),
        "status": result.get("status"),
    }


@register_node("zoho_crm.convert_lead")
async def zoho_convert_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert a Zoho CRM Lead into a Contact, Account, and optionally a Deal."""
    cred = await _zoho_creds(credential_id, db)
    lead_id = config.get("lead_id")
    if not lead_id:
        raise ValueError("zoho_crm.convert_lead requires 'lead_id'")

    url = f"{_zoho_base(cred)}/Leads/{lead_id}/actions/convert"
    assert_safe_url(url)

    conversion: dict = {}
    assign_to = config.get("assign_to")
    if assign_to:
        conversion["assign_to"] = {"id": assign_to}
    notify_lead_owner = config.get("notify_lead_owner")
    if notify_lead_owner is not None:
        conversion["notify_lead_owner"] = notify_lead_owner

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.post(url, json={"data": [conversion]})
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {"converted": result}


# ---------------------------------------------------------------------------
# Fields metadata
# ---------------------------------------------------------------------------

@register_node("zoho_crm.get_fields")
async def zoho_get_fields(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the field definitions for a Zoho CRM module."""
    cred = await _zoho_creds(credential_id, db)
    module = config.get("module")
    if not module:
        raise ValueError("zoho_crm.get_fields requires 'module'")

    url = f"{_zoho_base(cred)}/{module}/fields"
    assert_safe_url(url)

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.get(url)
    resp = _check(r)
    return {"fields": resp.get("fields") or []}


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@register_node("zoho_crm.add_note")
async def zoho_add_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add a note to any Zoho CRM record."""
    cred = await _zoho_creds(credential_id, db)
    parent_module = config.get("parent_module")
    parent_id = config.get("parent_id")
    note_content = config.get("note_content")
    if not parent_module or not parent_id:
        raise ValueError("zoho_crm.add_note requires 'parent_module' and 'parent_id'")
    if not note_content:
        raise ValueError("zoho_crm.add_note requires 'note_content'")

    url = f"{_zoho_base(cred)}/Notes"
    assert_safe_url(url)

    record: dict = {
        "Note_Content": note_content,
        "Parent_Id": {"id": parent_id},
        "$se_module": parent_module,
    }
    note_title = config.get("note_title")
    if note_title:
        record["Note_Title"] = note_title

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.post(url, json={"data": [record]})
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {
        "id": result.get("details", {}).get("id"),
        "message": result.get("message"),
        "status": result.get("status"),
    }


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@register_node("zoho_crm.add_task")
async def zoho_add_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a task in Zoho CRM."""
    cred = await _zoho_creds(credential_id, db)
    subject = config.get("subject")
    if not subject:
        raise ValueError("zoho_crm.add_task requires 'subject'")

    url = f"{_zoho_base(cred)}/Tasks"
    assert_safe_url(url)

    record: dict = {"Subject": subject}
    field_map = {
        "due_date": "Due_Date",
        "account_name": "Account_Name",
        "status": "Status",
        "priority": "Priority",
    }
    for cfg_key, zoho_key in field_map.items():
        v = config.get(cfg_key)
        if v is not None:
            record[zoho_key] = v

    contact_id = config.get("contact_id")
    if contact_id:
        record["Who_Id"] = {"id": contact_id}
    deal_id = config.get("deal_id")
    if deal_id:
        record["What_Id"] = {"id": deal_id}

    async with _zoho_client(cred["access_token"]) as client:
        r = await client.post(url, json={"data": [record]})
    resp = _check(r)
    result = (resp.get("data") or [{}])[0]
    return {
        "id": result.get("details", {}).get("id"),
        "message": result.get("message"),
        "status": result.get("status"),
    }


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@register_node("zoho_crm.refresh_token")
async def zoho_refresh_token(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Refresh the Zoho CRM OAuth access token using the stored refresh token.

    Note: This returns the new access_token but does NOT automatically persist it
    back to the credential store. The caller must update the credential separately.
    """
    cred = await _zoho_creds(credential_id, db)
    refresh_token = cred.get("refresh_token")
    client_id = cred.get("client_id")
    client_secret = cred.get("client_secret")
    data_center = cred.get("data_center", "com")

    if not all([refresh_token, client_id, client_secret]):
        raise ValueError(
            "zoho_crm.refresh_token requires 'refresh_token', 'client_id', 'client_secret' in the credential"
        )

    token_url = f"https://accounts.zoho.{data_center}/oauth/v2/token"
    assert_safe_url(token_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(token_url, data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        })
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Zoho token refresh failed {r.status_code}: {detail}")

    resp = r.json()
    new_token = resp.get("access_token")
    if not new_token:
        raise ValueError(f"Zoho token refresh did not return access_token: {resp}")

    log.info("zoho_crm_token_refreshed",
             expires_in=resp.get("expires_in"),
             note="Update the credential record with the new access_token")

    return {
        "access_token": new_token,
        "expires_in": resp.get("expires_in"),
        "token_type": resp.get("token_type"),
    }
