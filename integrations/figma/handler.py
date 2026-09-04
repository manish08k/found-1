"""
Figma API integration.

Credential fields:
  - access_token: Figma personal access token or OAuth2 token (X-Figma-Token header)

Auth: X-Figma-Token header
Base URL: https://api.figma.com/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

FIGMA_BASE_URL = "https://api.figma.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token") or creds.get("api_key")
    if not access_token:
        raise ValueError("Figma credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=FIGMA_BASE_URL,
        headers={
            "X-Figma-Token": access_token,
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Figma API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("figma.get_file")
async def figma_get_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /files/{file_key} — get the document structure of a Figma file."""
    file_key = config.get("file_key") or input_data.get("file_key")
    if not file_key:
        raise ValueError("figma.get_file requires 'file_key'")
    params: dict = {}
    depth = config.get("depth") or input_data.get("depth")
    if depth:
        params["depth"] = int(depth)
    geometry = config.get("geometry") or input_data.get("geometry")
    if geometry:
        params["geometry"] = geometry
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/files/{file_key}", params=params)
    return _check(r)


@register_node("figma.get_file_nodes")
async def figma_get_file_nodes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /files/{file_key}/nodes — get specific nodes from a Figma file."""
    file_key = config.get("file_key") or input_data.get("file_key")
    node_ids = config.get("node_ids") or input_data.get("node_ids")
    if not file_key:
        raise ValueError("figma.get_file_nodes requires 'file_key'")
    if not node_ids:
        raise ValueError("figma.get_file_nodes requires 'node_ids'")
    ids_str = ",".join(node_ids) if isinstance(node_ids, list) else node_ids
    params: dict = {"ids": ids_str}
    depth = config.get("depth") or input_data.get("depth")
    if depth:
        params["depth"] = int(depth)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/files/{file_key}/nodes", params=params)
    return _check(r)


@register_node("figma.list_projects")
async def figma_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams/{team_id}/projects — list projects for a team."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("figma.list_projects requires 'team_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/projects")
    return _check(r)


@register_node("figma.list_team_projects")
async def figma_list_team_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams/{team_id}/projects — list all projects for a team (alias)."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("figma.list_team_projects requires 'team_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/projects")
    return _check(r)


@register_node("figma.list_files")
async def figma_list_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /projects/{project_id}/files — list files in a project."""
    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("figma.list_files requires 'project_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/projects/{project_id}/files")
    return _check(r)


@register_node("figma.get_team_styles")
async def figma_get_team_styles(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams/{team_id}/styles — list styles for a team."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("figma.get_team_styles requires 'team_id'")
    params: dict = {}
    page_size = config.get("page_size") or input_data.get("page_size")
    if page_size:
        params["page_size"] = min(int(page_size), 100)
    after = config.get("after") or input_data.get("after")
    if after:
        params["after"] = after
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/styles", params=params)
    return _check(r)


@register_node("figma.get_team_components")
async def figma_get_team_components(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams/{team_id}/components — list components for a team."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("figma.get_team_components requires 'team_id'")
    params: dict = {}
    page_size = config.get("page_size") or input_data.get("page_size")
    if page_size:
        params["page_size"] = min(int(page_size), 100)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/components", params=params)
    return _check(r)


@register_node("figma.get_comments")
async def figma_get_comments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /files/{file_key}/comments — get all comments on a file."""
    file_key = config.get("file_key") or input_data.get("file_key")
    if not file_key:
        raise ValueError("figma.get_comments requires 'file_key'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/files/{file_key}/comments")
    return _check(r)


@register_node("figma.post_comment")
async def figma_post_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /files/{file_key}/comments — post a comment on a file."""
    file_key = config.get("file_key") or input_data.get("file_key")
    message = config.get("message") or input_data.get("message")
    if not file_key:
        raise ValueError("figma.post_comment requires 'file_key'")
    if not message:
        raise ValueError("figma.post_comment requires 'message'")
    body: dict = {"message": message}
    client_meta = config.get("client_meta") or input_data.get("client_meta")
    if client_meta:
        body["client_meta"] = client_meta
    comment_id = config.get("comment_id") or input_data.get("comment_id")
    if comment_id:
        body["comment_id"] = comment_id
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/files/{file_key}/comments", json=body)
    return _check(r)


@register_node("figma.get_versions")
async def figma_get_versions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /files/{file_key}/versions — get version history of a file."""
    file_key = config.get("file_key") or input_data.get("file_key")
    if not file_key:
        raise ValueError("figma.get_versions requires 'file_key'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/files/{file_key}/versions")
    return _check(r)


@register_node("figma.export_images")
async def figma_export_images(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /images/{file_key} — export node(s) as images."""
    file_key = config.get("file_key") or input_data.get("file_key")
    node_ids = config.get("node_ids") or input_data.get("node_ids")
    if not file_key:
        raise ValueError("figma.export_images requires 'file_key'")
    if not node_ids:
        raise ValueError("figma.export_images requires 'node_ids'")
    ids_str = ",".join(node_ids) if isinstance(node_ids, list) else node_ids
    params: dict = {"ids": ids_str}
    format_ = config.get("format") or input_data.get("format", "png")
    params["format"] = format_
    scale = config.get("scale") or input_data.get("scale")
    if scale:
        params["scale"] = float(scale)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/images/{file_key}", params=params)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test Figma connection by fetching the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    _check(r)
    return {"ok": True}
