"""Stable Diffusion WebUI integration — local image generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return config.get("base_url", "http://127.0.0.1:7860").rstrip("/")


@register_node("stable_diffusion_webui.txt2img")
async def sd_txt2img(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{_base(merged)}/sdapi/v1/txt2img", json={
            "prompt": merged.get("prompt", ""),
            "negative_prompt": merged.get("negative_prompt", ""),
            "steps": merged.get("steps", 20),
            "width": merged.get("width", 512),
            "height": merged.get("height", 512),
            "cfg_scale": merged.get("cfg_scale", 7),
            "sampler_name": merged.get("sampler", "DPM++ 2M Karras"),
        })
        r.raise_for_status()
    data = r.json()
    return {"images": data.get("images", []), "info": data.get("info", "")}


@register_node("stable_diffusion_webui.img2img")
async def sd_img2img(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{_base(merged)}/sdapi/v1/img2img", json={
            "prompt": merged.get("prompt", ""),
            "init_images": [merged.get("init_image", "")],
            "denoising_strength": merged.get("denoising_strength", 0.75),
            "steps": merged.get("steps", 20),
        })
        r.raise_for_status()
    data = r.json()
    return {"images": data.get("images", []), "info": data.get("info", "")}


@register_node("stable_diffusion_webui.get_models")
async def sd_get_models(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{_base(merged)}/sdapi/v1/sd-models")
        r.raise_for_status()
    return {"models": r.json()}
