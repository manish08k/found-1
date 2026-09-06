"""PhotoRoom integration — AI background removal and image editing."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PHOTOROOM_BASE = "https://sdk.photoroom.com/v1"


def _photoroom_headers(api_key: str) -> dict:
    return {"x-api-key": api_key}


@register_node("photoroom.remove_background")
async def photoroom_remove_background(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Remove the background from an image using PhotoRoom.

    config:
      api_key      — PhotoRoom API key (required)
      image_url    — URL of the image to process (use this OR image_base64)
      image_base64 — base64-encoded image bytes (use this OR image_url)
      format       — output format: png/jpg (optional, default png)
      bg_color     — background color hex e.g. "#FFFFFF" (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for photoroom.remove_background")

    image_url = merged.get("image_url")
    image_base64 = merged.get("image_base64")
    if not image_url and not image_base64:
        raise ValueError("Either image_url or image_base64 is required")

    output_format = merged.get("format", "png")

    if image_url:
        async with httpx.AsyncClient(timeout=30) as dl_client:
            img_response = await dl_client.get(image_url)
            img_response.raise_for_status()
            image_bytes = img_response.content
    else:
        image_bytes = base64.b64decode(image_base64)

    files = {"image_file": ("image.png", image_bytes, "image/png")}
    data: dict = {"format": output_format}
    if merged.get("bg_color"):
        data["bg_color"] = merged["bg_color"]

    async with httpx.AsyncClient(base_url=PHOTOROOM_BASE, timeout=60) as client:
        r = await client.post(
            "/segment",
            headers=_photoroom_headers(api_key),
            files=files,
            data=data,
        )
        r.raise_for_status()
        result_bytes = r.content

    result_b64 = base64.b64encode(result_bytes).decode()
    log.info("photoroom.remove_background", format=output_format, result_size=len(result_bytes))
    return {
        "image_base64": result_b64,
        "format": output_format,
        "size_bytes": len(result_bytes),
    }


@register_node("photoroom.get_result")
async def photoroom_get_result(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch a previously processed PhotoRoom result by job ID (if async API).

    config:
      api_key — PhotoRoom API key (required)
      job_id  — async job ID returned from a previous request (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    job_id = merged.get("job_id")
    if not api_key or not job_id:
        raise ValueError("api_key and job_id are required for photoroom.get_result")

    async with httpx.AsyncClient(base_url=PHOTOROOM_BASE, timeout=30) as client:
        r = await client.get(f"/jobs/{job_id}", headers=_photoroom_headers(api_key))
        r.raise_for_status()
        data = r.json()

    status = data.get("status")
    log.info("photoroom.get_result", job_id=job_id, status=status)
    return {"result": data, "job_id": job_id, "status": status}
