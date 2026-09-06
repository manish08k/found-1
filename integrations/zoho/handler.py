"""Zoho integration — unified Zoho platform operations."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _headers(config: dict) -> dict:
    return {"Authorization": f"Zoho-oauthtoken {config.get('access_token', '')}", "Content-Type": "application/json"}


@register_node("zoho.create_lead")
async def zoho_create_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dc = merged.get("data_center", "com")
    base = f"https://www.zohoapis.{dc}/crm/v2"
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{base}/Leads", json={
            "data": [{
                "Last_Name": merged.get("last_name", ""),
                "First_Name": merged.get("first_name", ""),
                "Email": merged.get("email", ""),
                "Company": merged.get("company", ""),
                "Phone": merged.get("phone", ""),
            }]
        })
        r.raise_for_status()
    return r.json()


@register_node("zoho.search_records")
async def zoho_search_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dc = merged.get("data_center", "com")
    module = merged.get("module", "Leads")
    base = f"https://www.zohoapis.{dc}/crm/v2"
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{base}/{module}/search", params={
            "criteria": merged.get("criteria", ""),
            "per_page": merged.get("per_page", 10),
        })
        r.raise_for_status()
    return r.json()


@register_node("zoho.update_record")
async def zoho_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dc = merged.get("data_center", "com")
    module = merged.get("module", "Leads")
    record_id = merged.get("record_id", "")
    base = f"https://www.zohoapis.{dc}/crm/v2"
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.put(f"{base}/{module}/{record_id}", json={
            "data": [merged.get("fields", {})]
        })
        r.raise_for_status()
    return r.json()


@register_node("zoho.create_contact")
async def zoho_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dc = merged.get("data_center", "com")
    base = f"https://www.zohoapis.{dc}/crm/v2"
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{base}/Contacts", json={
            "data": [{
                "Last_Name": merged.get("last_name", ""),
                "First_Name": merged.get("first_name", ""),
                "Email": merged.get("email", ""),
                "Phone": merged.get("phone", ""),
            }]
        })
        r.raise_for_status()
    return r.json()
