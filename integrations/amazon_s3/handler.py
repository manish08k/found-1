"""Amazon S3 (Activepieces variant naming) — handler for amazon_s3 integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL_TEMPLATE = "https://s3.{region}.amazonaws.com"


def _build_base_url(merged: dict) -> str:
    region = merged.get("region") or "us-east-1"
    return BASE_URL_TEMPLATE.format(region=region)


def _build_headers(merged: dict) -> dict:
    api_key = merged.get("access_key_id") or merged.get("api_key") or ""
    api_secret = merged.get("secret_access_key") or merged.get("api_token") or ""
    return {
        "Authorization": f"AWS {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }


@register_node("amazon_s3.list_buckets")
async def amazon_s3_list_buckets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List S3 buckets.

    config/input_data:
      access_key_id / api_key — AWS access key (required)
      secret_access_key / api_token — AWS secret key (required)
      region — AWS region (default us-east-1)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("amazon_s3.list_buckets")
    return {"data": data}

@register_node("amazon_s3.list_objects")
async def amazon_s3_list_objects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List objects in a bucket.

    config/input_data:
      access_key_id / api_key — (required)
      secret_access_key / api_token — (required)
      region — AWS region (default us-east-1)
      bucket — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    bucket = merged.get("bucket") or ""
    if not bucket:
        raise ValueError("bucket required for amazon_s3.list_objects")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/{bucket}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("amazon_s3.list_objects")
    return {"data": data}

@register_node("amazon_s3.get_object")
async def amazon_s3_get_object(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get an object.

    config/input_data:
      access_key_id / api_key — (required)
      secret_access_key / api_token — (required)
      region — AWS region (default us-east-1)
      bucket — (required)
      key — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    bucket = merged.get("bucket") or ""
    key = merged.get("key") or ""
    if not bucket or not key:
        raise ValueError("bucket, key required for amazon_s3.get_object")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/{bucket}/{key}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("amazon_s3.get_object")
    return {"data": data}

@register_node("amazon_s3.put_object")
async def amazon_s3_put_object(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upload an object.

    config/input_data:
      access_key_id / api_key — (required)
      secret_access_key / api_token — (required)
      region — AWS region (default us-east-1)
      bucket — (required)
      key — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    bucket = merged.get("bucket") or ""
    key = merged.get("key") or ""
    body = merged.get("body") or ""
    if not bucket or not key or not body:
        raise ValueError("bucket, key, body required for amazon_s3.put_object")
    payload = {"body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{base_url}/{bucket}/{key}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("amazon_s3.put_object")
    return {"data": data}
