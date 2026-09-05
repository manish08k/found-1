"""Teamhood kanban integration — boards and tasks."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TEAMHOOD_BASE = "https://teamhood.com/api/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("teamhood.list_boards")
async def teamhood_list_boards(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List boards in a Teamhood workspace.

    config:
      api_key      — Teamhood API key (required)
      workspace_id — workspace ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for teamhood.list_boards")

    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("workspace_id is required for teamhood.list_boards")

    async with httpx.AsyncClient(base_url=TEAMHOOD_BASE, timeout=30) as client:
        r = await client.get(f"/workspaces/{workspace_id}/boards", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    boards = data if isinstance(data, list) else data.get("boards", [])
    log.info("teamhood.list_boards", workspace_id=workspace_id, count=len(boards))
    return {"boards": boards, "count": len(boards)}


@register_node("teamhood.list_tasks")
async def teamhood_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks on a Teamhood board.

    config:
      api_key  — Teamhood API key (required)
      board_id — board ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for teamhood.list_tasks")

    board_id = config.get("board_id") or input_data.get("board_id")
    if not board_id:
        raise ValueError("board_id is required for teamhood.list_tasks")

    async with httpx.AsyncClient(base_url=TEAMHOOD_BASE, timeout=30) as client:
        r = await client.get(f"/boards/{board_id}/tasks", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    tasks = data if isinstance(data, list) else data.get("tasks", [])
    log.info("teamhood.list_tasks", board_id=board_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("teamhood.create_task")
async def teamhood_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task item on a Teamhood board.

    config/input_data:
      api_key  — Teamhood API key (required)
      board_id — board ID to create the task on (required)
      name     — task name (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for teamhood.create_task")

    board_id = config.get("board_id") or input_data.get("board_id")
    name = config.get("name") or input_data.get("name")
    if not board_id or not name:
        raise ValueError("board_id and name are required for teamhood.create_task")

    payload = {"name": name}

    async with httpx.AsyncClient(base_url=TEAMHOOD_BASE, timeout=30) as client:
        r = await client.post(f"/boards/{board_id}/items", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        task = r.json()

    log.info("teamhood.create_task", board_id=board_id, name=name)
    return {"task": task, "task_id": task.get("id") if isinstance(task, dict) else None}
