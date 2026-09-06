"""Fireflies AI integration — meeting transcription and analysis."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.fireflies.ai/graphql"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("fireflies_ai.get_transcripts")
async def fireflies_ai_get_transcripts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    query = """query { transcripts(limit: %d) { id title date duration summary { keywords action_items } } }""" % merged.get("limit", 10)
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(BASE, json={"query": query})
        r.raise_for_status()
    return r.json()


@register_node("fireflies_ai.get_transcript")
async def fireflies_ai_get_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    tid = merged.get("transcript_id", "")
    query = f"""query {{ transcript(id: "{tid}") {{ id title date sentences {{ text speaker_name start_time end_time }} }} }}"""
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(BASE, json={"query": query})
        r.raise_for_status()
    return r.json()
