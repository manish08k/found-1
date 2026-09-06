"""ClickFunnels integration for funnel and contact management."""
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.clickfunnels.com"


def _get_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _workspace_url(workspace_id: str) -> str:
    return f"{BASE_URL}/workspaces/{workspace_id}"


@register_node("clickfunnels.list_funnels")
async def cf_list_funnels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List funnels in the ClickFunnels workspace."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    access_token = creds.get("access_token")
    workspace_id = creds.get("workspace_id") or merged.get("workspace_id")
    if not access_token or not workspace_id:
        raise ValueError("clickfunnels requires 'access_token' and 'workspace_id'")

    params = {"page": int(merged.get("page", 1)), "per_page": int(merged.get("per_page", 25))}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_workspace_url(workspace_id)}/funnels",
            headers=_get_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        return r.json()


@register_node("clickfunnels.get_funnel")
async def cf_get_funnel(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific funnel."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    access_token = creds.get("access_token")
    workspace_id = creds.get("workspace_id") or merged.get("workspace_id")
    funnel_id = merged.get("funnel_id")
    if not funnel_id:
        raise ValueError("get_funnel requires 'funnel_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_workspace_url(workspace_id)}/funnels/{funnel_id}",
            headers=_get_headers(access_token),
        )
        r.raise_for_status()
        return r.json()


@register_node("clickfunnels.list_contacts")
async def cf_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts in the ClickFunnels workspace."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    access_token = creds.get("access_token")
    workspace_id = creds.get("workspace_id") or merged.get("workspace_id")

    params = {"page": int(merged.get("page", 1)), "per_page": int(merged.get("per_page", 25))}
    if merged.get("email"):
        params["email"] = merged["email"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_workspace_url(workspace_id)}/contacts",
            headers=_get_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        return r.json()


@register_node("clickfunnels.create_contact")
async def cf_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in ClickFunnels."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    access_token = creds.get("access_token")
    workspace_id = creds.get("workspace_id") or merged.get("workspace_id")
    email = merged.get("email")
    if not email:
        raise ValueError("create_contact requires 'email'")

    payload = {"contact": {"email_address": email}}
    contact_data = payload["contact"]
    for field in ["first_name", "last_name", "phone_number", "time_zone"]:
        if merged.get(field):
            contact_data[field] = merged[field]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_workspace_url(workspace_id)}/contacts",
            headers=_get_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("clickfunnels.get_order")
async def cf_get_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific order."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    access_token = creds.get("access_token")
    workspace_id = creds.get("workspace_id") or merged.get("workspace_id")
    order_id = merged.get("order_id")
    if not order_id:
        raise ValueError("get_order requires 'order_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_workspace_url(workspace_id)}/orders/{order_id}",
            headers=_get_headers(access_token),
        )
        r.raise_for_status()
        return r.json()
