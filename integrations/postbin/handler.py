"""
PostBin HTTP request inspector integration.

No authentication required — public API.

Nodes:
  - postbin.create_bin   : Create a new PostBin bin and return its ID.
  - postbin.get_requests : Retrieve all captured requests for a bin.
  - postbin.get_request  : Retrieve a specific request by index/id from a bin.

Base URL: https://www.toptal.com/developers/postbin/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — imported for consistency

log = structlog.get_logger(__name__)

_BASE_URL = "https://www.toptal.com/developers/postbin/api/"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"PostBin API error {r.status_code}: {detail}")


@register_node("postbin.create_bin")
async def create_bin(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new PostBin request bin.

    Config / input keys: none required.

    Returns the bin ID, full bin URL, and expiry information.
    """
    log.info("postbin.create_bin")
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        r = await client.post("bin")
        _raise_for_status(r)
        data = r.json()

    bin_id = data.get("binId") or data.get("id") or data.get("bin_id")
    return {
        "bin_id": bin_id,
        "bin_url": f"https://www.toptal.com/developers/postbin/{bin_id}",
        "api_url": f"{_BASE_URL}bin/{bin_id}/req/shift",
        "expires_at": data.get("expiresAt") or data.get("expires_at"),
        "raw": data,
    }


@register_node("postbin.get_requests")
async def get_requests(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the most recent captured request from a PostBin bin.

    PostBin's API exposes a "shift" endpoint that pops the oldest request.
    This node calls it to retrieve pending requests one at a time.

    Config / input keys:
      - bin_id (str, required) : The PostBin bin ID.
      - max_requests (int)     : Maximum number of requests to retrieve (up to 100). Default 10.
    """
    bin_id = config.get("bin_id") or input_data.get("bin_id")
    if not bin_id:
        raise ValueError("postbin.get_requests requires 'bin_id'")

    max_requests = min(int(config.get("max_requests") or input_data.get("max_requests", 10)), 100)

    log.info("postbin.get_requests", bin_id=bin_id, max_requests=max_requests)
    requests_list = []
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        for _ in range(max_requests):
            r = await client.get(f"bin/{bin_id}/req/shift")
            if r.status_code == 404:
                # No more requests in the bin
                break
            _raise_for_status(r)
            data = r.json()
            if data.get("id") == "no-results":
                break
            requests_list.append(data)

    return {
        "bin_id": bin_id,
        "requests": requests_list,
        "count": len(requests_list),
    }


@register_node("postbin.get_request")
async def get_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a specific request from a PostBin bin by request ID.

    Config / input keys:
      - bin_id (str, required)     : The PostBin bin ID.
      - request_id (str, required) : The request ID (obtained from get_requests or bin UI).
    """
    bin_id = config.get("bin_id") or input_data.get("bin_id")
    request_id = config.get("request_id") or input_data.get("request_id")

    if not bin_id:
        raise ValueError("postbin.get_request requires 'bin_id'")
    if not request_id:
        raise ValueError("postbin.get_request requires 'request_id'")

    log.info("postbin.get_request", bin_id=bin_id, request_id=request_id)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        r = await client.get(f"bin/{bin_id}/req/{request_id}")
        _raise_for_status(r)
        data = r.json()

    return {
        "bin_id": bin_id,
        "request_id": request_id,
        "method": data.get("method"),
        "path": data.get("path"),
        "headers": data.get("headers", {}),
        "body": data.get("body"),
        "query": data.get("query", {}),
        "inserted": data.get("inserted"),
        "raw": data,
    }
