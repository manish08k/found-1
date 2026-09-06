"""CustomGPT AI chatbot project integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CUSTOMGPT_BASE = "https://app.customgpt.ai/api/v1"


@register_node("customgpt.list_projects")
async def customgpt_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all CustomGPT projects.

    config/input_data:
      api_token — CustomGPT API token
      page      — optional page number (default 1)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required")

    params: dict = {}
    if merged.get("page"):
        params["page"] = merged["page"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CUSTOMGPT_BASE}/projects",
            headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
            params=params,
        )
        r.raise_for_status()
        result = r.json()

    log.info("customgpt.list_projects")
    return result


@register_node("customgpt.create_project")
async def customgpt_create_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new CustomGPT project.

    config/input_data:
      api_token    — CustomGPT API token
      project_name — name of the project
      sitemap_path — optional sitemap URL to ingest
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required")
    project_name = merged.get("project_name", "")
    if not project_name:
        raise ValueError("project_name is required")

    payload: dict = {"project_name": project_name}
    if merged.get("sitemap_path"):
        payload["sitemap_path"] = merged["sitemap_path"]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{CUSTOMGPT_BASE}/projects",
            headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("customgpt.create_project", project_name=project_name)
    return result


@register_node("customgpt.send_message")
async def customgpt_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a CustomGPT project chatbot.

    config/input_data:
      api_token   — CustomGPT API token
      project_id  — ID of the project
      session_id  — conversation session ID (uuid)
      prompt      — user message
      stream      — optional bool to stream responses (default False)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required")
    project_id = merged.get("project_id", "")
    if not project_id:
        raise ValueError("project_id is required")
    session_id = merged.get("session_id", "")
    if not session_id:
        raise ValueError("session_id is required")
    prompt = merged.get("prompt", "")
    if not prompt:
        raise ValueError("prompt is required")

    payload = {
        "prompt": prompt,
        "stream": merged.get("stream", False),
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{CUSTOMGPT_BASE}/projects/{project_id}/conversations/{session_id}/messages",
            headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("customgpt.send_message", project_id=project_id, session_id=session_id)
    return result


@register_node("customgpt.get_conversation")
async def customgpt_get_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get messages in a CustomGPT conversation session.

    config/input_data:
      api_token  — CustomGPT API token
      project_id — ID of the project
      session_id — conversation session ID
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required")
    project_id = merged.get("project_id", "")
    if not project_id:
        raise ValueError("project_id is required")
    session_id = merged.get("session_id", "")
    if not session_id:
        raise ValueError("session_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CUSTOMGPT_BASE}/projects/{project_id}/conversations/{session_id}/messages",
            headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("customgpt.get_conversation", project_id=project_id, session_id=session_id)
    return result
