"""Carbone integration — document generation from templates."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CARBONE_BASE = "https://api.carbone.io"


def _carbone_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}


@register_node("carbone.render_template")
async def carbone_render_template(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Render a document from a Carbone template with provided data.

    config:
      api_token   — Carbone API token (required)
      template_id — ID of the template to render (required)
      data        — dict of data to inject into the template (required)
      convert_to  — output format e.g. "pdf", "docx" (optional, default "pdf")
      lang        — locale for rendering e.g. "en-us" (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    template_id = merged.get("template_id")
    data = merged.get("data", {})

    if not template_id:
        raise ValueError("template_id is required for carbone.render_template")
    if not data:
        raise ValueError("data dict is required for carbone.render_template")

    payload: dict = {
        "data": data,
        "convertTo": merged.get("convert_to", "pdf"),
    }
    if merged.get("lang"):
        payload["lang"] = merged["lang"]

    async with httpx.AsyncClient(base_url=CARBONE_BASE, timeout=60) as client:
        r = await client.post(
            f"/render/{template_id}",
            headers=_carbone_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        response = r.json()

    render_id = response.get("data", {}).get("renderId")
    log.info("carbone.render_template", template_id=template_id, render_id=render_id)
    return {"render_id": render_id, "template_id": template_id, "response": response}


@register_node("carbone.get_render")
async def carbone_get_render(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Download a rendered document by render ID.

    config:
      api_token — Carbone API token (required)
      render_id — render ID returned by render_template (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    render_id = merged.get("render_id")
    if not render_id:
        raise ValueError("render_id is required for carbone.get_render")

    headers = {"Authorization": f"Bearer {api_token}"}

    async with httpx.AsyncClient(base_url=CARBONE_BASE, timeout=60) as client:
        r = await client.get(f"/render/{render_id}", headers=headers)
        r.raise_for_status()
        content = r.content

    content_type = r.headers.get("content-type", "application/octet-stream")
    content_disposition = r.headers.get("content-disposition", "")
    log.info("carbone.get_render", render_id=render_id, size=len(content))
    return {
        "render_id": render_id,
        "content_type": content_type,
        "content_disposition": content_disposition,
        "size": len(content),
        "content_base64": content.hex(),
    }


@register_node("carbone.add_template")
async def carbone_add_template(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Upload a new template to Carbone.

    config:
      api_token     — Carbone API token (required)
      template_data — base64-encoded template file content (required)
      payload       — optional payload for pre-computing template hash (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    template_data = merged.get("template_data")
    if not template_data:
        raise ValueError("template_data is required for carbone.add_template")

    import base64 as _b64
    file_bytes = _b64.b64decode(template_data)

    headers = {"Authorization": f"Bearer {api_token}"}

    async with httpx.AsyncClient(base_url=CARBONE_BASE, timeout=60) as client:
        r = await client.post(
            "/template",
            headers=headers,
            files={"template": ("template.docx", file_bytes, "application/octet-stream")},
        )
        r.raise_for_status()
        response = r.json()

    template_id = response.get("data", {}).get("templateId")
    log.info("carbone.add_template", template_id=template_id)
    return {"template_id": template_id, "response": response}


@register_node("carbone.delete_template")
async def carbone_delete_template(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Delete a template from Carbone by its template ID.

    config:
      api_token   — Carbone API token (required)
      template_id — ID of the template to delete (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    template_id = merged.get("template_id")
    if not template_id:
        raise ValueError("template_id is required for carbone.delete_template")

    async with httpx.AsyncClient(base_url=CARBONE_BASE, timeout=30) as client:
        r = await client.delete(
            f"/template/{template_id}",
            headers=_carbone_headers(api_token),
        )
        r.raise_for_status()

    log.info("carbone.delete_template", template_id=template_id)
    return {"success": True, "template_id": template_id}


@register_node("carbone.get_report")
async def carbone_get_report(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Render and immediately retrieve a Carbone report in one step.

    config:
      api_token   — Carbone API token (required)
      template_id — ID of the template to render (required)
      data        — dict of data to inject into the template (required)
      convert_to  — output format e.g. "pdf" (optional, default "pdf")
      lang        — locale for rendering (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    template_id = merged.get("template_id")
    data = merged.get("data", {})

    if not template_id or not data:
        raise ValueError("template_id and data are required for carbone.get_report")

    payload: dict = {
        "data": data,
        "convertTo": merged.get("convert_to", "pdf"),
    }
    if merged.get("lang"):
        payload["lang"] = merged["lang"]

    async with httpx.AsyncClient(base_url=CARBONE_BASE, timeout=120) as client:
        # Step 1: render
        r = await client.post(
            f"/render/{template_id}",
            headers=_carbone_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        render_resp = r.json()
        render_id = render_resp.get("data", {}).get("renderId")
        if not render_id:
            raise RuntimeError(f"No renderId in Carbone response: {render_resp}")

        # Step 2: download
        headers = {"Authorization": f"Bearer {api_token}"}
        r2 = await client.get(f"/render/{render_id}", headers=headers)
        r2.raise_for_status()
        content = r2.content

    log.info("carbone.get_report", template_id=template_id, render_id=render_id, size=len(content))
    return {
        "render_id": render_id,
        "template_id": template_id,
        "content_type": r2.headers.get("content-type", "application/pdf"),
        "size": len(content),
        "content_base64": content.hex(),
    }
