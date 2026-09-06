"""SlideSpeak integration — AI presentation generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://slidespeak-api.uk.r.appspot.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("slidespeak.generate_presentation")
async def slidespeak_generate_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=120) as client:
        r = await client.post(f"{BASE}/presentation/generate", json={
            "plain_text": merged.get("text", ""),
            "length": merged.get("num_slides", 10),
            "theme": merged.get("theme", "default"),
            "language": merged.get("language", "ENGLISH"),
        })
        r.raise_for_status()
    return r.json()
