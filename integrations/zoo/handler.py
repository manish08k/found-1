"""Zoo (KittyCAD) 3D design API — handler for zoo integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.zoo.dev"


@register_node("zoo.convert_file")
async def zoo_convert_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert a 3D file.

    config/input_data:
      api_key — API key or token (required)
      src_format — (required)
      output_format — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    src_format = merged.get("src_format") or ""
    output_format = merged.get("output_format") or ""
    if not src_format or not output_format:
        raise ValueError("src_format, output_format required for zoo.convert_file")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/file/conversion/{src_format}/{output_format}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoo.convert_file")
    return {"data": data}

@register_node("zoo.get_ai_prompt")
async def zoo_get_ai_prompt(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate 3D model from text.

    config/input_data:
      api_key — API key or token (required)
      output_format — (required)
      prompt — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    output_format = merged.get("output_format") or ""
    prompt = merged.get("prompt") or ""
    if not output_format or not prompt:
        raise ValueError("output_format, prompt required for zoo.get_ai_prompt")
    payload = {"prompt": prompt}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/ai/text-to-cad/{output_format}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoo.get_ai_prompt")
    return {"data": data}
