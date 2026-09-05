"""
KoBoToolbox data collection integration.

Provides form and submission management via the KoBoToolbox API v2.

Credential fields:
  - api_key : KoBoToolbox API key (used as Token auth)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://kf.kobotoolbox.org/api/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("KoBoToolbox credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Token {api_key}",
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
        raise ValueError(f"KoBoToolbox API error {r.status_code}: {detail}")


@register_node("kobotoolbox.list_forms")
async def kobo_list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all forms (assets) in KoBoToolbox."""
    limit = min(int(config.get("limit") or input_data.get("limit", 20)), 100)
    offset = int(config.get("offset") or input_data.get("offset", 0))

    log.info("kobotoolbox.list_forms", limit=limit, offset=offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/assets/", params={"limit": limit, "offset": offset, "asset_type": "survey"})
        _raise_for_status(r)
        data = r.json()

    return {"forms": data.get("results", []), "count": data.get("count", 0)}


@register_node("kobotoolbox.get_submissions")
async def kobo_get_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get submissions for a specific form."""
    asset_uid = config.get("asset_uid") or input_data.get("asset_uid")
    if not asset_uid:
        raise ValueError("kobotoolbox.get_submissions requires 'asset_uid'")

    limit = min(int(config.get("limit") or input_data.get("limit", 100)), 30000)
    start = int(config.get("start") or input_data.get("start", 0))

    log.info("kobotoolbox.get_submissions", asset_uid=asset_uid, limit=limit)
    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/assets/{asset_uid}/data/",
            params={"limit": limit, "start": start, "format": "json"},
        )
        _raise_for_status(r)
        data = r.json()

    return {"submissions": data.get("results", []), "count": data.get("count", 0)}


@register_node("kobotoolbox.get_form_data")
async def kobo_get_form_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get metadata and structure for a specific form."""
    asset_uid = config.get("asset_uid") or input_data.get("asset_uid")
    if not asset_uid:
        raise ValueError("kobotoolbox.get_form_data requires 'asset_uid'")

    log.info("kobotoolbox.get_form_data", asset_uid=asset_uid)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/assets/{asset_uid}/")
        _raise_for_status(r)
        data = r.json()

    return {"form": data}


@register_node("kobotoolbox.delete_submission")
async def kobo_delete_submission(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a specific submission from a form."""
    asset_uid = config.get("asset_uid") or input_data.get("asset_uid")
    submission_id = config.get("submission_id") or input_data.get("submission_id")

    if not asset_uid:
        raise ValueError("kobotoolbox.delete_submission requires 'asset_uid'")
    if not submission_id:
        raise ValueError("kobotoolbox.delete_submission requires 'submission_id'")

    log.info("kobotoolbox.delete_submission", asset_uid=asset_uid, submission_id=submission_id)
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/assets/{asset_uid}/data/{submission_id}/")
        _raise_for_status(r)

    return {"deleted": True, "submission_id": submission_id}
