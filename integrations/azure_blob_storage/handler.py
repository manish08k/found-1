"""Azure Blob Storage integration — containers and blob operations via SAS token."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(account_name: str) -> str:
    return f"https://{account_name}.blob.core.windows.net"


@register_node("azure_blob_storage.list_containers")
async def azure_list_containers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all containers in an Azure Blob Storage account.

    config:
      account_name — Storage account name (required)
      sas_token    — SAS token including leading '?' (required)
    """
    account_name = config.get("account_name") or input_data.get("account_name")
    sas_token = config.get("sas_token") or input_data.get("sas_token")

    if not account_name:
        raise ValueError("account_name is required for azure_blob_storage.list_containers")
    if not sas_token:
        raise ValueError("sas_token is required for azure_blob_storage.list_containers")

    base = _base_url(account_name)
    url = f"{base}/{sas_token}&comp=list" if "?" in sas_token else f"{base}/?comp=list{sas_token}"
    url = f"{base}/{sas_token.lstrip('?')}" if not sas_token.startswith("?") else f"{base}/{sas_token}"
    # Build cleanly
    url = f"{base}/"
    params_str = sas_token.lstrip("?")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params={**dict(p.split("=", 1) for p in params_str.split("&") if "=" in p), "comp": "list"})
        r.raise_for_status()
        content = r.text

    log.info("azure_blob_storage.list_containers", account_name=account_name)
    return {"account_name": account_name, "xml_response": content}


@register_node("azure_blob_storage.list_blobs")
async def azure_list_blobs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List blobs in an Azure Blob Storage container.

    config:
      account_name   — Storage account name (required)
      container_name — Container name (required)
      sas_token      — SAS token including leading '?' (required)
    """
    account_name = config.get("account_name") or input_data.get("account_name")
    container_name = config.get("container_name") or input_data.get("container_name")
    sas_token = config.get("sas_token") or input_data.get("sas_token")

    if not account_name:
        raise ValueError("account_name is required for azure_blob_storage.list_blobs")
    if not container_name:
        raise ValueError("container_name is required for azure_blob_storage.list_blobs")
    if not sas_token:
        raise ValueError("sas_token is required for azure_blob_storage.list_blobs")

    base = _base_url(account_name)
    url = f"{base}/{container_name}"
    params_str = sas_token.lstrip("?")
    params = {**dict(p.split("=", 1) for p in params_str.split("&") if "=" in p), "restype": "container", "comp": "list"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        content = r.text

    log.info("azure_blob_storage.list_blobs", account_name=account_name, container=container_name)
    return {"account_name": account_name, "container_name": container_name, "xml_response": content}


@register_node("azure_blob_storage.upload_blob")
async def azure_upload_blob(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upload a blob to Azure Blob Storage.

    config/input_data:
      account_name   — Storage account name (required)
      container_name — Container name (required)
      blob_name      — Blob name / path (required)
      sas_token      — SAS token including leading '?' (required)
      content        — Content to upload as string (required)
      content_type   — MIME type (default "application/octet-stream")
    """
    account_name = config.get("account_name") or input_data.get("account_name")
    container_name = config.get("container_name") or input_data.get("container_name")
    blob_name = config.get("blob_name") or input_data.get("blob_name")
    sas_token = config.get("sas_token") or input_data.get("sas_token")
    content = config.get("content") or input_data.get("content", "")
    content_type = config.get("content_type", "application/octet-stream")

    if not account_name:
        raise ValueError("account_name is required for azure_blob_storage.upload_blob")
    if not container_name:
        raise ValueError("container_name is required for azure_blob_storage.upload_blob")
    if not blob_name:
        raise ValueError("blob_name is required for azure_blob_storage.upload_blob")
    if not sas_token:
        raise ValueError("sas_token is required for azure_blob_storage.upload_blob")

    base = _base_url(account_name)
    url = f"{base}/{container_name}/{blob_name}"
    params_str = sas_token.lstrip("?")
    params = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in params_str.split("&") if "=" in p}

    headers = {
        "Content-Type": content_type,
        "x-ms-blob-type": "BlockBlob",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.put(url, params=params, headers=headers, content=content.encode() if isinstance(content, str) else content)
        r.raise_for_status()

    log.info("azure_blob_storage.upload_blob", account_name=account_name, container=container_name, blob=blob_name)
    return {
        "account_name": account_name,
        "container_name": container_name,
        "blob_name": blob_name,
        "status": "uploaded",
        "url": f"{base}/{container_name}/{blob_name}",
    }


@register_node("azure_blob_storage.download_blob")
async def azure_download_blob(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Download a blob from Azure Blob Storage.

    config/input_data:
      account_name   — Storage account name (required)
      container_name — Container name (required)
      blob_name      — Blob name / path (required)
      sas_token      — SAS token including leading '?' (required)
    """
    account_name = config.get("account_name") or input_data.get("account_name")
    container_name = config.get("container_name") or input_data.get("container_name")
    blob_name = config.get("blob_name") or input_data.get("blob_name")
    sas_token = config.get("sas_token") or input_data.get("sas_token")

    if not account_name:
        raise ValueError("account_name is required for azure_blob_storage.download_blob")
    if not container_name:
        raise ValueError("container_name is required for azure_blob_storage.download_blob")
    if not blob_name:
        raise ValueError("blob_name is required for azure_blob_storage.download_blob")
    if not sas_token:
        raise ValueError("sas_token is required for azure_blob_storage.download_blob")

    base = _base_url(account_name)
    url = f"{base}/{container_name}/{blob_name}"
    params_str = sas_token.lstrip("?")
    params = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in params_str.split("&") if "=" in p}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        content = r.text
        content_type = r.headers.get("Content-Type", "")

    log.info("azure_blob_storage.download_blob", account_name=account_name, container=container_name, blob=blob_name)
    return {
        "account_name": account_name,
        "container_name": container_name,
        "blob_name": blob_name,
        "content": content,
        "content_type": content_type,
        "size_bytes": len(r.content),
    }
