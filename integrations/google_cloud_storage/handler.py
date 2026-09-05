"""Google Cloud Storage integration — buckets and objects."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GCS_BASE = "https://storage.googleapis.com/storage/v1"
GCS_UPLOAD_BASE = "https://storage.googleapis.com/upload/storage/v1"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("google_cloud_storage.list_buckets")
async def gcs_list_buckets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List GCS buckets for a project.

    config:
      access_token — GCP OAuth2 access token (required)
      project_id   — GCP project ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    project_id = config.get("project_id") or input_data.get("project_id")

    if not access_token:
        raise ValueError("access_token is required for google_cloud_storage.list_buckets")
    if not project_id:
        raise ValueError("project_id is required for google_cloud_storage.list_buckets")

    async with httpx.AsyncClient(base_url=GCS_BASE, timeout=30) as client:
        r = await client.get("/b", headers=_headers(access_token), params={"project": project_id})
        r.raise_for_status()
        data = r.json()

    buckets = data.get("items", [])
    log.info("google_cloud_storage.list_buckets", project_id=project_id, count=len(buckets))
    return {"buckets": buckets, "count": len(buckets), "next_page_token": data.get("nextPageToken")}


@register_node("google_cloud_storage.list_objects")
async def gcs_list_objects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List objects in a GCS bucket.

    config:
      access_token — GCP OAuth2 access token (required)
      bucket       — Bucket name (required)
      max_results  — Maximum number of results (default 25)
      prefix       — Filter by prefix (optional)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    bucket = config.get("bucket") or input_data.get("bucket")

    if not access_token:
        raise ValueError("access_token is required for google_cloud_storage.list_objects")
    if not bucket:
        raise ValueError("bucket is required for google_cloud_storage.list_objects")

    max_results = int(config.get("max_results", 25))
    params: dict = {"maxResults": max_results}
    prefix = config.get("prefix") or input_data.get("prefix")
    if prefix:
        params["prefix"] = prefix

    async with httpx.AsyncClient(base_url=GCS_BASE, timeout=30) as client:
        r = await client.get(f"/b/{bucket}/o", headers=_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    objects = data.get("items", [])
    log.info("google_cloud_storage.list_objects", bucket=bucket, count=len(objects))
    return {"objects": objects, "count": len(objects), "bucket": bucket, "next_page_token": data.get("nextPageToken")}


@register_node("google_cloud_storage.upload_object")
async def gcs_upload_object(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upload an object to a GCS bucket.

    config/input_data:
      access_token — GCP OAuth2 access token (required)
      bucket       — Bucket name (required)
      object_name  — Destination object name (required)
      content      — Content to upload as string (required)
      content_type — MIME type (default "text/plain")
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    bucket = config.get("bucket") or input_data.get("bucket")
    object_name = config.get("object_name") or input_data.get("object_name")
    content = config.get("content") or input_data.get("content", "")
    content_type = config.get("content_type", "text/plain")

    if not access_token:
        raise ValueError("access_token is required for google_cloud_storage.upload_object")
    if not bucket:
        raise ValueError("bucket is required for google_cloud_storage.upload_object")
    if not object_name:
        raise ValueError("object_name is required for google_cloud_storage.upload_object")

    upload_url = f"{GCS_UPLOAD_BASE}/b/{bucket}/o"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": content_type,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            upload_url,
            headers=headers,
            params={"uploadType": "media", "name": object_name},
            content=content.encode() if isinstance(content, str) else content,
        )
        r.raise_for_status()
        obj = r.json()

    log.info("google_cloud_storage.upload_object", bucket=bucket, object_name=object_name)
    return {"object": obj, "bucket": bucket, "object_name": object_name, "size": obj.get("size"), "media_link": obj.get("mediaLink")}


@register_node("google_cloud_storage.get_object")
async def gcs_get_object(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Download an object from GCS (returns content as string).

    config/input_data:
      access_token — GCP OAuth2 access token (required)
      bucket       — Bucket name (required)
      object_name  — Object name (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    bucket = config.get("bucket") or input_data.get("bucket")
    object_name = config.get("object_name") or input_data.get("object_name")

    if not access_token:
        raise ValueError("access_token is required for google_cloud_storage.get_object")
    if not bucket:
        raise ValueError("bucket is required for google_cloud_storage.get_object")
    if not object_name:
        raise ValueError("object_name is required for google_cloud_storage.get_object")

    async with httpx.AsyncClient(base_url=GCS_BASE, timeout=60) as client:
        r = await client.get(
            f"/b/{bucket}/o/{httpx.URL(object_name)}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"alt": "media"},
        )
        r.raise_for_status()
        content = r.text
        content_type = r.headers.get("Content-Type", "")

    log.info("google_cloud_storage.get_object", bucket=bucket, object_name=object_name)
    return {
        "bucket": bucket,
        "object_name": object_name,
        "content": content,
        "content_type": content_type,
        "size_bytes": len(r.content),
    }
