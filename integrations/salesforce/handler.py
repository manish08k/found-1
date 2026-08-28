"""
Salesforce integration — leads, contacts, opportunities, cases, SOQL queries.
Uses the Salesforce REST API with OAuth2 credentials or username/password flow.

Nodes: salesforce.query, salesforce.create_record, salesforce.update_record,
       salesforce.get_record, salesforce.delete_record, salesforce.create_lead,
       salesforce.create_contact, salesforce.create_opportunity
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


async def _get_sf_token(config: dict) -> tuple[str, str]:
    """Returns (access_token, instance_url) via username-password OAuth flow."""
    client_id = config.get("client_id") or getattr(settings, "SALESFORCE_CLIENT_ID", "")
    client_secret = config.get("client_secret") or getattr(settings, "SALESFORCE_CLIENT_SECRET", "")
    username = config.get("username") or getattr(settings, "SALESFORCE_USERNAME", "")
    password = config.get("password") or getattr(settings, "SALESFORCE_PASSWORD", "")
    security_token = config.get("security_token") or getattr(settings, "SALESFORCE_SECURITY_TOKEN", "")
    sandbox = config.get("sandbox", False)

    login_url = "https://test.salesforce.com" if sandbox else "https://login.salesforce.com"

    if not all([client_id, client_secret, username, password]):
        raise ValueError("salesforce nodes require client_id, client_secret, username, password")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{login_url}/services/oauth2/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": f"{password}{security_token}",
            },
        )
        r.raise_for_status()
        data = r.json()

    return data["access_token"], data["instance_url"]


@register_node("salesforce.query")
async def salesforce_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a SOQL query."""
    merged = {**config, **input_data}
    soql = merged.get("soql") or merged.get("query")
    if not soql:
        raise ValueError("salesforce.query requires 'soql'")

    token, instance_url = await _get_sf_token(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{instance_url}/services/data/v57.0/query",
            params={"q": soql},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    return {"records": data.get("records", []), "total_size": data.get("totalSize", 0), "done": data.get("done")}


@register_node("salesforce.create_record")
async def salesforce_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a Salesforce record of any object type."""
    merged = {**config, **input_data}
    sobject = merged.get("object_type") or merged.get("sobject", "Lead")
    fields = merged.get("fields") or {}

    token, instance_url = await _get_sf_token(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{instance_url}/services/data/v57.0/sobjects/{sobject}/",
            json=fields,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    return {"id": data.get("id"), "success": data.get("success"), "errors": data.get("errors", [])}


@register_node("salesforce.update_record")
async def salesforce_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update a Salesforce record."""
    merged = {**config, **input_data}
    sobject = merged.get("object_type", "Lead")
    record_id = merged.get("record_id")
    fields = merged.get("fields") or {}

    if not record_id:
        raise ValueError("salesforce.update_record requires 'record_id'")

    token, instance_url = await _get_sf_token(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{instance_url}/services/data/v57.0/sobjects/{sobject}/{record_id}",
            json=fields,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()

    return {"ok": True, "record_id": record_id}


@register_node("salesforce.get_record")
async def salesforce_get_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get a Salesforce record by ID."""
    merged = {**config, **input_data}
    sobject = merged.get("object_type", "Lead")
    record_id = merged.get("record_id")
    fields = merged.get("fields")  # comma-separated field names

    if not record_id:
        raise ValueError("salesforce.get_record requires 'record_id'")

    token, instance_url = await _get_sf_token(merged)
    params = {}
    if fields:
        params["fields"] = fields if isinstance(fields, str) else ",".join(fields)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{instance_url}/services/data/v57.0/sobjects/{sobject}/{record_id}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()

    return {"record": r.json()}


@register_node("salesforce.delete_record")
async def salesforce_delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a Salesforce record."""
    merged = {**config, **input_data}
    sobject = merged.get("object_type", "Lead")
    record_id = merged.get("record_id")

    if not record_id:
        raise ValueError("salesforce.delete_record requires 'record_id'")

    token, instance_url = await _get_sf_token(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(
            f"{instance_url}/services/data/v57.0/sobjects/{sobject}/{record_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()

    return {"ok": True, "deleted": record_id}


@register_node("salesforce.create_lead")
async def salesforce_create_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convenience node to create a Salesforce Lead."""
    merged = {**config, **input_data}
    required = ["LastName", "Company"]
    fields = {k: merged.get(k) or merged.get("fields", {}).get(k)
              for k in ["FirstName", "LastName", "Email", "Phone", "Company", "LeadSource", "Status"]}
    fields = {k: v for k, v in fields.items() if v is not None}

    for req in required:
        if req not in fields:
            raise ValueError(f"salesforce.create_lead requires '{req}'")

    merged["object_type"] = "Lead"
    merged["fields"] = fields
    return await salesforce_create_record(merged, {}, credential_id, db)


@register_node("salesforce.create_contact")
async def salesforce_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convenience node to create a Salesforce Contact."""
    merged = {**config, **input_data}
    fields = {k: merged.get(k) or merged.get("fields", {}).get(k)
              for k in ["FirstName", "LastName", "Email", "Phone", "AccountId", "Title", "Department"]}
    fields = {k: v for k, v in fields.items() if v is not None}

    if "LastName" not in fields:
        raise ValueError("salesforce.create_contact requires 'LastName'")

    merged["object_type"] = "Contact"
    merged["fields"] = fields
    return await salesforce_create_record(merged, {}, credential_id, db)


@register_node("salesforce.create_opportunity")
async def salesforce_create_opportunity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convenience node to create a Salesforce Opportunity."""
    merged = {**config, **input_data}
    fields = {k: merged.get(k) or merged.get("fields", {}).get(k)
              for k in ["Name", "CloseDate", "StageName", "AccountId", "Amount", "Probability"]}
    fields = {k: v for k, v in fields.items() if v is not None}

    for req in ["Name", "CloseDate", "StageName"]:
        if req not in fields:
            raise ValueError(f"salesforce.create_opportunity requires '{req}'")

    merged["object_type"] = "Opportunity"
    merged["fields"] = fields
    return await salesforce_create_record(merged, {}, credential_id, db)
