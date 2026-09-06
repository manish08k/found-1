"""SimplyPrint 3D print farm management integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(shop_id: str) -> str:
    return f"https://apiv2.simplyprint.io/{shop_id}"


@register_node("simplyprint.list_printers")
async def simplyprint_list_printers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all printers in the shop."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    shop_id = merged.get("shop_id", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not shop_id:
        raise ValueError("shop_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_base_url(shop_id)}/printers/get",
            headers={"x-api-key": api_key},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplyprint.list_printers")
    return result


@register_node("simplyprint.get_printer")
async def simplyprint_get_printer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details for a specific printer."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    shop_id = merged.get("shop_id", "")
    printer_id = merged.get("printer_id", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not shop_id:
        raise ValueError("shop_id is required")
    if not printer_id:
        raise ValueError("printer_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_base_url(shop_id)}/printers/get",
            headers={"x-api-key": api_key},
            params={"pid": printer_id},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplyprint.get_printer")
    return result


@register_node("simplyprint.list_print_jobs")
async def simplyprint_list_print_jobs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List print jobs for the shop."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    shop_id = merged.get("shop_id", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not shop_id:
        raise ValueError("shop_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_base_url(shop_id)}/jobs/list",
            headers={"x-api-key": api_key},
            params={"page": merged.get("page", 1), "page_size": merged.get("page_size", 20)},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplyprint.list_print_jobs")
    return result


@register_node("simplyprint.create_print_job")
async def simplyprint_create_print_job(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new print job."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    shop_id = merged.get("shop_id", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not shop_id:
        raise ValueError("shop_id is required")
    payload = {
        "printer_id": merged.get("printer_id", ""),
        "file_id": merged.get("file_id", ""),
        "note": merged.get("note", ""),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_base_url(shop_id)}/jobs/create",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplyprint.create_print_job")
    return result
