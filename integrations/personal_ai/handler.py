"""Personal AI integration — personal AI memory and messaging."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.personal.ai/v1"


def _headers(config: dict) -> dict:
    return {"x-api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("personal_ai.send_message")
async def personal_ai_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/message", json={
            "Text": merged.get("message", ""),
            "UserName": merged.get("username", ""),
            "SourceName": merged.get("source_name", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("personal_ai.upload_memory")
async def personal_ai_upload_memory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/memory", json={
            "Text": merged.get("text", ""),
            "SourceName": merged.get("source_name", "upload"),
            "CreatedTime": merged.get("created_time", ""),
        })
        r.raise_for_status()
    return r.json()
