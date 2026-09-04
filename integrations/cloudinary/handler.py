"""
Cloudinary integration.

Credential fields:
  - cloud_name: Cloudinary cloud name
  - api_key: Cloudinary API key
  - api_secret: Cloudinary API secret

Auth: HTTP Basic with api_key:api_secret
Base URL: https://api.cloudinary.com/v1_1/{cloud_name}
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    cloud_name = creds.get("cloud_name")
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    if not cloud_name:
        raise ValueError("Cloudinary credential is missing 'cloud_name'")
    if not api_key:
        raise ValueError("Cloudinary credential is missing 'api_key'")
    if not api_secret:
        raise ValueError("Cloudinary credential is missing 'api_secret'")
    base_url = f"https://api.cloudinary.com/v1_1/{cloud_name}"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(api_key, api_secret),
        timeout=60.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cloudinary API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching usage stats."""
    creds = await get_credential_data(credential_id, db)
    cloud_name = creds.get("cloud_name")
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/usage",
            auth=(api_key, api_secret),
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Resources (Images, Videos, Files)
# ---------------------------------------------------------------------------

@register_node("cloudinary.upload_image")
async def cloudinary_upload_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{resource_type}/upload — upload a resource to Cloudinary."""
    file_url = config.get("file") or input_data.get("file")
    if not file_url:
        raise ValueError("cloudinary.upload_image requires 'file' (URL or base64 data URI)")
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    creds = await get_credential_data(credential_id, db)
    cloud_name = creds.get("cloud_name")
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    data: dict = {"file": file_url, "api_key": api_key}
    public_id = config.get("public_id") or input_data.get("public_id")
    if public_id:
        data["public_id"] = public_id
    folder = config.get("folder") or input_data.get("folder")
    if folder:
        data["folder"] = folder
    tags = config.get("tags") or input_data.get("tags")
    if tags:
        data["tags"] = tags if isinstance(tags, str) else ",".join(tags)
    transformation = config.get("transformation") or input_data.get("transformation")
    if transformation:
        data["transformation"] = transformation
    # Generate signature
    import hashlib
    import time
    timestamp = str(int(time.time()))
    data["timestamp"] = timestamp
    params_to_sign = {k: v for k, v in data.items() if k not in ("file", "api_key")}
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params_to_sign.items()))
    signature_str = sorted_params + api_secret
    data["signature"] = hashlib.sha1(signature_str.encode()).hexdigest()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload",
            data=data,
        )
    return _check(r)


@register_node("cloudinary.get_resource")
async def cloudinary_get_resource(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /resources/{resource_type}/{public_id} — get resource details."""
    public_id = config.get("public_id") or input_data.get("public_id")
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    delivery_type = config.get("type") or input_data.get("type", "upload")
    if not public_id:
        raise ValueError("cloudinary.get_resource requires 'public_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/resources/{resource_type}/{delivery_type}/{public_id}")
    return _check(r)


