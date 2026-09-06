"""Bland AI phone call automation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BLAND_BASE = "https://api.bland.ai/v1"


@register_node("bland_ai.make_call")
async def bland_ai_make_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Initiate an AI phone call using Bland AI.

    config/input_data:
      api_key       — Bland AI API key
      phone_number  — E.164 format phone number to call
      task          — description of what the AI should accomplish
      voice         — optional voice ID or name
      pathway_id    — optional pathway ID to use
      max_duration  — optional max call duration in minutes (default 12)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    phone_number = merged.get("phone_number", "")
    if not phone_number:
        raise ValueError("phone_number is required")

    payload: dict = {"phone_number": phone_number}
    if merged.get("task"):
        payload["task"] = merged["task"]
    if merged.get("pathway_id"):
        payload["pathway_id"] = merged["pathway_id"]
    if merged.get("voice"):
        payload["voice"] = merged["voice"]
    if merged.get("max_duration"):
        payload["max_duration"] = merged["max_duration"]
    if merged.get("request_data"):
        payload["request_data"] = merged["request_data"]
    if merged.get("first_sentence"):
        payload["first_sentence"] = merged["first_sentence"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BLAND_BASE}/calls",
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("bland_ai.make_call", call_id=result.get("call_id"))
    return result


@register_node("bland_ai.get_call")
async def bland_ai_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a Bland AI phone call.

    config/input_data:
      api_key — Bland AI API key
      call_id — ID of the call to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    call_id = merged.get("call_id", "")
    if not call_id:
        raise ValueError("call_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BLAND_BASE}/calls/{call_id}",
            headers={"Authorization": api_key},
        )
        r.raise_for_status()
        result = r.json()

    log.info("bland_ai.get_call", call_id=call_id)
    return result


@register_node("bland_ai.list_calls")
async def bland_ai_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recent Bland AI phone calls.

    config/input_data:
      api_key — Bland AI API key
      limit   — optional number of calls to return (default 1000)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    params: dict = {}
    if merged.get("limit"):
        params["limit"] = merged["limit"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BLAND_BASE}/calls",
            headers={"Authorization": api_key},
            params=params,
        )
        r.raise_for_status()
        result = r.json()

    log.info("bland_ai.list_calls")
    return result


@register_node("bland_ai.analyze_call")
async def bland_ai_analyze_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Analyze a Bland AI call with a custom prompt.

    config/input_data:
      api_key  — Bland AI API key
      call_id  — ID of the call to analyze
      goal     — description of the analysis goal
      questions — optional list of [question, type] pairs for structured extraction
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    call_id = merged.get("call_id", "")
    if not call_id:
        raise ValueError("call_id is required")
    goal = merged.get("goal", "")
    if not goal:
        raise ValueError("goal is required")

    payload: dict = {"goal": goal}
    if merged.get("questions"):
        payload["questions"] = merged["questions"]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BLAND_BASE}/calls/{call_id}/analyze",
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("bland_ai.analyze_call", call_id=call_id)
    return result
