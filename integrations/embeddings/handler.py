"""
Standalone embedding nodes — produce dense vector representations.

Nodes:
  embedding.openai              — OpenAI text-embedding-3-small/large
  embedding.azure_openai        — Azure OpenAI embeddings deployment
  embedding.cohere              — Cohere embed-english-v3.0
  embedding.huggingface         — HuggingFace feature-extraction endpoint
  embedding.google              — Google generative AI embeddings
  embedding.mistral             — Mistral embed
  embedding.jina                — Jina AI embeddings
  embedding.voyageai            — VoyageAI embeddings
  embedding.together_ai         — Together AI embeddings (OpenAI-compatible)
  embedding.aws_bedrock         — AWS Bedrock Titan/Cohere embed
  embedding.ollama              — Local Ollama embedding models
  embedding.nomic               — Nomic Embed via HuggingFace-compatible API
"""
import asyncio

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _to_list(texts_or_text, input_data: dict) -> list[str]:
    """Normalize text/texts input to a list of strings."""
    texts = texts_or_text or input_data.get("texts") or input_data.get("text") or ""
    if isinstance(texts, str):
        return [texts]
    if isinstance(texts, list):
        return texts
    return [str(texts)]


# ─── OpenAI ───────────────────────────────────────────────────────────────────

@register_node("embedding.openai")
async def embedding_openai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via OpenAI API.
    config: model (text-embedding-3-small | text-embedding-3-large | text-embedding-ada-002),
            text (str) or texts (list[str]), dimensions (int, optional)
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("embedding.openai requires OPENAI_API_KEY")

    model = config.get("model", "text-embedding-3-small")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)
    dimensions = config.get("dimensions")

    payload: dict = {"model": model, "input": texts}
    if dimensions:
        payload["dimensions"] = int(dimensions)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "openai",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Azure OpenAI ─────────────────────────────────────────────────────────────

@register_node("embedding.azure_openai")
async def embedding_azure_openai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Azure OpenAI deployment.
    Requires AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT.
    config: deployment (embedding deployment name), api_version, text/texts
    """
    api_key = getattr(settings, "AZURE_OPENAI_API_KEY", None)
    endpoint = getattr(settings, "AZURE_OPENAI_ENDPOINT", None)
    if not api_key or not endpoint:
        raise ValueError("embedding.azure_openai requires AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT")

    deployment = config.get("deployment", "text-embedding-3-small")
    api_version = config.get("api_version", "2024-02-01")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            url,
            json={"input": texts},
            headers={"api-key": api_key},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": deployment,
        "provider": "azure_openai",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Cohere ───────────────────────────────────────────────────────────────────

@register_node("embedding.cohere")
async def embedding_cohere(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Cohere API.
    Requires COHERE_API_KEY.
    config: model (embed-english-v3.0 | embed-multilingual-v3.0),
            input_type (search_document | search_query | classification | clustering),
            text/texts
    """
    api_key = getattr(settings, "COHERE_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.cohere requires COHERE_API_KEY")

    model = config.get("model", "embed-english-v3.0")
    input_type = config.get("input_type", "search_document")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.cohere.ai/v1/embed",
            json={"texts": texts, "model": model, "input_type": input_type},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = data["embeddings"]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "cohere",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── HuggingFace ──────────────────────────────────────────────────────────────

