"""
Bannerbear image and video generation integration.

Provides template listing, image creation/retrieval, and video creation
via the Bannerbear REST API v2.

Credential fields:
  - api_key : Bannerbear project API key (found in Project Settings)

Auth: Bearer token via Authorization header.
Base URL: https://api.bannerbear.com/v2/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bannerbear.com/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Bannerbear credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Bannerbear API error {r.status_code}: {detail}")


@register_node("bannerbear.list_templates")
async def bb_list_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all available Bannerbear templates for the project."""
    page = int(config.get("page") or input_data.get("page", 1))
    limit = min(int(config.get("limit") or input_data.get("limit", 25)), 100)

    params: dict = {"page": page, "limit": limit}
    tag = config.get("tag") or input_data.get("tag")
    if tag:
        params["tag"] = tag

    async with await _client(credential_id, db) as client:
        r = await client.get("/templates", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("bannerbear.list_templates", count=len(data) if isinstance(data, list) else 0)
    return {"templates": data if isinstance(data, list) else data.get("templates", []), "page": page}


@register_node("bannerbear.get_template")
async def bb_get_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a single template by UID."""
    template_uid = config.get("template_uid") or input_data.get("template_uid")
    if not template_uid:
        raise ValueError("bannerbear.get_template requires 'template_uid'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/templates/{template_uid}")
        _raise_for_status(r)
        data = r.json()

    return {"template": data}


@register_node("bannerbear.create_image")
async def bb_create_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create (generate) an image from a Bannerbear template.

    Params:
      - template_uid (required): UID of the template to use.
      - modifications (list[dict]): Layer modifications, e.g.
          [{"name": "title", "text": "Hello"}, {"name": "bg", "color": "#ff0000"}]
      - webhook_url: URL to POST when image is ready (async generation).
      - transparent: bool — render with transparent background.
      - render_pdf: bool — also render a PDF version.
      - metadata: arbitrary string stored with the image.
    """
    template_uid = config.get("template_uid") or input_data.get("template_uid")
    if not template_uid:
        raise ValueError("bannerbear.create_image requires 'template_uid'")

    modifications = config.get("modifications") or input_data.get("modifications", [])
    if isinstance(modifications, str):
        import json
        modifications = json.loads(modifications)

    payload: dict = {
        "template": template_uid,
        "modifications": modifications,
    }

    webhook_url = config.get("webhook_url") or input_data.get("webhook_url")
    if webhook_url:
        payload["webhook_url"] = webhook_url

    if config.get("transparent") or input_data.get("transparent"):
        payload["transparent"] = True
    if config.get("render_pdf") or input_data.get("render_pdf"):
        payload["render_pdf"] = True

    metadata = config.get("metadata") or input_data.get("metadata")
    if metadata:
        payload["metadata"] = str(metadata)

    async with await _client(credential_id, db) as client:
        r = await client.post("/images", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bannerbear.create_image", uid=data.get("uid"), status=data.get("status"))
    return {"image": data, "uid": data.get("uid"), "status": data.get("status")}


@register_node("bannerbear.get_image")
async def bb_get_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a previously created image by UID.

    Params:
      - uid (required): UID of the image to retrieve.
    """
    uid = config.get("uid") or input_data.get("uid")
    if not uid:
        raise ValueError("bannerbear.get_image requires 'uid'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/images/{uid}")
        _raise_for_status(r)
        data = r.json()

    return {
        "image": data,
        "uid": data.get("uid"),
        "status": data.get("status"),
        "image_url": data.get("image_url"),
        "image_url_png": data.get("image_url_png"),
    }


@register_node("bannerbear.create_video")
async def bb_create_video(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a video from a Bannerbear video template.

    Params:
      - video_template_uid (required): UID of the video template.
      - modifications (list[dict]): Layer modifications.
      - input_media_url: URL of an input video/audio clip to use.
      - webhook_url: Callback URL for async completion.
      - metadata: arbitrary string metadata.
      - approve: bool — set to True to approve before rendering.
    """
    video_template_uid = config.get("video_template_uid") or input_data.get("video_template_uid")
    if not video_template_uid:
        raise ValueError("bannerbear.create_video requires 'video_template_uid'")

    modifications = config.get("modifications") or input_data.get("modifications", [])
    if isinstance(modifications, str):
        import json
        modifications = json.loads(modifications)

    payload: dict = {
        "video_template": video_template_uid,
        "modifications": modifications,
    }

    input_media_url = config.get("input_media_url") or input_data.get("input_media_url")
    if input_media_url:
        payload["input_media_url"] = input_media_url

    webhook_url = config.get("webhook_url") or input_data.get("webhook_url")
    if webhook_url:
        payload["webhook_url"] = webhook_url

    metadata = config.get("metadata") or input_data.get("metadata")
    if metadata:
        payload["metadata"] = str(metadata)

    if config.get("approve") or input_data.get("approve"):
        payload["approve"] = True

    async with await _client(credential_id, db) as client:
        r = await client.post("/videos", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bannerbear.create_video", uid=data.get("uid"), status=data.get("status"))
    return {"video": data, "uid": data.get("uid"), "status": data.get("status")}


@register_node("bannerbear.list_images")
async def bb_list_images(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List images generated for the project, optionally filtered by template UID."""
    page = int(config.get("page") or input_data.get("page", 1))
    template_uid = config.get("template_uid") or input_data.get("template_uid")

    params: dict = {"page": page}
    if template_uid:
        params["template"] = template_uid

    async with await _client(credential_id, db) as client:
        r = await client.get("/images", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"images": data if isinstance(data, list) else data.get("images", []), "page": page}
