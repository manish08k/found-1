"""
Cloudflare DNS/CDN integration.

Provides zone management, DNS record CRUD, and cache purging via the
Cloudflare API v4.

Credential fields:
  - api_token : Cloudflare API token (Bearer auth)

Base URL: https://api.cloudflare.com/client/v4/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.cloudflare.com/client/v4"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_token = creds.get("api_token")
    if not api_token:
        raise ValueError("Cloudflare credential missing 'api_token'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cloudflare API error {r.status_code}: {detail}")


def _cf_result(r: httpx.Response) -> dict:
    _raise_for_status(r)
    data = r.json()
    if not data.get("success", True):
        errors = data.get("errors", [])
        raise ValueError(f"Cloudflare API returned errors: {errors}")
    return data


@register_node("cloudflare.list_zones")
async def cf_list_zones(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all zones (domains) in the Cloudflare account."""
    name_filter = config.get("name") or input_data.get("name")
    status = config.get("status") or input_data.get("status")
    page = int(config.get("page") or input_data.get("page", 1))
    per_page = min(int(config.get("per_page") or input_data.get("per_page", 20)), 50)

    params: dict = {"page": page, "per_page": per_page}
    if name_filter:
        params["name"] = name_filter
    if status:
        params["status"] = status

    async with await _client(credential_id, db) as client:
        r = await client.get("/zones", params=params)
        data = _cf_result(r)

    return {
        "zones": data.get("result", []),
        "result_info": data.get("result_info", {}),
    }


@register_node("cloudflare.create_dns_record")
async def cf_create_dns_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a DNS record in a Cloudflare zone."""
    zone_id = config.get("zone_id") or input_data.get("zone_id")
    record_type = config.get("type") or input_data.get("type")
    name = config.get("name") or input_data.get("name")
    content = config.get("content") or input_data.get("content")
    ttl = int(config.get("ttl") or input_data.get("ttl", 1))  # 1 = Auto
    proxied = bool(config.get("proxied") or input_data.get("proxied", False))
    priority = config.get("priority") or input_data.get("priority")

    if not all([zone_id, record_type, name, content]):
        raise ValueError(
            "cloudflare.create_dns_record requires 'zone_id', 'type', 'name', 'content'"
        )

    payload: dict = {
        "type": record_type.upper(),
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    if priority is not None:
        payload["priority"] = int(priority)

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/zones/{zone_id}/dns_records", json=payload)
        data = _cf_result(r)

    return {"dns_record": data.get("result", {})}


@register_node("cloudflare.update_dns_record")
async def cf_update_dns_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing DNS record in a Cloudflare zone."""
    zone_id = config.get("zone_id") or input_data.get("zone_id")
    record_id = config.get("record_id") or input_data.get("record_id")

    if not all([zone_id, record_id]):
        raise ValueError(
            "cloudflare.update_dns_record requires 'zone_id' and 'record_id'"
        )

    payload: dict = {}
    for key in ("type", "name", "content", "ttl", "proxied"):
        val = config.get(key) if config.get(key) is not None else input_data.get(key)
        if val is not None:
            if key == "type":
                payload[key] = str(val).upper()
            elif key == "proxied":
                payload[key] = bool(val)
            elif key == "ttl":
                payload[key] = int(val)
            else:
                payload[key] = val

    if not payload:
        raise ValueError("cloudflare.update_dns_record: at least one field to update is required")

    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/zones/{zone_id}/dns_records/{record_id}", json=payload)
        data = _cf_result(r)

    return {"dns_record": data.get("result", {})}


@register_node("cloudflare.delete_dns_record")
async def cf_delete_dns_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a DNS record from a Cloudflare zone."""
    zone_id = config.get("zone_id") or input_data.get("zone_id")
    record_id = config.get("record_id") or input_data.get("record_id")

    if not all([zone_id, record_id]):
        raise ValueError(
            "cloudflare.delete_dns_record requires 'zone_id' and 'record_id'"
        )

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/zones/{zone_id}/dns_records/{record_id}")
        data = _cf_result(r)

    return {"deleted": True, "result": data.get("result", {})}


@register_node("cloudflare.purge_cache")
async def cf_purge_cache(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Purge cached content from Cloudflare edge nodes.

    Supports purging by specific URLs or a full zone purge.
    Config:
      - zone_id  : Required. The zone to purge.
      - urls     : Optional list of URLs to purge. If omitted, purges everything.
      - purge_all: Optional bool, set True to purge entire cache (overrides urls).
    """
    zone_id = config.get("zone_id") or input_data.get("zone_id")
    if not zone_id:
        raise ValueError("cloudflare.purge_cache requires 'zone_id'")

    purge_all = bool(config.get("purge_all") or input_data.get("purge_all", False))
    urls = config.get("urls") or input_data.get("urls")

    if purge_all:
        payload: dict = {"purge_everything": True}
    elif urls:
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",") if u.strip()]
        payload = {"files": urls}
    else:
        # Default to full purge if nothing specified
        payload = {"purge_everything": True}

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/zones/{zone_id}/purge_cache", json=payload)
        data = _cf_result(r)

    return {"purged": True, "result": data.get("result", {})}


@register_node("cloudflare.list_dns_records")
async def cf_list_dns_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List DNS records for a Cloudflare zone."""
    zone_id = config.get("zone_id") or input_data.get("zone_id")
    if not zone_id:
        raise ValueError("cloudflare.list_dns_records requires 'zone_id'")

    params: dict = {}
    for key in ("type", "name", "content"):
        val = config.get(key) or input_data.get(key)
        if val:
            params[key] = val
    params["per_page"] = min(int(config.get("per_page") or input_data.get("per_page", 100)), 100)
    params["page"] = int(config.get("page") or input_data.get("page", 1))

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/zones/{zone_id}/dns_records", params=params)
        data = _cf_result(r)

    return {
        "dns_records": data.get("result", []),
        "result_info": data.get("result_info", {}),
    }
