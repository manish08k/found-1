"""Backblaze B2 integration — cloud object storage."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BACKBLAZE_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"


async def _authorize(application_key_id: str, application_key: str) -> tuple[str, str, str]:
    """Authorize with Backblaze B2 and return (auth_token, api_url, account_id)."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(BACKBLAZE_AUTH_URL, auth=(application_key_id, application_key))
        r.raise_for_status()
        data = r.json()
    return data["authorizationToken"], data["apiUrl"], data["accountId"]


@register_node("backblaze.list_buckets")
async def backblaze_list_buckets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Backblaze B2 buckets.

    config:
      application_key_id — B2 application key ID (required)
      application_key    — B2 application key (required)
    """
    key_id = config.get("application_key_id") or input_data.get("application_key_id")
    app_key = config.get("application_key") or input_data.get("application_key")

    if not key_id:
        raise ValueError("application_key_id is required for backblaze.list_buckets")
    if not app_key:
        raise ValueError("application_key is required for backblaze.list_buckets")

    auth_token, api_url, account_id = await _authorize(key_id, app_key)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{api_url}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth_token},
            json={"accountId": account_id},
        )
        r.raise_for_status()
        data = r.json()

    buckets = data.get("buckets", [])
    log.info("backblaze.list_buckets", count=len(buckets))
    return {"buckets": buckets, "count": len(buckets), "account_id": account_id}


@register_node("backblaze.list_files")
async def backblaze_list_files(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List files in a Backblaze B2 bucket.

    config:
      application_key_id — B2 application key ID (required)
      application_key    — B2 application key (required)
      bucket_id          — Bucket ID (required)
      max_file_count     — Maximum files to return (default 100)
    """
    key_id = config.get("application_key_id") or input_data.get("application_key_id")
    app_key = config.get("application_key") or input_data.get("application_key")
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")

    if not key_id:
        raise ValueError("application_key_id is required for backblaze.list_files")
    if not app_key:
        raise ValueError("application_key is required for backblaze.list_files")
    if not bucket_id:
        raise ValueError("bucket_id is required for backblaze.list_files")

    max_file_count = int(config.get("max_file_count", 100))
    auth_token, api_url, _ = await _authorize(key_id, app_key)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{api_url}/b2api/v2/b2_list_file_names",
            headers={"Authorization": auth_token},
            json={"bucketId": bucket_id, "maxFileCount": max_file_count},
        )
        r.raise_for_status()
        data = r.json()

    files = data.get("files", [])
    log.info("backblaze.list_files", bucket_id=bucket_id, count=len(files))
    return {"files": files, "count": len(files), "next_file_name": data.get("nextFileName")}


@register_node("backblaze.get_download_url")
async def backblaze_get_download_url(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a download authorization token for a Backblaze B2 file prefix.

    config:
      application_key_id      — B2 application key ID (required)
      application_key         — B2 application key (required)
      bucket_id               — Bucket ID (required)
      file_name_prefix        — File name prefix to authorize (default "")
      valid_duration_seconds  — Token validity in seconds (default 3600)
    """
    key_id = config.get("application_key_id") or input_data.get("application_key_id")
    app_key = config.get("application_key") or input_data.get("application_key")
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")

    if not key_id:
        raise ValueError("application_key_id is required for backblaze.get_download_url")
    if not app_key:
        raise ValueError("application_key is required for backblaze.get_download_url")
    if not bucket_id:
        raise ValueError("bucket_id is required for backblaze.get_download_url")

    file_name_prefix = config.get("file_name_prefix", "")
    valid_duration = int(config.get("valid_duration_seconds", 3600))
    auth_token, api_url, _ = await _authorize(key_id, app_key)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{api_url}/b2api/v2/b2_get_download_authorization",
            headers={"Authorization": auth_token},
            json={
                "bucketId": bucket_id,
                "fileNamePrefix": file_name_prefix,
                "validDurationInSeconds": valid_duration,
            },
        )
        r.raise_for_status()
        data = r.json()

    download_auth = data.get("authorizationToken")
    log.info("backblaze.get_download_url", bucket_id=bucket_id, prefix=file_name_prefix)
    return {
        "bucket_id": bucket_id,
        "file_name_prefix": file_name_prefix,
        "authorization_token": download_auth,
        "valid_duration_seconds": valid_duration,
    }
