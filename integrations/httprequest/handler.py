"""HttpRequest integration — make arbitrary HTTP requests."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

# SSRF guard: private/loopback CIDR ranges to block
_SSRF_BLOCKED_PREFIXES = (
    "http://localhost",
    "https://localhost",
    "http://127.",
    "https://127.",
    "http://0.",
    "https://0.",
    "http://10.",
    "https://10.",
    "http://172.16.",
    "https://172.16.",
    "http://172.17.",
    "https://172.17.",
    "http://172.18.",
    "https://172.18.",
    "http://172.19.",
    "https://172.19.",
    "http://172.20.",
    "https://172.20.",
    "http://172.21.",
    "https://172.21.",
    "http://172.22.",
    "https://172.22.",
    "http://172.23.",
    "https://172.23.",
    "http://172.24.",
    "https://172.24.",
    "http://172.25.",
    "https://172.25.",
    "http://172.26.",
    "https://172.26.",
    "http://172.27.",
    "https://172.27.",
    "http://172.28.",
    "https://172.28.",
    "http://172.29.",
    "https://172.29.",
    "http://172.30.",
    "https://172.30.",
    "http://172.31.",
    "https://172.31.",
    "http://192.168.",
    "https://192.168.",
    "http://169.254.",  # link-local / cloud metadata
    "https://169.254.",
    "http://[::1]",
    "https://[::1]",
    "http://[fc",
    "https://[fc",
    "http://[fd",
    "https://[fd",
)


def _ssrf_check(url: str) -> None:
    """Raise ValueError if the URL targets a private/internal address."""
    url_lower = url.lower()
    for prefix in _SSRF_BLOCKED_PREFIXES:
        if url_lower.startswith(prefix):
            raise ValueError(
                f"httprequest.make_request: SSRF guard blocked request to private address: {url}"
            )


def _build_auth(auth_type: str, cred: dict) -> httpx.Auth | None:
    """Build an httpx Auth object from credential data."""
    if not cred or auth_type == "none":
        return None
    if auth_type == "basic":
        username = cred.get("username", "")
        password = cred.get("password", "")
        return httpx.BasicAuth(username, password)
    if auth_type == "bearer":
        token = cred.get("token") or cred.get("access_token", "")
        return _BearerAuth(token)
    return None


class _BearerAuth(httpx.Auth):
    def __init__(self, token: str):
        self._token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


@register_node("httprequest.make_request")
async def httprequest_make_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Make an arbitrary HTTP request.

    Config:
        method (str): GET/POST/PUT/DELETE/PATCH (default GET).
        url (str): target URL.
        headers (dict): additional request headers.
        body (dict|str): request body (sent as JSON if dict, raw string otherwise).
        timeout (int): request timeout in seconds (default 30, max 120).
        auth_type (str): none / basic / bearer (default none).
    Credential (optional):
        For basic auth: username, password.
        For bearer auth: token or access_token.
    Returns:
        status_code, headers, body, success (bool).
    """
    method = (config.get("method") or input_data.get("method", "GET")).upper()
    url = config.get("url") or input_data.get("url", "")
    headers: dict = config.get("headers") or input_data.get("headers") or {}
    body = config.get("body") if "body" in config else input_data.get("body")
    timeout = min(int(config.get("timeout") or input_data.get("timeout", 30)), 120)
    auth_type = (config.get("auth_type") or input_data.get("auth_type", "none")).lower()

    if not url:
        raise ValueError("httprequest.make_request: 'url' is required")

    if method not in _ALLOWED_METHODS:
        raise ValueError(
            f"httprequest.make_request: unsupported method '{method}'. "
            f"Allowed: {sorted(_ALLOWED_METHODS)}"
        )

    _ssrf_check(url)

    # Load credential for auth if credential_id is provided
    cred: dict = {}
    if credential_id and auth_type != "none":
        try:
            cred = await get_credential_data(credential_id, db)
        except Exception as exc:
            log.warning("httprequest: could not load credential", error=str(exc))

    auth = _build_auth(auth_type, cred)

    log.info("httprequest.make_request", method=method, url=url, auth_type=auth_type)

    request_kwargs: dict = {
        "method": method,
        "url": url,
        "headers": headers,
        "timeout": timeout,
        "follow_redirects": True,
    }
    if body is not None:
        if isinstance(body, dict):
            request_kwargs["json"] = body
        else:
            request_kwargs["content"] = str(body).encode("utf-8")
    if auth:
        request_kwargs["auth"] = auth

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(**request_kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"httprequest.make_request: request timed out after {timeout}s") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(f"httprequest.make_request: request failed — {exc}") from exc

    # Attempt to parse JSON body, fall back to text
    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    success = 200 <= response.status_code < 300

    log.info(
        "httprequest.make_request completed",
        status_code=response.status_code,
        success=success,
    )

    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": response_body,
        "success": success,
    }
