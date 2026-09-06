"""DocsBot integration — AI documentation chatbot."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://docsbot.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("docsbot.ask_question")
async def docsbot_ask_question(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    bot_id = merged.get("bot_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/bots/{bot_id}/question", json={
            "question": merged.get("question", ""),
            "full_source": merged.get("full_source", False),
        })
        r.raise_for_status()
    return r.json()


@register_node("docsbot.create_bot")
async def docsbot_create_bot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/bots", json={
            "name": merged.get("name", ""),
            "description": merged.get("description", ""),
        })
        r.raise_for_status()
    return r.json()
