"""Amazon Bedrock integration for invoking foundation models."""
import base64
import json
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _get_client(creds: dict, service: str):
    if not HAS_BOTO3:
        raise ImportError("boto3 is required for Amazon Bedrock. Install it with: pip install boto3")
    return boto3.client(
        service,
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        region_name=creds.get("region_name", "us-east-1"),
    )


@register_node("amazon_bedrock.invoke_model")
async def amazon_bedrock_invoke_model(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Invoke a Bedrock foundation model synchronously."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    model_id = merged.get("model_id", "anthropic.claude-3-haiku-20240307-v1:0")
    prompt = merged.get("prompt", "")
    max_tokens = int(merged.get("max_tokens", 1024))

    # Build provider-specific body
    if "anthropic" in model_id:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    elif "amazon.titan" in model_id:
        body = {
            "inputText": prompt,
            "textGenerationConfig": {"maxTokenCount": max_tokens},
        }
    elif "meta.llama" in model_id:
        body = {"prompt": prompt, "max_gen_len": max_tokens}
    elif "mistral" in model_id:
        body = {"prompt": prompt, "max_tokens": max_tokens}
    elif "cohere" in model_id:
        body = {"prompt": prompt, "max_tokens": max_tokens}
    else:
        body = merged.get("body", {"prompt": prompt, "max_tokens": max_tokens})

    def _invoke():
        client = _get_client(creds, "bedrock-runtime")
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result_body = json.loads(response["body"].read())
        return {
            "model_id": model_id,
            "response": result_body,
            "usage": response.get("ResponseMetadata", {}),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _invoke)


@register_node("amazon_bedrock.invoke_model_streaming")
async def amazon_bedrock_invoke_model_streaming(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Invoke a Bedrock model with streaming response (returns aggregated text)."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    model_id = merged.get("model_id", "anthropic.claude-3-haiku-20240307-v1:0")
    prompt = merged.get("prompt", "")
    max_tokens = int(merged.get("max_tokens", 1024))

    if "anthropic" in model_id:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        body = merged.get("body", {"prompt": prompt, "max_tokens": max_tokens})

    def _invoke_streaming():
        client = _get_client(creds, "bedrock-runtime")
        response = client.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        chunks = []
        for event in response["body"]:
            chunk = event.get("chunk")
            if chunk:
                data = json.loads(chunk["bytes"])
                # Anthropic streaming format
                if data.get("type") == "content_block_delta":
                    chunks.append(data.get("delta", {}).get("text", ""))
                elif "outputText" in data:
                    chunks.append(data["outputText"])
        return {"model_id": model_id, "text": "".join(chunks), "chunks_received": len(chunks)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _invoke_streaming)


@register_node("amazon_bedrock.list_models")
async def amazon_bedrock_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available Bedrock foundation models."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    by_provider = merged.get("by_provider")

    def _list():
        client = _get_client(creds, "bedrock")
        kwargs = {}
        if by_provider:
            kwargs["byProvider"] = by_provider
        response = client.list_foundation_models(**kwargs)
        models = response.get("modelSummaries", [])
        return {"models": models, "count": len(models)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list)
