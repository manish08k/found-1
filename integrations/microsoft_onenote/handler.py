"""Microsoft OneNote integration — notebooks, sections, and pages via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("onenote.list_notebooks")
async def onenote_list_notebooks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List OneNote notebooks for the authenticated user.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of notebooks to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/me/onenote/notebooks", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    notebooks = data.get("value", [])
    log.info("onenote.list_notebooks", count=len(notebooks))
    return {"notebooks": notebooks, "count": len(notebooks)}


@register_node("onenote.create_page")
async def onenote_create_page(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new page in a OneNote section.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      section_id   — ID of the section to create the page in (required)
      title        — page title (required)
      html_content — HTML body content for the page (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    section_id = merged.get("section_id")
    title = merged.get("title", "New Page")
    if not section_id:
        raise ValueError("section_id is required for onenote.create_page")

    html_content = merged.get("html_content", "")
    html_body = f"""<!DOCTYPE html>
<html>
  <head>
    <title>{title}</title>
  </head>
  <body>
    {html_content}
  </body>
</html>"""

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/html",
    }

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(
            f"/me/onenote/sections/{section_id}/pages",
            headers=headers,
            content=html_body.encode("utf-8"),
        )
        r.raise_for_status()
        page = r.json()

    log.info("onenote.create_page", section_id=section_id, page_id=page.get("id"))
    return {"page": page, "page_id": page.get("id")}


@register_node("onenote.get_page")
async def onenote_get_page(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific OneNote page by ID.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      page_id      — OneNote page ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    page_id = merged.get("page_id")
    if not page_id:
        raise ValueError("page_id is required for onenote.get_page")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/me/onenote/pages/{page_id}", headers=_graph_headers(access_token))
        r.raise_for_status()
        page = r.json()

    log.info("onenote.get_page", page_id=page_id)
    return {"page": page, "page_id": page_id}


@register_node("onenote.list_pages")
async def onenote_list_pages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List pages in a OneNote section.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      section_id   — section ID to list pages from (required)
      top          — maximum number of pages to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    section_id = merged.get("section_id")
    if not section_id:
        raise ValueError("section_id is required for onenote.list_pages")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/onenote/sections/{section_id}/pages",
            headers=_graph_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    pages = data.get("value", [])
    log.info("onenote.list_pages", section_id=section_id, count=len(pages))
    return {"pages": pages, "count": len(pages)}


@register_node("onenote.list_sections")
async def onenote_list_sections(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List sections in a OneNote notebook.

    config/input_data:
      access_token  — Microsoft Graph OAuth2 bearer token (required)
      notebook_id   — notebook ID to list sections from (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    notebook_id = merged.get("notebook_id")
    if not notebook_id:
        raise ValueError("notebook_id is required for onenote.list_sections")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/onenote/notebooks/{notebook_id}/sections",
            headers=_graph_headers(access_token),
        )
        r.raise_for_status()
        data = r.json()

    sections = data.get("value", [])
    log.info("onenote.list_sections", notebook_id=notebook_id, count=len(sections))
    return {"sections": sections, "count": len(sections)}
