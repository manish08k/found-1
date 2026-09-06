"""Pastebin paste creation and management integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PASTEBIN_API_URL = "https://pastebin.com/api/api_post.php"
PASTEBIN_RAW_URL = "https://pastebin.com/raw"


@register_node("pastebin.create_paste")
async def pastebin_create_paste(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new paste on Pastebin."""
    merged = {**config, **input_data}
    api_dev_key = merged.get("api_dev_key", "")
    if not api_dev_key:
        raise ValueError("api_dev_key is required for pastebin.create_paste")
    content = merged.get("content", merged.get("api_paste_code", ""))
    if not content:
        raise ValueError("content is required for pastebin.create_paste")
    payload = {
        "api_dev_key": api_dev_key,
        "api_option": "paste",
        "api_paste_code": content,
    }
    if merged.get("api_user_key"):
        payload["api_user_key"] = merged["api_user_key"]
    if merged.get("title"):
        payload["api_paste_name"] = merged["title"]
    if merged.get("format"):
        payload["api_paste_format"] = merged["format"]
    if merged.get("privacy"):
        payload["api_paste_private"] = merged["privacy"]
    if merged.get("expire_date"):
        payload["api_paste_expire_date"] = merged["expire_date"]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(PASTEBIN_API_URL, data=payload)
        r.raise_for_status()
        result = r.text
    if result.startswith("Bad API request"):
        raise ValueError(f"Pastebin API error: {result}")
    paste_key = result.split("/")[-1] if "/" in result else result
    log.info("pastebin.create_paste", paste_key=paste_key)
    return {"paste_url": result, "paste_key": paste_key}


@register_node("pastebin.get_paste")
async def pastebin_get_paste(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get raw content of a paste from Pastebin."""
    merged = {**config, **input_data}
    paste_key = merged.get("paste_key", "")
    if not paste_key:
        raise ValueError("paste_key is required for pastebin.get_paste")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{PASTEBIN_RAW_URL}/{paste_key}")
        r.raise_for_status()
        content = r.text
    log.info("pastebin.get_paste", paste_key=paste_key)
    return {"content": content, "paste_key": paste_key, "url": f"https://pastebin.com/{paste_key}"}


@register_node("pastebin.list_pastes")
async def pastebin_list_pastes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List pastes for a Pastebin user."""
    merged = {**config, **input_data}
    api_dev_key = merged.get("api_dev_key", "")
    api_user_key = merged.get("api_user_key", "")
    if not api_dev_key or not api_user_key:
        raise ValueError("api_dev_key and api_user_key are required for pastebin.list_pastes")
    payload = {
        "api_dev_key": api_dev_key,
        "api_user_key": api_user_key,
        "api_option": "list",
        "api_results_limit": merged.get("limit", 50),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(PASTEBIN_API_URL, data=payload)
        r.raise_for_status()
        result = r.text
    if result.startswith("Bad API request"):
        raise ValueError(f"Pastebin API error: {result}")
    log.info("pastebin.list_pastes")
    return {"pastes_xml": result}


@register_node("pastebin.delete_paste")
async def pastebin_delete_paste(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a paste from Pastebin."""
    merged = {**config, **input_data}
    api_dev_key = merged.get("api_dev_key", "")
    api_user_key = merged.get("api_user_key", "")
    paste_key = merged.get("paste_key", "")
    if not api_dev_key or not api_user_key:
        raise ValueError("api_dev_key and api_user_key are required for pastebin.delete_paste")
    if not paste_key:
        raise ValueError("paste_key is required for pastebin.delete_paste")
    payload = {
        "api_dev_key": api_dev_key,
        "api_user_key": api_user_key,
        "api_paste_key": paste_key,
        "api_option": "delete",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(PASTEBIN_API_URL, data=payload)
        r.raise_for_status()
        result = r.text
    if result.startswith("Bad API request"):
        raise ValueError(f"Pastebin API error: {result}")
    log.info("pastebin.delete_paste", paste_key=paste_key)
    return {"deleted": True, "paste_key": paste_key, "response": result}
