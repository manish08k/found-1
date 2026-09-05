"""
Bubble no-code application database API integration.

Provides CRUD operations on any Bubble data type via the Bubble
Data API.

Credential fields:
  - api_key  : Bubble API key (from Settings > API).
  - app_name : The Bubble app name (subdomain) — e.g. 'myapp' for myapp.bubbleapps.io.
               Alternatively set 'custom_domain' for a deployed custom domain.
  - custom_domain: (optional) Custom domain like 'app.mycompany.com'.
  - environment: 'live' (default) or 'test'. Affects the API base URL.

Auth: Bearer token via Authorization header.
Base URL: https://{app_name}.bubbleapps.io/api/1.1/obj/{type}
         OR https://{custom_domain}/api/1.1/obj/{type}
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> tuple[str, str, str]:
    """Returns (api_key, base_url, version_prefix)."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Bubble credential missing 'api_key'")

    custom_domain = creds.get("custom_domain")
    app_name = creds.get("app_name")
    if not custom_domain and not app_name:
        raise ValueError("Bubble credential requires 'app_name' or 'custom_domain'")

    environment = creds.get("environment", "live")
    version_prefix = "" if environment == "live" else "?version=test"

    if custom_domain:
        base_url = f"https://{custom_domain.rstrip('/')}/api/1.1/obj"
    else:
        base_url = f"https://{app_name}.bubbleapps.io/api/1.1/obj"

    return api_key, base_url, version_prefix


