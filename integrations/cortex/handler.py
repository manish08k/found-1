"""
Cortex engineering metrics platform integration.

Provides service catalog management, deployment tracking, and scorecard
retrieval via the Cortex API v1.

Credential fields:
  - api_key : Cortex API key (Bearer auth)

Base URL: https://api.cortex.io/api/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.cortex.io/api/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Cortex credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cortex API error {r.status_code}: {detail}")


@register_node("cortex.list_services")
async def cortex_list_services(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List services in the Cortex service catalog.

    Config:
      - page     : Page number (default 0)
      - page_size: Items per page (default 50)
      - group    : Optional group/team filter
      - type     : Optional service type filter
    """
    page = int(config.get("page") or input_data.get("page", 0))
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 50)), 200)

    params: dict = {"page": page, "pageSize": page_size}
    group = config.get("group") or input_data.get("group")
    if group:
        params["group"] = group
    service_type = config.get("type") or input_data.get("type")
    if service_type:
        params["type"] = service_type

    async with await _client(credential_id, db) as client:
        r = await client.get("/catalog", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "services": data.get("entities", data.get("services", [])),
        "total": data.get("total", 0),
        "page": page,
        "page_size": page_size,
    }


@register_node("cortex.get_service")
async def cortex_get_service(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get details for a specific service in the Cortex catalog.

    Config:
      - service_tag : The unique tag/slug of the service (required)
    """
    service_tag = config.get("service_tag") or input_data.get("service_tag")
    if not service_tag:
        raise ValueError("cortex.get_service requires 'service_tag'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/catalog/{service_tag}")
        _raise_for_status(r)
        data = r.json()

    return {"service": data}


@register_node("cortex.create_deployment")
async def cortex_create_deployment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Record a deployment event for a service in Cortex.

    Config:
      - service_tag   : The unique tag/slug of the service (required)
      - version       : Deployment version/tag (required)
      - environment   : Target environment (e.g. 'production', 'staging') (required)
      - deployer      : Name or email of the deployer
      - sha           : Git commit SHA being deployed
      - title         : Optional deployment title
      - custom_data   : Optional dict of additional metadata
    """
    service_tag = config.get("service_tag") or input_data.get("service_tag")
    version = config.get("version") or input_data.get("version")
    environment = config.get("environment") or input_data.get("environment")

    if not all([service_tag, version, environment]):
        raise ValueError(
            "cortex.create_deployment requires 'service_tag', 'version', and 'environment'"
        )

    payload: dict = {
        "version": version,
        "environment": environment,
    }

    deployer = config.get("deployer") or input_data.get("deployer")
    if deployer:
        payload["deployer"] = {"name": deployer} if "@" not in deployer else {"email": deployer}

    sha = config.get("sha") or input_data.get("sha")
    if sha:
        payload["sha"] = sha

    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    custom_data = config.get("custom_data") or input_data.get("custom_data")
    if custom_data and isinstance(custom_data, dict):
        payload["customData"] = custom_data

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/catalog/{service_tag}/deployments", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"deployment": data, "service_tag": service_tag}


@register_node("cortex.get_scorecard")
async def cortex_get_scorecard(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve scorecard results for a service or all services.

    Config:
      - scorecard_tag : The scorecard identifier (required)
      - service_tag   : Optional — if provided, get score for this specific service;
                        otherwise list all service scores for the scorecard
      - page          : Page number for paginated results (default 0)
      - page_size     : Items per page (default 50)
    """
    scorecard_tag = config.get("scorecard_tag") or input_data.get("scorecard_tag")
    if not scorecard_tag:
        raise ValueError("cortex.get_scorecard requires 'scorecard_tag'")

    service_tag = config.get("service_tag") or input_data.get("service_tag")

    async with await _client(credential_id, db) as client:
        if service_tag:
            r = await client.get(f"/scorecards/{scorecard_tag}/scores/{service_tag}")
            _raise_for_status(r)
            data = r.json()
            return {"scorecard_tag": scorecard_tag, "service_tag": service_tag, "score": data}
        else:
            page = int(config.get("page") or input_data.get("page", 0))
            page_size = min(int(config.get("page_size") or input_data.get("page_size", 50)), 200)
            r = await client.get(
                f"/scorecards/{scorecard_tag}/scores",
                params={"page": page, "pageSize": page_size},
            )
            _raise_for_status(r)
            data = r.json()
            return {
                "scorecard_tag": scorecard_tag,
                "scores": data.get("scores", data.get("items", [])),
                "total": data.get("total", 0),
                "page": page,
            }


@register_node("cortex.list_scorecards")
async def cortex_list_scorecards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all scorecards defined in Cortex.

    Config:
      - page      : Page number (default 0)
      - page_size : Items per page (default 50)
    """
    page = int(config.get("page") or input_data.get("page", 0))
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 50)), 200)

    async with await _client(credential_id, db) as client:
        r = await client.get("/scorecards", params={"page": page, "pageSize": page_size})
        _raise_for_status(r)
        data = r.json()

    return {
        "scorecards": data.get("scorecards", data.get("items", [])),
        "total": data.get("total", 0),
        "page": page,
    }
