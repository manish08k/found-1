"""Formbricks integration — survey management and response collection."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FORMBRICKS_BASE = "https://app.formbricks.com/api/v1"


def _formbricks_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("formbricks.list_surveys")
async def formbricks_list_surveys(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all surveys in the Formbricks environment.

    config:
      api_key        — Formbricks API key (required)
      environment_id — Formbricks environment ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    environment_id = merged.get("environment_id")
    if not environment_id:
        raise ValueError("environment_id is required for formbricks.list_surveys")

    async with httpx.AsyncClient(base_url=FORMBRICKS_BASE, timeout=30) as client:
        r = await client.get(
            f"/environments/{environment_id}/surveys",
            headers=_formbricks_headers(api_key),
        )
        r.raise_for_status()
        data = r.json()

    surveys = data.get("data", data) if isinstance(data, dict) else data
    log.info("formbricks.list_surveys", environment_id=environment_id, count=len(surveys))
    return {"surveys": surveys, "count": len(surveys)}


@register_node("formbricks.get_survey")
async def formbricks_get_survey(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Formbricks survey.

    config:
      api_key        — Formbricks API key (required)
      environment_id — Formbricks environment ID (required)
      survey_id      — survey ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    environment_id = merged.get("environment_id")
    survey_id = merged.get("survey_id")
    if not environment_id:
        raise ValueError("environment_id is required for formbricks.get_survey")
    if not survey_id:
        raise ValueError("survey_id is required for formbricks.get_survey")

    async with httpx.AsyncClient(base_url=FORMBRICKS_BASE, timeout=30) as client:
        r = await client.get(
            f"/environments/{environment_id}/surveys/{survey_id}",
            headers=_formbricks_headers(api_key),
        )
        r.raise_for_status()
        data = r.json()

    survey = data.get("data", data) if isinstance(data, dict) else data
    log.info("formbricks.get_survey", survey_id=survey_id)
    return {"survey": survey, "survey_id": survey_id}


@register_node("formbricks.list_responses")
async def formbricks_list_responses(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List responses for a specific Formbricks survey.

    config:
      api_key        — Formbricks API key (required)
      environment_id — Formbricks environment ID (required)
      survey_id      — survey ID to fetch responses for (required)
      limit          — max number of responses to return (optional)
      offset         — pagination offset (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    environment_id = merged.get("environment_id")
    survey_id = merged.get("survey_id")
    if not environment_id:
        raise ValueError("environment_id is required for formbricks.list_responses")
    if not survey_id:
        raise ValueError("survey_id is required for formbricks.list_responses")

    params = {}
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]
    if merged.get("offset") is not None:
        params["offset"] = merged["offset"]

    async with httpx.AsyncClient(base_url=FORMBRICKS_BASE, timeout=30) as client:
        r = await client.get(
            f"/environments/{environment_id}/surveys/{survey_id}/responses",
            headers=_formbricks_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    responses = data.get("data", data) if isinstance(data, dict) else data
    log.info("formbricks.list_responses", survey_id=survey_id, count=len(responses))
    return {"responses": responses, "count": len(responses), "survey_id": survey_id}


@register_node("formbricks.create_response")
async def formbricks_create_response(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new response for a Formbricks survey.

    config:
      api_key        — Formbricks API key (required)
      environment_id — Formbricks environment ID (required)
      survey_id      — survey ID to submit response to (required)
      data           — dict of question_id -> answer (required)
      finished       — whether the response is complete (optional, default True)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    environment_id = merged.get("environment_id")
    survey_id = merged.get("survey_id")
    response_data = merged.get("data")
    if not environment_id:
        raise ValueError("environment_id is required for formbricks.create_response")
    if not survey_id:
        raise ValueError("survey_id is required for formbricks.create_response")
    if not response_data:
        raise ValueError("data is required for formbricks.create_response")

    payload = {
        "surveyId": survey_id,
        "data": response_data,
        "finished": merged.get("finished", True),
    }

    async with httpx.AsyncClient(base_url=FORMBRICKS_BASE, timeout=30) as client:
        r = await client.post(
            f"/environments/{environment_id}/responses",
            headers=_formbricks_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    response = data.get("data", data) if isinstance(data, dict) else data
    log.info("formbricks.create_response", survey_id=survey_id)
    return {"response": response, "survey_id": survey_id}
