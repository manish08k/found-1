"""Browse AI web scraping and monitoring — handler for browse_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.browse.ai/v2"


@register_node("browse_ai.list_robots")
async def browse_ai_list_robots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all robots.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/robots", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("browse_ai.list_robots")
    return {"data": data}

@register_node("browse_ai.run_robot")
async def browse_ai_run_robot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a robot task.

    config/input_data:
      api_key — API key or token (required)
      robot_id — (required)
      input_parameters — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    robot_id = merged.get("robot_id") or ""
    input_parameters = merged.get("input_parameters") or ""
    if not robot_id or not input_parameters:
        raise ValueError("robot_id, input_parameters required for browse_ai.run_robot")
    payload = {"input_parameters": input_parameters}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/robots/{robot_id}/tasks", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("browse_ai.run_robot")
    return {"data": data}

@register_node("browse_ai.get_task")
async def browse_ai_get_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get task results.

    config/input_data:
      api_key — API key or token (required)
      robot_id — (required)
      task_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    robot_id = merged.get("robot_id") or ""
    task_id = merged.get("task_id") or ""
    if not robot_id or not task_id:
        raise ValueError("robot_id, task_id required for browse_ai.get_task")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/robots/{robot_id}/tasks/{task_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("browse_ai.get_task")
    return {"data": data}
