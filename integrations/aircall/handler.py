"""Aircall integration for cloud phone system management."""
import base64
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.aircall.io/v1"


def _get_auth_header(api_id: str, api_token: str) -> str:
    token = base64.b64encode(f"{api_id}:{api_token}".encode()).decode()
    return f"Basic {token}"


@register_node("aircall.list_calls")
async def aircall_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List calls with optional filters."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_id = creds.get("api_id")
    api_token = creds.get("api_token")
    if not api_id or not api_token:
        raise ValueError("aircall requires 'api_id' and 'api_token'")

    params = {"per_page": int(merged.get("per_page", 25)), "page": int(merged.get("page", 1))}
    for key in ["from", "to", "direction", "missed_call_reason", "user_id", "number_id"]:
        if merged.get(key):
            params[key] = merged[key]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/calls",
            headers={"Authorization": _get_auth_header(api_id, api_token)},
            params=params,
        )
        r.raise_for_status()
        return r.json()


@register_node("aircall.get_call")
async def aircall_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific call by ID."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_id = creds.get("api_id")
    api_token = creds.get("api_token")
    call_id = merged.get("call_id")
    if not call_id:
        raise ValueError("get_call requires 'call_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/calls/{call_id}",
            headers={"Authorization": _get_auth_header(api_id, api_token)},
        )
        r.raise_for_status()
        return r.json()


@register_node("aircall.list_users")
async def aircall_list_users(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all users in the Aircall account."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_id = creds.get("api_id")
    api_token = creds.get("api_token")

    params = {"per_page": int(merged.get("per_page", 25)), "page": int(merged.get("page", 1))}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/users",
            headers={"Authorization": _get_auth_header(api_id, api_token)},
            params=params,
        )
        r.raise_for_status()
        return r.json()


@register_node("aircall.create_call")
async def aircall_create_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Initiate an outbound call from an Aircall number."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_id = creds.get("api_id")
    api_token = creds.get("api_token")
    number_id = merged.get("number_id")
    to = merged.get("to")
    if not number_id or not to:
        raise ValueError("create_call requires 'number_id' and 'to'")

    payload = {"number_id": number_id, "to": to}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/calls",
            headers={"Authorization": _get_auth_header(api_id, api_token), "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("aircall.list_contacts")
async def aircall_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts in the Aircall account."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_id = creds.get("api_id")
    api_token = creds.get("api_token")

    params = {"per_page": int(merged.get("per_page", 25)), "page": int(merged.get("page", 1))}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/contacts",
            headers={"Authorization": _get_auth_header(api_id, api_token)},
            params=params,
        )
        r.raise_for_status()
        return r.json()


@register_node("aircall.search_contacts")
async def aircall_search_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search contacts by phone number or name."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_id = creds.get("api_id")
    api_token = creds.get("api_token")
    phone_number = merged.get("phone_number")
    name = merged.get("name")
    if not phone_number and not name:
        raise ValueError("search_contacts requires 'phone_number' or 'name'")

    params = {}
    if phone_number:
        params["phone_number"] = phone_number
    if name:
        params["name"] = name

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/contacts/search",
            headers={"Authorization": _get_auth_header(api_id, api_token)},
            params=params,
        )
        r.raise_for_status()
        return r.json()
