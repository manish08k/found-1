"""ComfyICU ComfyUI cloud service — handler for comfyicu integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://comfy.icu/api"


@register_node("comfyicu.create_run")
async def comfyicu_create_run(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a ComfyUI run.

    config/input_data:
      api_key — API key or token (required)
      workflow — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workflow = merged.get("workflow") or ""
    if not workflow:
        raise ValueError("workflow required for comfyicu.create_run")
    payload = {"workflow": workflow}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/runs", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("comfyicu.create_run")
    return {"data": data}

@register_node("comfyicu.get_run")
async def comfyicu_get_run(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get run status and results.

    config/input_data:
      api_key — API key or token (required)
      run_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    run_id = merged.get("run_id") or ""
    if not run_id:
        raise ValueError("run_id required for comfyicu.get_run")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/runs/{run_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("comfyicu.get_run")
    return {"data": data}

@register_node("comfyicu.list_runs")
async def comfyicu_list_runs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List runs.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/runs", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("comfyicu.list_runs")
    return {"data": data}
