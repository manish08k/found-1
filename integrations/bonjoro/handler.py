"""Bonjoro personal video messaging — handler for bonjoro integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bonjoro.com/api/v1"


@register_node("bonjoro.list_tasks")
async def bonjoro_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List video tasks.

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
    log.info("bonjoro.list_tasks")
    return {"data": data}

@register_node("bonjoro.create_task")
async def bonjoro_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a video task.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    name = merged.get("name") or ""
    if not email or not name:
        raise ValueError("email, name required for bonjoro.create_task")
    payload = {"email": email, "name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tasks", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bonjoro.create_task")
    return {"data": data}

@register_node("bonjoro.get_task")
async def bonjoro_get_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get task details.

    config/input_data:
      api_key — API key or token (required)
      task_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    task_id = merged.get("task_id") or ""
    if not task_id:
        raise ValueError("task_id required for bonjoro.get_task")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bonjoro.get_task")
    return {"data": data}
