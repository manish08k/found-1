"""Bursty AI content generation — handler for bursty_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.burstyai.com/v1"


@register_node("bursty_ai.generate")
async def bursty_ai_generate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate content.

    config/input_data:
      api_key — API key or token (required)
      prompt — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = merged.get("prompt") or ""
    if not prompt:
        raise ValueError("prompt required for bursty_ai.generate")
    payload = {"prompt": prompt}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/generate", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bursty_ai.generate")
    return {"data": data}

@register_node("bursty_ai.list_workflows")
async def bursty_ai_list_workflows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List workflows.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/workflows", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bursty_ai.list_workflows")
    return {"data": data}

@register_node("bursty_ai.run_workflow")
async def bursty_ai_run_workflow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a workflow.

    config/input_data:
      api_key — API key or token (required)
      workflow_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workflow_id = merged.get("workflow_id") or ""
    if not workflow_id:
        raise ValueError("workflow_id required for bursty_ai.run_workflow")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/workflows/{workflow_id}/run", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bursty_ai.run_workflow")
    return {"data": data}
