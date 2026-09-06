"""SurveyTale integration — AI-powered surveys and feedback."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.surveytale.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("surveytale.create_survey")
async def surveytale_create_survey(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/surveys", json={
            "title": merged.get("title", ""),
            "description": merged.get("description", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("surveytale.get_responses")
async def surveytale_get_responses(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    survey_id = merged.get("survey_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/surveys/{survey_id}/responses")
        r.raise_for_status()
    return {"responses": r.json()}
