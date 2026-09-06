"""Twin Labs AI browser automation — handler for twin_labs integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.twin-labs.com/v1"


@register_node("twin_labs.run_task")
async def twin_labs_run_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a browser automation task.

    config/input_data:
      api_key — API key or token (required)
      goal — (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    goal = merged.get("goal") or ""
    url = merged.get("url") or ""
    if not goal or not url:
        raise ValueError("goal, url required for twin_labs.run_task")
    payload = {"goal": goal, "url": url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tasks", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("twin_labs.run_task")
    return {"data": data}

@register_node("twin_labs.get_task")
async def twin_labs_get_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get task status.

    config/input_data:
      api_key — API key or token (required)
      task_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    task_id = merged.get("task_id") or ""
    if not task_id:
        raise ValueError("task_id required for twin_labs.get_task")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("twin_labs.get_task")
    return {"data": data}

@register_node("twin_labs.list_tasks")
async def twin_labs_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tasks", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("twin_labs.list_tasks")
    return {"data": data}
