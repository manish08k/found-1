"""MySendingBox integration — physical mail and postal services."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.mysendingbox.fr/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("mysendingbox.send_letter")
async def mysendingbox_send_letter(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/letters", json={
            "to": merged.get("to", {}),
            "from": merged.get("from_address", {}),
            "file": merged.get("file_url", ""),
            "color": merged.get("color", "bw"),
        })
        r.raise_for_status()
    return r.json()


@register_node("mysendingbox.get_letters")
async def mysendingbox_get_letters(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/letters", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"letters": r.json()}
