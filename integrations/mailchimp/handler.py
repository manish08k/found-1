"""
Mailchimp integration — lists, members, campaigns, templates.
Nodes: mailchimp.add_member, mailchimp.update_member, mailchimp.remove_member,
       mailchimp.get_lists, mailchimp.create_campaign, mailchimp.send_campaign,
       mailchimp.get_members
"""
import hashlib
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


def _client_info(config):
    api_key = config.get("api_key") or getattr(settings, "MAILCHIMP_API_KEY", "")
    server = config.get("server") or getattr(settings, "MAILCHIMP_SERVER", "us1")
    if not api_key:
        raise ValueError("mailchimp nodes require MAILCHIMP_API_KEY")
    base_url = f"https://{server}.api.mailchimp.com/3.0"
    auth = ("anystring", api_key)
    return base_url, auth


def _email_hash(email: str) -> str:
    return hashlib.md5(email.lower().encode()).hexdigest()


@register_node("mailchimp.get_lists")
async def mailchimp_get_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    count = min(int(merged.get("count", 10)), 100)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/lists", params={"count": count}, auth=auth)
        r.raise_for_status()
        data = r.json()

    return {"lists": data.get("lists", []), "total_items": data.get("total_items", 0)}


@register_node("mailchimp.add_member")
async def mailchimp_add_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    list_id = merged.get("list_id")
    email = merged.get("email")
    if not list_id or not email:
        raise ValueError("mailchimp.add_member requires 'list_id' and 'email'")

    payload = {
        "email_address": email,
        "status": merged.get("status", "subscribed"),
        "merge_fields": merged.get("merge_fields") or {
            "FNAME": merged.get("first_name", ""),
            "LNAME": merged.get("last_name", ""),
        },
        "tags": merged.get("tags") or [],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/lists/{list_id}/members", json=payload, auth=auth)
        if r.status_code == 400 and "already a list member" in r.text:
            return {"ok": True, "status": "already_subscribed", "email": email}
        r.raise_for_status()
        return {"member": r.json(), "ok": True}


@register_node("mailchimp.update_member")
async def mailchimp_update_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    list_id = merged.get("list_id")
    email = merged.get("email")
    if not list_id or not email:
        raise ValueError("mailchimp.update_member requires 'list_id' and 'email'")

    email_hash = _email_hash(email)
    payload = {}
    for field in ("status", "merge_fields", "tags"):
        val = merged.get(field)
        if val is not None:
            payload[field] = val

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(f"{base_url}/lists/{list_id}/members/{email_hash}", json=payload, auth=auth)
        r.raise_for_status()
        return {"member": r.json(), "ok": True}


@register_node("mailchimp.remove_member")
async def mailchimp_remove_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    list_id = merged.get("list_id")
    email = merged.get("email")
    if not list_id or not email:
        raise ValueError("mailchimp.remove_member requires 'list_id' and 'email'")

    email_hash = _email_hash(email)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{base_url}/lists/{list_id}/members/{email_hash}", auth=auth)
        r.raise_for_status()
    return {"ok": True, "email": email}


@register_node("mailchimp.get_members")
async def mailchimp_get_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth = _client_info(merged)
    list_id = merged.get("list_id")
    if not list_id:
        raise ValueError("mailchimp.get_members requires 'list_id'")
    count = min(int(merged.get("count", 25)), 1000)
    status = merged.get("status")

    params = {"count": count}
    if status:
        params["status"] = status

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/lists/{list_id}/members", params=params, auth=auth)
        r.raise_for_status()
        data = r.json()

    return {"members": data.get("members", []), "total_items": data.get("total_items", 0)}
