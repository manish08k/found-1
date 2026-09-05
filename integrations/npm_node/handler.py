"""
npm package registry integration.

Auth: Bearer token (api_key) for write operations; public registry for reads.

Credential fields (optional for read-only use):
  - api_key: npm access token (required for publish/write operations)

Nodes:
  - npm_node.get_package          — fetch package metadata
  - npm_node.search_packages      — search the npm registry
  - npm_node.get_package_versions — list all published versions
  - npm_node.get_download_stats   — fetch download counts
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://registry.npmjs.org"
_SEARCH_URL = "https://registry.npmjs.org/-/v1/search"
_DOWNLOADS_URL = "https://api.npmjs.org/downloads"


async def _headers(credential_id: str, db) -> dict:
    """Build auth headers; Bearer token is optional for read ops."""
    if not credential_id:
        return {}
    try:
        creds = await get_credential_data(credential_id, db)
        api_key = creds.get("api_key")
        if api_key:
            return {"Authorization": f"Bearer {api_key}"}
    except Exception:
        pass
    return {}


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"npm API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


@register_node("npm_node.get_package")
async def get_package(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /{package} — fetch full package metadata.

    Config:
      package — (required) package name (e.g. express or @scope/pkg)
      version — (optional) specific version to fetch
    """
    package = config.get("package") or input_data.get("package")
    if not package:
        raise ValueError("npm_node.get_package requires 'package'")
    version = config.get("version") or input_data.get("version")
    path = f"/{package}/{version}" if version else f"/{package}"

    log.info("npm_node.get_package", package=package, version=version)
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=30.0) as client:
        r = await client.get(path)
    return _check(r)


@register_node("npm_node.search_packages")
async def search_packages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /-/v1/search — search the npm public registry.

    Config:
      query    — (required) search text
      size     — number of results (default: 20, max: 250)
      from_    — offset (pagination)
      quality  — quality weight [0-1]
      popularity — popularity weight [0-1]
      maintenance — maintenance weight [0-1]
    """
    query = config.get("query") or input_data.get("query") or config.get("q") or input_data.get("q")
    if not query:
        raise ValueError("npm_node.search_packages requires 'query'")

    params: dict = {"text": query}
    for field, key in (("size", "size"), ("from_", "from"), ("quality", "quality"),
                       ("popularity", "popularity"), ("maintenance", "maintenance")):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            params[key] = val

    log.info("npm_node.search_packages", query=query)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(_SEARCH_URL, params=params)
    return _check(r)


@register_node("npm_node.get_package_versions")
async def get_package_versions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /{package} — return the 'versions' map listing all published versions.

    Config:
      package — (required) package name
    """
    package = config.get("package") or input_data.get("package")
    if not package:
        raise ValueError("npm_node.get_package_versions requires 'package'")

    log.info("npm_node.get_package_versions", package=package)
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=30.0) as client:
        r = await client.get(f"/{package}")
    data = _check(r)
    return {
        "name": data.get("name"),
        "dist-tags": data.get("dist-tags", {}),
        "versions": list((data.get("versions") or {}).keys()),
    }


@register_node("npm_node.get_download_stats")
async def get_download_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET https://api.npmjs.org/downloads/point/{period}/{package} — download counts.

    Config:
      package — (required) package name
      period  — last-day | last-week | last-month | YYYY-MM-DD:YYYY-MM-DD (default: last-week)
      bulk    — bool, fetch range instead of point (default: false)
    """
    package = config.get("package") or input_data.get("package")
    if not package:
        raise ValueError("npm_node.get_download_stats requires 'package'")
    period = config.get("period") or input_data.get("period") or "last-week"
    bulk = config.get("bulk") or input_data.get("bulk") or False
    endpoint_type = "range" if bulk else "point"

    log.info("npm_node.get_download_stats", package=package, period=period)
    url = f"{_DOWNLOADS_URL}/{endpoint_type}/{period}/{package}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
    return _check(r)


async def test_connection(creds: dict) -> None:
    """Verify npm token (if provided) by fetching the npm CLI package."""
    api_key = creds.get("api_key")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=15.0) as client:
        r = await client.get("/npm")
    if not r.is_success:
        raise ValueError(f"npm connection failed: {r.status_code}")
