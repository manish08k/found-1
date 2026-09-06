"""GenerateBanners integration — programmatic banner and image creation."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GENERATEBANNERS_BASE = "https://api.generatebanners.com/v1"


def _generatebanners_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("generatebanners.create_banner")
async def generatebanners_create_banner(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new banner image using a GenerateBanners template.

    config:
      api_key     — GenerateBanners API key (required)
      template_id — template ID to use for banner generation (required)
      modifications — dict of template field modifications (optional)
      width       — banner width in pixels (optional)
      height      — banner height in pixels (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    template_id = merged.get("template_id")
    if not template_id:
        raise ValueError("template_id is required for generatebanners.create_banner")

    payload: dict = {"template_id": template_id}
    if merged.get("modifications"):
        payload["modifications"] = merged["modifications"]
    if merged.get("width") is not None:
        payload["width"] = merged["width"]
    if merged.get("height") is not None:
        payload["height"] = merged["height"]

    async with httpx.AsyncClient(base_url=GENERATEBANNERS_BASE, timeout=60) as client:
        r = await client.post(
            "/banners",
            headers=_generatebanners_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        banner = r.json()

    banner_id = banner.get("id") if isinstance(banner, dict) else None
    banner_url = banner.get("url") if isinstance(banner, dict) else None
    log.info("generatebanners.create_banner", template_id=template_id, banner_id=banner_id)
    return {"banner": banner, "banner_id": banner_id, "url": banner_url}


@register_node("generatebanners.get_banner")
async def generatebanners_get_banner(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details and status of a previously created banner.

    config:
      api_key   — GenerateBanners API key (required)
      banner_id — banner ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    banner_id = merged.get("banner_id")
    if not banner_id:
        raise ValueError("banner_id is required for generatebanners.get_banner")

    async with httpx.AsyncClient(base_url=GENERATEBANNERS_BASE, timeout=30) as client:
        r = await client.get(
            f"/banners/{banner_id}",
            headers=_generatebanners_headers(api_key),
        )
        r.raise_for_status()
        banner = r.json()

    banner_url = banner.get("url") if isinstance(banner, dict) else None
    status = banner.get("status") if isinstance(banner, dict) else None
    log.info("generatebanners.get_banner", banner_id=banner_id, status=status)
    return {"banner": banner, "banner_id": banner_id, "url": banner_url, "status": status}
