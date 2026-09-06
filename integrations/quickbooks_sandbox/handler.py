"""QuickBooks Sandbox integration — test environment for QuickBooks."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://sandbox-quickbooks.api.intuit.com/v3"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}


@register_node("quickbooks_sandbox.get_company_info")
async def qbs_get_company_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    realm_id = merged.get("realm_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/company/{realm_id}/companyinfo/{realm_id}")
        r.raise_for_status()
    return r.json()


@register_node("quickbooks_sandbox.create_customer")
async def qbs_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    realm_id = merged.get("realm_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/company/{realm_id}/customer", json={
            "FullyQualifiedName": merged.get("name", ""),
            "PrimaryEmailAddr": {"Address": merged.get("email", "")},
        })
        r.raise_for_status()
    return r.json()
