"""
ApiTemplate.io PDF and image generation integration.

Provides PDF creation, image generation, and template listing
via the ApiTemplate REST API v2.

Credential fields:
  - api_key : ApiTemplate.io API key

Auth: X-API-KEY header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://rest.apitemplate.io/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ApiTemplate credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "X-API-KEY": api_key,
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
        raise ValueError(f"ApiTemplate API error {r.status_code}: {detail}")


@register_node("apitemplate.create_pdf")
async def apt_create_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate a PDF from an ApiTemplate template by merging data."""
    template_id = config.get("template_id") or input_data.get("template_id")
    data = config.get("data") or input_data.get("data")

    if not template_id:
        raise ValueError("apitemplate.create_pdf requires 'template_id'")
    if not data:
        raise ValueError("apitemplate.create_pdf requires 'data' (dict of template variables)")

    # Optional rendering options
    expiration = int(config.get("expiration") or input_data.get("expiration", 5))  # minutes
    export_type = config.get("export_type") or input_data.get("export_type", "json")
    cloud_storage = int(config.get("cloud_storage") or input_data.get("cloud_storage", 1))
    output_file = config.get("output_file") or input_data.get("output_file")

    params: dict = {
        "template_id": template_id,
        "expiration": expiration,
        "export_type": export_type,
        "cloud_storage": cloud_storage,
    }
    if output_file:
        params["output_file"] = output_file

    payload: dict = {"data": data if isinstance(data, list) else [data]}

    async with await _client(credential_id, db) as client:
        r = await client.post("/create-pdf", params=params, json=payload)
        _raise_for_status(r)
        result = r.json()

    download_url = result.get("download_url", "")
    log.info("apitemplate.create_pdf", template_id=template_id, download_url=download_url)
    return {
        "download_url": download_url,
        "template_id": template_id,
        "response": result,
    }


@register_node("apitemplate.create_image")
async def apt_create_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate an image (PNG/JPEG) from an ApiTemplate template."""
    template_id = config.get("template_id") or input_data.get("template_id")
    data = config.get("data") or input_data.get("data")

    if not template_id:
        raise ValueError("apitemplate.create_image requires 'template_id'")
    if not data:
        raise ValueError("apitemplate.create_image requires 'data' (dict of template variables)")

    expiration = int(config.get("expiration") or input_data.get("expiration", 5))
    export_type = config.get("export_type") or input_data.get("export_type", "json")
    cloud_storage = int(config.get("cloud_storage") or input_data.get("cloud_storage", 1))
    image_quality = int(config.get("image_quality") or input_data.get("image_quality", 95))
    output_file = config.get("output_file") or input_data.get("output_file")

    params: dict = {
        "template_id": template_id,
        "expiration": expiration,
        "export_type": export_type,
        "cloud_storage": cloud_storage,
        "image_quality": image_quality,
    }
    if output_file:
        params["output_file"] = output_file

    payload: dict = {"data": data if isinstance(data, list) else [data]}

    async with await _client(credential_id, db) as client:
        r = await client.post("/create-image", params=params, json=payload)
        _raise_for_status(r)
        result = r.json()

    download_url = result.get("download_url", "")
    log.info("apitemplate.create_image", template_id=template_id, download_url=download_url)
    return {
        "download_url": download_url,
        "template_id": template_id,
        "response": result,
    }


@register_node("apitemplate.list_templates")
async def apt_list_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all PDF and image templates available in the ApiTemplate account."""
    template_type = config.get("template_type") or input_data.get("template_type")
    limit = int(config.get("limit") or input_data.get("limit", 100))

    params: dict = {"limit": limit}
    if template_type:
        # "pdf" or "image"
        params["template_type"] = template_type

    async with await _client(credential_id, db) as client:
        r = await client.get("/list-templates", params=params)
        _raise_for_status(r)
        data = r.json()

    templates = data.get("templates", data if isinstance(data, list) else [])
    return {
        "templates": templates,
        "count": len(templates),
    }


@register_node("apitemplate.get_template")
async def apt_get_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve details and variables for a specific ApiTemplate template."""
    template_id = config.get("template_id") or input_data.get("template_id")
    if not template_id:
        raise ValueError("apitemplate.get_template requires 'template_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get("/get-template", params={"template_id": template_id})
        _raise_for_status(r)
        data = r.json()

    return {"template": data, "template_id": template_id}


@register_node("apitemplate.delete_object")
async def apt_delete_object(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a generated PDF or image from cloud storage by transaction reference."""
    transaction_ref = config.get("transaction_ref") or input_data.get("transaction_ref")
    if not transaction_ref:
        raise ValueError("apitemplate.delete_object requires 'transaction_ref'")

    async with await _client(credential_id, db) as client:
        r = await client.delete("/delete-object", params={"transaction_ref": transaction_ref})
        _raise_for_status(r)
        result = r.json()

    log.info("apitemplate.delete_object", transaction_ref=transaction_ref)
    return {"deleted": True, "transaction_ref": transaction_ref, "response": result}
