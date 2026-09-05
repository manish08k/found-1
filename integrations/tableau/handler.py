"""Tableau analytics integration — workbooks, datasources, views, and authentication."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(config: dict) -> str:
    server = config.get("server", "")
    if not server:
        raise ValueError("server is required in config")
    api_version = config.get("api_version", "3.19")
    return f"https://{server}/api/{api_version}"


async def _get_auth_token(config: dict) -> tuple[str, str]:
    """Sign in to Tableau and return (token, site_id)."""
    base = _base_url(config)
    username = config.get("username", "")
    password = config.get("password", "")
    site_content_url = config.get("site_id", "")

    if not username or not password:
        raise ValueError("username and password are required")

    payload = {
        "credentials": {
            "name": username,
            "password": password,
            "site": {"contentUrl": site_content_url},
        }
    }

    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post("/auth/signin", json=payload)
        r.raise_for_status()
        data = r.json()

    credentials = data.get("credentials", {})
    token = credentials.get("token", "")
    site_id = credentials.get("site", {}).get("id", "")
    return token, site_id


@register_node("tableau.list_workbooks")
async def tableau_list_workbooks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all workbooks in a Tableau site.

    config:
      server      — Tableau server hostname (required)
      api_version — API version (default '3.19')
      username    — Tableau username (required)
      password    — Tableau password (required)
      site_id     — site contentUrl (default '' for default site)
    """
    base = _base_url(config)
    token, site_id = await _get_auth_token(config)
    headers = {"X-Tableau-Auth": token}

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get(f"/sites/{site_id}/workbooks")
        r.raise_for_status()
        data = r.json()

    workbooks = data.get("workbooks", {}).get("workbook", [])
    log.info("tableau.list_workbooks", site_id=site_id, count=len(workbooks))
    return {"workbooks": workbooks, "count": len(workbooks), "site_id": site_id}


@register_node("tableau.list_datasources")
async def tableau_list_datasources(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all data sources in a Tableau site.

    config:
      server      — Tableau server hostname (required)
      api_version — API version (default '3.19')
      username    — Tableau username (required)
      password    — Tableau password (required)
      site_id     — site contentUrl (default '' for default site)
    """
    base = _base_url(config)
    token, site_id = await _get_auth_token(config)
    headers = {"X-Tableau-Auth": token}

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get(f"/sites/{site_id}/datasources")
        r.raise_for_status()
        data = r.json()

    datasources = data.get("datasources", {}).get("datasource", [])
    log.info("tableau.list_datasources", site_id=site_id, count=len(datasources))
    return {"datasources": datasources, "count": len(datasources), "site_id": site_id}


@register_node("tableau.list_views")
async def tableau_list_views(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all views in a Tableau site.

    config:
      server      — Tableau server hostname (required)
      api_version — API version (default '3.19')
      username    — Tableau username (required)
      password    — Tableau password (required)
      site_id     — site contentUrl (default '' for default site)
    """
    base = _base_url(config)
    token, site_id = await _get_auth_token(config)
    headers = {"X-Tableau-Auth": token}

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get(f"/sites/{site_id}/views")
        r.raise_for_status()
        data = r.json()

    views = data.get("views", {}).get("view", [])
    log.info("tableau.list_views", site_id=site_id, count=len(views))
    return {"views": views, "count": len(views), "site_id": site_id}


@register_node("tableau.get_workbook")
async def tableau_get_workbook(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Tableau workbook by ID.

    config/input_data:
      server      — Tableau server hostname (required)
      api_version — API version (default '3.19')
      username    — Tableau username (required)
      password    — Tableau password (required)
      site_id     — site contentUrl (default '' for default site)
      workbook_id — workbook ID (required)
    """
    base = _base_url(config)
    token, site_id = await _get_auth_token(config)
    headers = {"X-Tableau-Auth": token}
    workbook_id = config.get("workbook_id") or input_data.get("workbook_id")
    if not workbook_id:
        raise ValueError("workbook_id is required")

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get(f"/sites/{site_id}/workbooks/{workbook_id}")
        r.raise_for_status()
        data = r.json()

    workbook = data.get("workbook", {})
    log.info("tableau.get_workbook", workbook_id=workbook_id)
    return {"workbook": workbook, "workbook_id": workbook_id, "site_id": site_id}
