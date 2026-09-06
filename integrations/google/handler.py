"""Google generic integration — Google APIs via OAuth."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)


@register_node("google.make_request")
async def google_make_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Make an authenticated request to any Google API."""
    merged = {**config, **input_data}
    token = await get_access_token(credential_id, db)
    url = merged.get("url", "")
    method = merged.get("method", "GET").upper()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.request(method, url, json=merged.get("body"), params=merged.get("params"))
        r.raise_for_status()
    return r.json()


@register_node("google.get_user_info")
async def google_get_user_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
        r = await client.get("https://www.googleapis.com/oauth2/v1/userinfo")
        r.raise_for_status()
    return r.json()
