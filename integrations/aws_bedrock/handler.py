"""AWS Bedrock (Activepieces variant) — handler for aws_bedrock integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL_TEMPLATE = "https://bedrock-runtime.{region}.amazonaws.com"


def _build_base_url(merged: dict) -> str:
    region = merged.get("region") or "us-east-1"
    return BASE_URL_TEMPLATE.format(region=region)


def _build_headers(merged: dict) -> dict:
    api_key = merged.get("access_key_id") or merged.get("api_key") or ""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


@register_node("aws_bedrock.invoke_model")
async def aws_bedrock_invoke_model(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Invoke a foundation model.

    config/input_data:
      access_key_id / api_key — (required)
      region — AWS region (default us-east-1)
      model_id — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    model_id = merged.get("model_id") or ""
    body = merged.get("body") or ""
    if not model_id or not body:
        raise ValueError("model_id, body required for aws_bedrock.invoke_model")
    payload = {"body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/model/{model_id}/invoke", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("aws_bedrock.invoke_model")
    return {"data": data}

@register_node("aws_bedrock.list_models")
async def aws_bedrock_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available models.

    config/input_data:
      access_key_id / api_key — (required)
      region — AWS region (default us-east-1)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/foundation-models", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("aws_bedrock.list_models")
    return {"data": data}