@register_node("cloudinary.delete_resource")
async def cloudinary_delete_resource(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /resources/{resource_type}/upload — delete resources by public IDs."""
    public_ids = config.get("public_ids") or input_data.get("public_ids")
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    if not public_ids:
        raise ValueError("cloudinary.delete_resource requires 'public_ids' list")
    if isinstance(public_ids, str):
        public_ids = [public_ids]
    async with await _client(credential_id, db) as client:
        r = await client.delete(
            f"/resources/{resource_type}/upload",
            params={"public_ids[]": public_ids},
        )
    return _check(r)


@register_node("cloudinary.list_resources")
async def cloudinary_list_resources(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /resources/{resource_type} — list resources."""
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    params: dict = {}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = int(max_results)
    next_cursor = config.get("next_cursor") or input_data.get("next_cursor")
    if next_cursor:
        params["next_cursor"] = next_cursor
    prefix = config.get("prefix") or input_data.get("prefix")
    if prefix:
        params["prefix"] = prefix
    folder = config.get("folder") or input_data.get("folder")
    if folder:
        params["prefix"] = folder
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/resources/{resource_type}", params=params)
    return _check(r)


@register_node("cloudinary.transform_image")
async def cloudinary_transform_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return a transformed image URL (no API call, URL generation only)."""
    public_id = config.get("public_id") or input_data.get("public_id")
    transformation = config.get("transformation") or input_data.get("transformation", "")
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    if not public_id:
        raise ValueError("cloudinary.transform_image requires 'public_id'")
    creds = await get_credential_data(credential_id, db)
    cloud_name = creds.get("cloud_name")
    if transformation:
        url = f"https://res.cloudinary.com/{cloud_name}/{resource_type}/upload/{transformation}/{public_id}"
    else:
        url = f"https://res.cloudinary.com/{cloud_name}/{resource_type}/upload/{public_id}"
    return {"url": url, "public_id": public_id, "transformation": transformation}


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

@register_node("cloudinary.list_folders")
async def cloudinary_list_folders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /folders — list root folders, or subfolders with path."""
    folder_path = config.get("folder") or input_data.get("folder")
    async with await _client(credential_id, db) as client:
        if folder_path:
            r = await client.get(f"/folders/{folder_path}")
        else:
            r = await client.get("/folders")
    return _check(r)


@register_node("cloudinary.create_folder")
async def cloudinary_create_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /folders/{path} — create a folder."""
    folder_path = config.get("folder") or input_data.get("folder")
    if not folder_path:
        raise ValueError("cloudinary.create_folder requires 'folder' path")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/folders/{folder_path}")
    return _check(r)


# ---------------------------------------------------------------------------
# Rename Resource
# ---------------------------------------------------------------------------

@register_node("cloudinary.rename_resource")
async def cloudinary_rename_resource(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /resources/{resource_type}/upload/rename — rename a resource."""
    from_public_id = config.get("from_public_id") or input_data.get("from_public_id")
    to_public_id = config.get("to_public_id") or input_data.get("to_public_id")
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    if not from_public_id or not to_public_id:
        raise ValueError("cloudinary.rename_resource requires 'from_public_id' and 'to_public_id'")
    creds = await get_credential_data(credential_id, db)
    cloud_name = creds.get("cloud_name")
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    import hashlib
    import time
    timestamp = str(int(time.time()))
    params_to_sign = {
        "from_public_id": from_public_id,
        "timestamp": timestamp,
        "to_public_id": to_public_id,
    }
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params_to_sign.items()))
    signature = hashlib.sha1((sorted_params + api_secret).encode()).hexdigest()
    data: dict = {
        "from_public_id": from_public_id,
        "to_public_id": to_public_id,
        "timestamp": timestamp,
        "api_key": api_key,
        "signature": signature,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/rename",
            data=data,
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@register_node("cloudinary.list_tags")
async def cloudinary_list_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tags/{resource_type} — list tags used in the account."""
    resource_type = config.get("resource_type") or input_data.get("resource_type", "image")
    params: dict = {}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = int(max_results)
    prefix = config.get("prefix") or input_data.get("prefix")
    if prefix:
        params["prefix"] = prefix
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/tags/{resource_type}", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@register_node("cloudinary.search_resources")
async def cloudinary_search_resources(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /resources/search — search resources using Cloudinary Search API."""
    expression = config.get("expression") or input_data.get("expression", "")
    body: dict = {"expression": expression}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        body["max_results"] = int(max_results)
    sort_by = config.get("sort_by") or input_data.get("sort_by")
    if sort_by:
        body["sort_by"] = sort_by
    with_field = config.get("with_field") or input_data.get("with_field")
    if with_field:
        body["with_field"] = with_field
    next_cursor = config.get("next_cursor") or input_data.get("next_cursor")
    if next_cursor:
        body["next_cursor"] = next_cursor
    async with await _client(credential_id, db) as client:
        r = await client.post("/resources/search", json=body)
    return _check(r)
