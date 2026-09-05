"""Azure OpenAI integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

AZURE_API_VERSION = "2024-02-01"


def _azure_base_url(resource_name: str, deployment_name: str) -> str:
    return (
        f"https://{resource_name}.openai.azure.com/openai/deployments/{deployment_name}"
    )


@register_node("azure_openai.chat")
async def azure_openai_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a chat completion using Azure OpenAI.

    config/input_data:
      api_key         — Azure OpenAI API key
      resource_name   — Azure resource name (subdomain)
      deployment_name — model deployment name
      messages        — list of {"role": ..., "content": ...} dicts
      temperature     — sampling temperature (default 0.7)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    resource_name = merged.get("resource_name") or ""
    deployment_name = merged.get("deployment_name") or ""
    messages = merged.get("messages") or []
    temperature = float(merged.get("temperature", 0.7))

    base_url = _azure_base_url(resource_name, deployment_name)
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {"messages": messages, "temperature": temperature}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            params={"api-version": AZURE_API_VERSION},
        )
        r.raise_for_status()

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    log.info("azure_openai.chat", resource=resource_name, deployment=deployment_name)
    return {"result": data, "content": content}


@register_node("azure_openai.embeddings")
async def azure_openai_embeddings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate embeddings using Azure OpenAI.

    config/input_data:
      api_key         — Azure OpenAI API key
      resource_name   — Azure resource name (subdomain)
      deployment_name — embedding model deployment name
      input           — string or list of strings to embed
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    resource_name = merged.get("resource_name") or ""
    deployment_name = merged.get("deployment_name") or ""
    input_text = merged.get("input") or ""

    base_url = _azure_base_url(resource_name, deployment_name)
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {"input": input_text}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{base_url}/embeddings",
            headers=headers,
            json=payload,
            params={"api-version": AZURE_API_VERSION},
        )
        r.raise_for_status()

    data = r.json()
    log.info("azure_openai.embeddings", resource=resource_name, deployment=deployment_name)
    return {"result": data}
