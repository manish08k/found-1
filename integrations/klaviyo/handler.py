"""
Klaviyo Email Marketing integration.

Provides profile management, event tracking, list/segment operations,
campaign management, template creation, and suppression via the Klaviyo API.

Credential fields:
  - private_api_key : Klaviyo private API key (starts with pk_)

Auth: Authorization: Klaviyo-API-Key {private_api_key}
Base URL: https://a.klaviyo.com/api
API Revision: 2024-02-15
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    from core.ssrf_guard import assert_safe_url
    _SSRF_AVAILABLE = True
except Exception:
    _SSRF_AVAILABLE = False

log = structlog.get_logger(__name__)

KLAVIYO_BASE = "https://a.klaviyo.com/api"
KLAVIYO_REVISION = "2024-02-15"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("private_api_key")
    if not api_key:
        raise ValueError("Klaviyo credential missing 'private_api_key'")
    if _SSRF_AVAILABLE:
        assert_safe_url(KLAVIYO_BASE)
    return httpx.AsyncClient(
        base_url=KLAVIYO_BASE,
        headers={
            "Authorization": f"Klaviyo-API-Key {api_key}",
            "Content-Type": "application/json",
            "revision": KLAVIYO_REVISION,
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Klaviyo API error {r.status_code}: {detail}")


@register_node("klaviyo.create_profile")
async def kv_create_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    phone_number = config.get("phone_number") or input_data.get("phone_number", "")
    external_id = config.get("external_id") or input_data.get("external_id", "")
    properties = config.get("properties") or input_data.get("properties", {})

    if not email:
        raise ValueError("klaviyo.create_profile requires 'email'")

    attrs: dict = {"email": email}
    if first_name:
        attrs["first_name"] = first_name
    if last_name:
        attrs["last_name"] = last_name
    if phone_number:
        attrs["phone_number"] = phone_number
    if external_id:
        attrs["external_id"] = external_id
    if properties:
        attrs["properties"] = properties

    payload = {"data": {"type": "profile", "attributes": attrs}}

    async with await _client(credential_id, db) as client:
        r = await client.post("/profiles/", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"profile": data.get("data", {})}


@register_node("klaviyo.get_profile")
async def kv_get_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    profile_id = config.get("profile_id") or input_data.get("profile_id")
    if not profile_id:
        raise ValueError("klaviyo.get_profile requires 'profile_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/profiles/{profile_id}")
        _raise_for_status(r)
        data = r.json()

    return {"profile": data.get("data", {})}


@register_node("klaviyo.update_profile")
async def kv_update_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    profile_id = config.get("profile_id") or input_data.get("profile_id")
    if not profile_id:
        raise ValueError("klaviyo.update_profile requires 'profile_id'")

    attrs: dict = {}
    for key in ("email", "first_name", "last_name", "phone_number", "external_id"):
        val = config.get(key) or input_data.get(key)
        if val:
            attrs[key] = val
    properties = config.get("properties") or input_data.get("properties")
    if properties:
        attrs["properties"] = properties

    payload = {"data": {"type": "profile", "id": profile_id, "attributes": attrs}}

    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/profiles/{profile_id}", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"profile": data.get("data", {})}


@register_node("klaviyo.list_profiles")
async def kv_list_profiles(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 20)), 100)
    filter_expr = config.get("filter") or input_data.get("filter", "")

    params: dict = {"page[size]": page_size}
    if filter_expr:
        params["filter"] = filter_expr

    async with await _client(credential_id, db) as client:
        r = await client.get("/profiles/", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"profiles": data.get("data", []), "links": data.get("links", {})}


@register_node("klaviyo.create_event")
async def kv_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    event_name = config.get("event_name") or input_data.get("event_name")
    profile_email = config.get("profile_email") or input_data.get("profile_email")
    properties = config.get("properties") or input_data.get("properties", {})
    value = config.get("value") or input_data.get("value")

    if not event_name:
        raise ValueError("klaviyo.create_event requires 'event_name'")
    if not profile_email:
        raise ValueError("klaviyo.create_event requires 'profile_email'")

    attrs: dict = {
        "metric": {"data": {"type": "metric", "attributes": {"name": event_name}}},
        "profile": {"data": {"type": "profile", "attributes": {"email": profile_email}}},
        "properties": properties or {},
    }
    if value is not None:
        attrs["value"] = float(value)

    payload = {"data": {"type": "event", "attributes": attrs}}

    async with await _client(credential_id, db) as client:
        r = await client.post("/events/", json=payload)
        _raise_for_status(r)

    return {"ok": True, "status_code": r.status_code}


@register_node("klaviyo.add_profile_to_list")
async def kv_add_profile_to_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    list_id = config.get("list_id") or input_data.get("list_id")
    profile_id = config.get("profile_id") or input_data.get("profile_id")
    profile_ids = config.get("profile_ids") or input_data.get("profile_ids", [])
    if not list_id:
        raise ValueError("klaviyo.add_profile_to_list requires 'list_id'")

    ids = profile_ids if profile_ids else ([profile_id] if profile_id else [])
    if not ids:
        raise ValueError("klaviyo.add_profile_to_list requires 'profile_id' or 'profile_ids'")

    payload = {"data": [{"type": "profile", "id": pid} for pid in ids]}

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/lists/{list_id}/relationships/profiles/", json=payload)
        _raise_for_status(r)

    return {"ok": True, "list_id": list_id, "profile_ids": ids}


@register_node("klaviyo.remove_profile_from_list")
async def kv_remove_profile_from_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    list_id = config.get("list_id") or input_data.get("list_id")
    profile_id = config.get("profile_id") or input_data.get("profile_id")
    if not list_id or not profile_id:
        raise ValueError("klaviyo.remove_profile_from_list requires 'list_id' and 'profile_id'")

    payload = {"data": [{"type": "profile", "id": profile_id}]}

    async with await _client(credential_id, db) as client:
        r = await client.request("DELETE", f"/lists/{list_id}/relationships/profiles/", json=payload)
        _raise_for_status(r)

    return {"ok": True, "list_id": list_id, "profile_id": profile_id}


@register_node("klaviyo.get_lists")
async def kv_get_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/lists/")
        _raise_for_status(r)
        data = r.json()

    return {"lists": data.get("data", []), "links": data.get("links", {})}


@register_node("klaviyo.create_list")
async def kv_create_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("klaviyo.create_list requires 'name'")

    payload = {"data": {"type": "list", "attributes": {"name": name}}}

    async with await _client(credential_id, db) as client:
        r = await client.post("/lists/", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"list": data.get("data", {})}


@register_node("klaviyo.get_segments")
async def kv_get_segments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/segments/")
        _raise_for_status(r)
        data = r.json()

    return {"segments": data.get("data", []), "links": data.get("links", {})}


@register_node("klaviyo.get_metrics")
async def kv_get_metrics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/metrics/")
        _raise_for_status(r)
        data = r.json()

    return {"metrics": data.get("data", []), "links": data.get("links", {})}


@register_node("klaviyo.create_template")
async def kv_create_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    name = config.get("name") or input_data.get("name")
    html = config.get("html") or input_data.get("html", "")
    text = config.get("text") or input_data.get("text", "")
    if not name:
        raise ValueError("klaviyo.create_template requires 'name'")

    attrs: dict = {"name": name}
    if html:
        attrs["html"] = html
    if text:
        attrs["text"] = text

    payload = {"data": {"type": "template", "attributes": attrs}}

    async with await _client(credential_id, db) as client:
        r = await client.post("/templates/", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"template": data.get("data", {})}


@register_node("klaviyo.send_campaign")
async def kv_send_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    if not campaign_id:
        raise ValueError("klaviyo.send_campaign requires 'campaign_id'")

    payload = {"data": {"type": "campaign-send-job", "attributes": {"campaign_id": campaign_id}}}

    async with await _client(credential_id, db) as client:
        r = await client.post("/campaign-send-jobs/", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"send_job": data.get("data", {})}


@register_node("klaviyo.get_campaigns")
async def kv_get_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    filter_expr = config.get("filter") or input_data.get("filter", "")

    params: dict = {}
    if filter_expr:
        params["filter"] = filter_expr

    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns/", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"campaigns": data.get("data", []), "links": data.get("links", {})}


@register_node("klaviyo.suppress_profile")
async def kv_suppress_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("klaviyo.suppress_profile requires 'email'")

    payload = {
        "data": {
            "type": "profile-suppression-bulk-create-job",
            "attributes": {
                "profiles": {
                    "data": [{"type": "profile", "attributes": {"email": email}}]
                }
            },
        }
    }

    async with await _client(credential_id, db) as client:
        r = await client.post("/profile-suppression-bulk-create-jobs/", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"suppression_job": data.get("data", {})}
