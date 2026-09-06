"""HTTP OAuth2 integration — make authenticated HTTP requests with OAuth2."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)


@register_node("http_oauth2.request")
async def http_oauth2_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await get_access_token(credential_id, db)
    url = merged.get("url", "")
    method = merged.get("method", "GET").upper()
    headers = {
        "Authorization": f"Bearer {token}",
        **(merged.get("headers", {})),
    }
    async with httpx.AsyncClient(headers=headers, timeout=merged.get("timeout", 30)) as client:
        r = await client.request(
            method, url,
            json=merged.get("body") if method in ("POST", "PUT", "PATCH") else None,
            params=merged.get("params"),
        )
        r.raise_for_status()
    try:
        return {"body": r.json(), "status_code": r.status_code}
    except Exception:
        return {"body": r.text, "status_code": r.status_code}
