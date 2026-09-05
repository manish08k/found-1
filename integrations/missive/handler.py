"""Missive — collaborative email integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MISSIVE_BASE = "https://public.missiveapp.com/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("missive.create_post")
async def missive_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a post in a Missive team conversation.

    config/input_data:
      api_key — Missive API key
      team_id — team ID to post into (required)
      subject — conversation subject/title (required)
      body    — post body in Markdown (required)
    """
    team_id = config.get("team_id") or input_data.get("team_id")
    subject = config.get("subject") or input_data.get("subject")
    body = config.get("body") or input_data.get("body")

    if not team_id:
        raise ValueError("team_id is required for missive.create_post")
    if not subject:
        raise ValueError("subject is required for missive.create_post")
    if not body:
        raise ValueError("body is required for missive.create_post")

    payload = {
        "posts": {
            "team_id": team_id,
            "conversation_subject": subject,
            "markdown": body,
        }
    }

    async with httpx.AsyncClient(base_url=MISSIVE_BASE, timeout=30) as client:
        r = await client.post("/posts", json=payload, headers=_headers(config))
        r.raise_for_status()
        result = r.json()

    log.info("missive.create_post", team_id=team_id, subject=subject)
    return {"post": result, "team_id": team_id}


@register_node("missive.list_conversations")
async def missive_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List conversations from Missive.

    config:
      api_key — Missive API key
      limit   — number of conversations to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=MISSIVE_BASE, timeout=30) as client:
        r = await client.get(
            "/conversations",
            params={"limit": limit},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    conversations = data.get("conversations", data if isinstance(data, list) else [])
    log.info("missive.list_conversations", count=len(conversations))
    return {"conversations": conversations, "count": len(conversations)}