def _make_client(api_key: str, base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
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
        raise ValueError(f"Bubble API error {r.status_code}: {detail}")


@register_node("bubble.list_things")
async def bubble_list_things(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List objects (Things) of a given data type from a Bubble app.

    Params:
      - type (required): The Bubble data type name (e.g. 'user', 'product').
      - limit: Max results per page (max 100, default 100).
      - cursor: Pagination cursor (integer offset, default 0).
      - sort_field: Field name to sort by.
      - descending: bool — sort descending (default False).
      - constraints: JSON list of constraint objects, e.g.
          [{"key": "email", "constraint_type": "equals", "value": "test@example.com"}]
        Valid constraint_type values: 'equals', 'not equal', 'is_empty', 'is_not_empty',
          'text contains', 'not text contains', 'greater than', 'less than',
          'in', 'not in', 'contains', 'not contains', 'geographic_search'.
    """
    thing_type = config.get("type") or input_data.get("type")
    if not thing_type:
        raise ValueError("bubble.list_things requires 'type'")

    api_key, base_url, version_prefix = await _get_creds(credential_id, db)

    limit = min(int(config.get("limit") or input_data.get("limit", 100)), 100)
    cursor = int(config.get("cursor") or input_data.get("cursor", 0))
    sort_field = config.get("sort_field") or input_data.get("sort_field")
    descending = bool(config.get("descending") or input_data.get("descending", False))

    params: dict = {"limit": limit, "cursor": cursor}
    if sort_field:
        params["sort_field"] = sort_field
        params["descending"] = "true" if descending else "false"

    constraints = config.get("constraints") or input_data.get("constraints")
    if constraints:
        if isinstance(constraints, str):
            import json
            constraints = json.loads(constraints)
        import json
        params["constraints"] = json.dumps(constraints)

    async with _make_client(api_key, base_url) as client:
        r = await client.get(f"/{thing_type}", params=params)
        _raise_for_status(r)
        data = r.json()

    response_data = data.get("response", {})
    log.info("bubble.list_things", type=thing_type, count=response_data.get("count", 0))
    return {
        "things": response_data.get("results", []),
        "count": response_data.get("count", 0),
        "remaining": response_data.get("remaining", 0),
        "cursor": cursor + limit,
    }


@register_node("bubble.create_thing")
async def bubble_create_thing(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new object (Thing) in a Bubble app.

    Params:
      - type (required): The Bubble data type name (e.g. 'product').
      - fields (dict, required): Key-value pairs of field names and values.
        Field names must exactly match the Bubble field names.
    """
    thing_type = config.get("type") or input_data.get("type")
    fields = config.get("fields") or input_data.get("fields")
    if not thing_type:
        raise ValueError("bubble.create_thing requires 'type'")
    if not fields:
        raise ValueError("bubble.create_thing requires 'fields' dict")
    if isinstance(fields, str):
        import json
        fields = json.loads(fields)

    api_key, base_url, _ = await _get_creds(credential_id, db)

    async with _make_client(api_key, base_url) as client:
        r = await client.post(f"/{thing_type}", json=fields)
        _raise_for_status(r)
        data = r.json()

    new_id = data.get("id") or (data.get("response", {}).get("id") if isinstance(data.get("response"), dict) else None)
    log.info("bubble.create_thing", type=thing_type, id=new_id)
    return {"id": new_id, "type": thing_type, "response": data}


@register_node("bubble.update_thing")
async def bubble_update_thing(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update an existing object (Thing) in a Bubble app.

    Params:
      - type (required): The Bubble data type name.
      - thing_id (required): The unique ID of the Thing to update.
      - fields (dict, required): Key-value pairs of fields to update.
    """
    thing_type = config.get("type") or input_data.get("type")
    thing_id = config.get("thing_id") or input_data.get("thing_id")
    fields = config.get("fields") or input_data.get("fields")
    if not thing_type:
        raise ValueError("bubble.update_thing requires 'type'")
    if not thing_id:
        raise ValueError("bubble.update_thing requires 'thing_id'")
    if not fields:
        raise ValueError("bubble.update_thing requires 'fields' dict")
    if isinstance(fields, str):
        import json
        fields = json.loads(fields)

    api_key, base_url, _ = await _get_creds(credential_id, db)

    async with _make_client(api_key, base_url) as client:
        r = await client.patch(f"/{thing_type}/{thing_id}", json=fields)
        _raise_for_status(r)
        # PATCH returns 204 No Content on success; body may be empty
        data = {}
        if r.content:
            try:
                data = r.json()
            except Exception:
                pass

    log.info("bubble.update_thing", type=thing_type, thing_id=thing_id)
    return {"updated": True, "type": thing_type, "thing_id": thing_id, "response": data}


@register_node("bubble.delete_thing")
async def bubble_delete_thing(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Delete an object (Thing) from a Bubble app.

    Params:
      - type (required): The Bubble data type name.
      - thing_id (required): The unique ID of the Thing to delete.
    """
    thing_type = config.get("type") or input_data.get("type")
    thing_id = config.get("thing_id") or input_data.get("thing_id")
    if not thing_type:
        raise ValueError("bubble.delete_thing requires 'type'")
    if not thing_id:
        raise ValueError("bubble.delete_thing requires 'thing_id'")

    api_key, base_url, _ = await _get_creds(credential_id, db)

    async with _make_client(api_key, base_url) as client:
        r = await client.delete(f"/{thing_type}/{thing_id}")
        _raise_for_status(r)

    log.info("bubble.delete_thing", type=thing_type, thing_id=thing_id)
    return {"deleted": True, "type": thing_type, "thing_id": thing_id}


@register_node("bubble.get_thing")
async def bubble_get_thing(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a single object (Thing) by its ID.

    Params:
      - type (required): The Bubble data type name.
      - thing_id (required): The unique ID of the Thing.
    """
    thing_type = config.get("type") or input_data.get("type")
    thing_id = config.get("thing_id") or input_data.get("thing_id")
    if not thing_type:
        raise ValueError("bubble.get_thing requires 'type'")
    if not thing_id:
        raise ValueError("bubble.get_thing requires 'thing_id'")

    api_key, base_url, _ = await _get_creds(credential_id, db)

    async with _make_client(api_key, base_url) as client:
        r = await client.get(f"/{thing_type}/{thing_id}")
        _raise_for_status(r)
        data = r.json()

    thing = data.get("response", data)
    return {"thing": thing, "type": thing_type, "thing_id": thing_id}
