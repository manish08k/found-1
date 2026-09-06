"""Pastefy paste creation and management integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERVICE_BASE = "https://pastefy.app/api/v2"


@register_node("pastefy.create_paste")
async def pastefy_create_paste(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new paste on Pastefy."""
    merged = {**config, **input_data}
    token = merged.get("token", merged.get("api_key", ""))
    if not token:
        raise ValueError("token is required for pastefy.create_paste")
    content = merged.get("content", "")
    if not content:
        raise ValueError("content is required for pastefy.create_paste")
    payload = {"content": content}
    if merged.get("title"):
        payload["title"] = merged["title"]
    if merged.get("type"):
        payload["type"] = merged["type"]
    if merged.get("encrypted") is not None:
        payload["encrypted"] = merged["encrypted"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.post("/paste", headers={"Authorization": f"Bearer {token}"}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("pastefy.create_paste")
    return {"paste": data}


@register_node("pastefy.get_paste")
async def pastefy_get_paste(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a paste from Pastefy."""
    merged = {**config, **input_data}
    token = merged.get("token", merged.get("api_key", ""))
    if not token:
        raise ValueError("token is required for pastefy.get_paste")
    paste_id = merged.get("paste_id", "")
    if not paste_id:
        raise ValueError("paste_id is required for pastefy.get_paste")
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get(f"/paste/{paste_id}", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        data = r.json()
    log.info("pastefy.get_paste", paste_id=paste_id)
    return {"paste": data}


@register_node("pastefy.list_pastes")
async def pastefy_list_pastes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List pastes from Pastefy."""
    merged = {**config, **input_data}
    token = merged.get("token", merged.get("api_key", ""))
    if not token:
        raise ValueError("token is required for pastefy.list_pastes")
    params = {}
    if merged.get("page"):
        params["page"] = merged["page"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get("/paste", headers={"Authorization": f"Bearer {token}"}, params=params)
        r.raise_for_status()
        data = r.json()
    pastes = data if isinstance(data, list) else data.get("pastes", data.get("data", []))
    log.info("pastefy.list_pastes", count=len(pastes))
    return {"pastes": pastes, "raw": data}
