"""Placid integration — dynamic image and PDF generation from templates."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PLACID_BASE = "https://api.placid.app/api/rest"


def _placid_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("placid.create_image")
async def placid_create_image(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Generate an image from a Placid template.

    config:
      api_key     — Placid API key (required)
      template_id — UUID of the template to use (required)
      layers      — dict of layer name to content values (required)
      webhook_url — URL for async callback when image is ready (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    template_id = merged.get("template_id")
    layers = merged.get("layers", {})

    if not template_id:
        raise ValueError("template_id is required for placid.create_image")
    if not layers:
        raise ValueError("layers dict is required for placid.create_image")

    payload: dict = {
        "template_uuid": template_id,
        "layers": layers,
    }
    if merged.get("webhook_url"):
        payload["webhook_success_url"] = merged["webhook_url"]

    async with httpx.AsyncClient(base_url=PLACID_BASE, timeout=120) as client:
        r = await client.post(
            "/images", headers=_placid_headers(api_key), json=payload
        )
        r.raise_for_status()
        data = r.json()

    image_url = data.get("image_url")
    log.info(
        "placid.create_image",
        template_id=template_id,
        image_id=data.get("id"),
        status=data.get("status"),
    )
    return {"image": data, "image_url": image_url, "image_id": data.get("id")}


@register_node("placid.create_pdf")
async def placid_create_pdf(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Generate a PDF from a Placid template.

    config:
      api_key     — Placid API key (required)
      template_id — UUID of the template to use (required)
      layers      — dict of layer name to content values (required)
      webhook_url — URL for async callback when PDF is ready (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    template_id = merged.get("template_id")
    layers = merged.get("layers", {})

    if not template_id:
        raise ValueError("template_id is required for placid.create_pdf")
    if not layers:
        raise ValueError("layers dict is required for placid.create_pdf")

    payload: dict = {
        "template_uuid": template_id,
        "layers": layers,
    }
    if merged.get("webhook_url"):
        payload["webhook_success_url"] = merged["webhook_url"]

    async with httpx.AsyncClient(base_url=PLACID_BASE, timeout=120) as client:
        r = await client.post(
            "/pdfs", headers=_placid_headers(api_key), json=payload
        )
        r.raise_for_status()
        data = r.json()

    pdf_url = data.get("pdf_url")
    log.info(
        "placid.create_pdf",
        template_id=template_id,
        pdf_id=data.get("id"),
        status=data.get("status"),
    )
    return {"pdf": data, "pdf_url": pdf_url, "pdf_id": data.get("id")}


@register_node("placid.list_templates")
async def placid_list_templates(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all Placid templates in the account.

    config:
      api_key  — Placid API key (required)
      page     — page number for pagination (optional)
      tags     — filter by template tags (optional, list of strings)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params: dict = {}
    if merged.get("page"):
        params["page"] = merged["page"]
    if merged.get("tags"):
        params["tags"] = ",".join(merged["tags"])

    async with httpx.AsyncClient(base_url=PLACID_BASE, timeout=30) as client:
        r = await client.get(
            "/templates", headers=_placid_headers(api_key), params=params
        )
        r.raise_for_status()
        data = r.json()

    templates = data.get("data", data) if isinstance(data, dict) else data
    count = len(templates) if isinstance(templates, list) else 0
    log.info("placid.list_templates", count=count)
    return {"templates": templates, "count": count}


@register_node("placid.get_image")
async def placid_get_image(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get the status and URL of a generated Placid image.

    config:
      api_key  — Placid API key (required)
      image_id — ID of the generated image (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    image_id = merged.get("image_id")
    if not image_id:
        raise ValueError("image_id is required for placid.get_image")

    async with httpx.AsyncClient(base_url=PLACID_BASE, timeout=30) as client:
        r = await client.get(
            f"/images/{image_id}", headers=_placid_headers(api_key)
        )
        r.raise_for_status()
        data = r.json()

    log.info(
        "placid.get_image",
        image_id=image_id,
        status=data.get("status"),
        image_url=data.get("image_url"),
    )
    return {"image": data, "image_id": image_id, "image_url": data.get("image_url")}