@register_node("embedding.huggingface")
async def embedding_huggingface(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via HuggingFace Inference API (feature-extraction endpoint).
    Requires HUGGINGFACE_API_KEY.
    config: model (sentence-transformers/all-MiniLM-L6-v2), text/texts
    """
    api_key = getattr(settings, "HUGGINGFACE_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.huggingface requires HUGGINGFACE_API_KEY")

    model = config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://api-inference.huggingface.co/models/{model}",
            json={"inputs": texts},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    if isinstance(data, list) and isinstance(data[0], list) and isinstance(data[0][0], float):
        embeddings = data
    elif isinstance(data, list) and isinstance(data[0], float):
        embeddings = [data]
    else:
        embeddings = [data.get("embedding", data)]

    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "huggingface",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Google Generative AI ─────────────────────────────────────────────────────

@register_node("embedding.google")
async def embedding_google(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Google Generative AI (Gemini embedding models).
    Requires GOOGLE_API_KEY.
    config: model (models/text-embedding-004), task_type (RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY),
            text/texts
    """
    api_key = getattr(settings, "GOOGLE_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.google requires GOOGLE_API_KEY")

    model = config.get("model", "models/text-embedding-004")
    task_type = config.get("task_type", "RETRIEVAL_DOCUMENT")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    embeddings = []
    async with httpx.AsyncClient(timeout=60) as client:
        for text in texts:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:embedContent?key={api_key}"
            r = await client.post(url, json={
                "model": model,
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
            })
            r.raise_for_status()
            data = r.json()
            embeddings.append(data["embedding"]["values"])

    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "google",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Mistral ──────────────────────────────────────────────────────────────────

@register_node("embedding.mistral")
async def embedding_mistral(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Mistral AI API.
    Requires MISTRAL_API_KEY.
    config: model (mistral-embed), text/texts
    """
    api_key = getattr(settings, "MISTRAL_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.mistral requires MISTRAL_API_KEY")

    model = config.get("model", "mistral-embed")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.mistral.ai/v1/embeddings",
            json={"model": model, "input": texts},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "mistral",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Jina AI ──────────────────────────────────────────────────────────────────

@register_node("embedding.jina")
async def embedding_jina(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Jina AI API.
    Requires JINA_API_KEY.
    config: model (jina-embeddings-v3), task (retrieval.passage | retrieval.query),
            dimensions (optional), text/texts
    """
    api_key = getattr(settings, "JINA_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.jina requires JINA_API_KEY")

    model = config.get("model", "jina-embeddings-v3")
    task = config.get("task", "retrieval.passage")
    dimensions = config.get("dimensions")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    payload: dict = {"model": model, "task": task, "input": texts}
    if dimensions:
        payload["dimensions"] = int(dimensions)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.jina.ai/v1/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "jina",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── VoyageAI ─────────────────────────────────────────────────────────────────

@register_node("embedding.voyageai")
async def embedding_voyageai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via VoyageAI (retrieval-optimized models).
    Requires VOYAGE_API_KEY.
    config: model (voyage-3 | voyage-3-lite | voyage-finance-2 | voyage-code-3),
            input_type (document | query), text/texts
    """
    api_key = getattr(settings, "VOYAGE_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.voyageai requires VOYAGE_API_KEY")

    model = config.get("model", "voyage-3")
    input_type = config.get("input_type", "document")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.voyageai.com/v1/embeddings",
            json={"model": model, "input": texts, "input_type": input_type},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "voyageai",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Together AI ──────────────────────────────────────────────────────────────

@register_node("embedding.together_ai")
async def embedding_together_ai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Together AI (OpenAI-compatible).
    Requires TOGETHER_API_KEY.
    config: model (togethercomputer/m2-bert-80M-8k-retrieval), text/texts
    """
    api_key = getattr(settings, "TOGETHER_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.together_ai requires TOGETHER_API_KEY")

    model = config.get("model", "togethercomputer/m2-bert-80M-8k-retrieval")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.together.xyz/v1/embeddings",
            json={"model": model, "input": texts},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "together_ai",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── AWS Bedrock ──────────────────────────────────────────────────────────────

@register_node("embedding.aws_bedrock")
async def embedding_aws_bedrock(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via AWS Bedrock (Titan Embed, Cohere Embed on AWS).
    Requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION.
    config: model_id (amazon.titan-embed-text-v2:0 | cohere.embed-english-v3), text/texts
    """
    try:
        import boto3
        import json as _json
    except ImportError:
        raise RuntimeError("embedding.aws_bedrock requires boto3: pip install boto3")

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    region = config.get("region") or getattr(settings, "AWS_REGION", "us-east-1")
    model_id = config.get("model_id", "amazon.titan-embed-text-v2:0")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    client_kwargs = {"region_name": region}
    if access_key:
        client_kwargs["aws_access_key_id"] = access_key
    if secret_key:
        client_kwargs["aws_secret_access_key"] = secret_key

    def _embed(text: str) -> list[float]:
        bedrock = boto3.client("bedrock-runtime", **client_kwargs)
        if "titan" in model_id:
            body = _json.dumps({"inputText": text})
        else:
            body = _json.dumps({"texts": [text], "input_type": "search_document"})
        resp = bedrock.invoke_model(modelId=model_id, body=body,
                                    contentType="application/json", accept="application/json")
        result = _json.loads(resp["body"].read())
        if "titan" in model_id:
            return result["embedding"]
        return result["embeddings"][0]

    loop = asyncio.get_event_loop()
    embeddings = []
    for text in texts:
        emb = await loop.run_in_executor(None, _embed, text)
        embeddings.append(emb)

    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model_id,
        "provider": "aws_bedrock",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Ollama ───────────────────────────────────────────────────────────────────

@register_node("embedding.ollama")
async def embedding_ollama(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via local Ollama instance.
    config: base_url (http://localhost:11434), model (nomic-embed-text), text/texts
    """
    base_url = config.get("base_url") or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    model = config.get("model", "nomic-embed-text")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    embeddings = []
    async with httpx.AsyncClient(timeout=120) as client:
        for text in texts:
            r = await client.post(
                f"{base_url.rstrip('/')}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            r.raise_for_status()
            embeddings.append(r.json()["embedding"])

    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "ollama",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }


# ─── Nomic ────────────────────────────────────────────────────────────────────

@register_node("embedding.nomic")
async def embedding_nomic(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Embeddings via Nomic AI API (nomic-embed-text-v1.5 and variants).
    Requires NOMIC_API_KEY.
    config: model (nomic-embed-text-v1.5), task_type (search_document | search_query),
            dimensionality (int, optional), text/texts
    """
    api_key = getattr(settings, "NOMIC_API_KEY", None)
    if not api_key:
        raise ValueError("embedding.nomic requires NOMIC_API_KEY")

    model = config.get("model", "nomic-embed-text-v1.5")
    task_type = config.get("task_type", "search_document")
    dimensionality = config.get("dimensionality")
    texts = _to_list(config.get("text") or config.get("texts"), input_data)

    payload: dict = {"model": model, "task_type": task_type, "texts": texts}
    if dimensionality:
        payload["dimensionality"] = int(dimensionality)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api-atlas.nomic.ai/v1/embedding/text",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embeddings = data["embeddings"]
    return {
        "embeddings": embeddings,
        "embedding": embeddings[0] if len(embeddings) == 1 else embeddings,
        "model": model,
        "provider": "nomic",
        "dimensions": len(embeddings[0]) if embeddings else 0,
    }
