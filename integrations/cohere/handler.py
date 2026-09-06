"""Cohere AI integration for text generation, embedding, classification, and more."""
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.cohere.ai/v1"


def _get_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("cohere.generate_text")
async def cohere_generate_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate text using Cohere's generation models."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("cohere requires 'api_key'")
    prompt = merged.get("prompt", "")
    if not prompt:
        raise ValueError("generate_text requires 'prompt'")

    payload = {
        "prompt": prompt,
        "model": merged.get("model", "command"),
        "max_tokens": int(merged.get("max_tokens", 1024)),
        "temperature": float(merged.get("temperature", 0.75)),
    }
    for key in ["k", "p", "stop_sequences", "return_likelihoods", "num_generations"]:
        if merged.get(key) is not None:
            payload[key] = merged[key]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{BASE_URL}/generate", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()
        generations = data.get("generations", [])
        return {"text": generations[0].get("text", "") if generations else "", "generations": generations, "meta": data.get("meta")}


@register_node("cohere.embed_text")
async def cohere_embed_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate embeddings for text using Cohere's embedding models."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    texts = merged.get("texts") or merged.get("text")
    if not texts:
        raise ValueError("embed_text requires 'texts' (list) or 'text' (string)")
    if isinstance(texts, str):
        texts = [texts]

    payload = {
        "texts": texts,
        "model": merged.get("model", "embed-english-v3.0"),
        "input_type": merged.get("input_type", "search_document"),
    }
    truncate = merged.get("truncate")
    if truncate:
        payload["truncate"] = truncate

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{BASE_URL}/embed", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()
        return {"embeddings": data.get("embeddings", []), "meta": data.get("meta"), "texts_count": len(texts)}


@register_node("cohere.classify")
async def cohere_classify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Classify text into categories using Cohere."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    inputs = merged.get("inputs", [])
    examples = merged.get("examples", [])
    if not inputs:
        raise ValueError("classify requires 'inputs' list")

    payload = {
        "inputs": inputs,
        "examples": examples,
        "model": merged.get("model", "embed-english-v2.0"),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{BASE_URL}/classify", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()
        return {"classifications": data.get("classifications", []), "meta": data.get("meta")}


@register_node("cohere.summarize")
async def cohere_summarize(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Summarize a document using Cohere's summarization."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    text = merged.get("text")
    if not text:
        raise ValueError("summarize requires 'text'")

    payload = {
        "text": text,
        "model": merged.get("model", "command"),
        "length": merged.get("length", "medium"),  # short, medium, long
        "format": merged.get("format", "paragraph"),  # paragraph, bullets
        "extractiveness": merged.get("extractiveness", "auto"),
    }
    extra_info = merged.get("additional_command")
    if extra_info:
        payload["additional_command"] = extra_info

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{BASE_URL}/summarize", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()
        return {"summary": data.get("summary", ""), "meta": data.get("meta")}


@register_node("cohere.chat")
async def cohere_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Chat with a Cohere model using multi-turn conversation."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    message = merged.get("message") or merged.get("prompt")
    if not message:
        raise ValueError("chat requires 'message'")

    payload = {
        "message": message,
        "model": merged.get("model", "command-r-plus"),
        "temperature": float(merged.get("temperature", 0.3)),
    }
    for key in ["chat_history", "preamble", "documents", "tools", "max_tokens"]:
        if merged.get(key) is not None:
            payload[key] = merged[key]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{BASE_URL}/chat", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()
        return {
            "text": data.get("text", ""),
            "generation_id": data.get("generation_id"),
            "finish_reason": data.get("finish_reason"),
            "chat_history": data.get("chat_history", []),
            "meta": data.get("meta"),
        }


@register_node("cohere.rerank")
async def cohere_rerank(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Rerank documents based on relevance to a query."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    query = merged.get("query")
    documents = merged.get("documents", [])
    if not query or not documents:
        raise ValueError("rerank requires 'query' and 'documents'")

    payload = {
        "query": query,
        "documents": documents,
        "model": merged.get("model", "rerank-english-v3.0"),
        "top_n": int(merged.get("top_n", len(documents))),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/rerank", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()
        return {"results": data.get("results", []), "meta": data.get("meta")}
