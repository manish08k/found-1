"""Recall AI integration — meeting recording and transcription bots."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://us-east-1.recall.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Token {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("recall_ai.create_bot")
async def recall_ai_create_bot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/bot", json={
            "meeting_url": merged.get("meeting_url", ""),
            "bot_name": merged.get("bot_name", "Meeting Recorder"),
            "transcription_options": {"provider": merged.get("transcription_provider", "assembly_ai")},
        })
        r.raise_for_status()
    return r.json()


@register_node("recall_ai.get_bot")
async def recall_ai_get_bot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    bot_id = merged.get("bot_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/bot/{bot_id}/")
        r.raise_for_status()
    return r.json()


@register_node("recall_ai.get_transcript")
async def recall_ai_get_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    bot_id = merged.get("bot_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/bot/{bot_id}/transcript/")
        r.raise_for_status()
    return {"transcript": r.json()}
