"""OpenMic AI integration — voice AI and speech processing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.openmic.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("openmic_ai.transcribe")
async def openmic_ai_transcribe(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/transcribe", json={"audio_url": merged.get("audio_url", "")})
        r.raise_for_status()
    return r.json()


@register_node("openmic_ai.synthesize")
async def openmic_ai_synthesize(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/synthesize", json={
            "text": merged.get("text", ""),
            "voice": merged.get("voice", "default"),
        })
        r.raise_for_status()
    return r.json()
