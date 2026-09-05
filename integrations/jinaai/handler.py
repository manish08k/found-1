"""
Jina AI neural search integration.

Provides text embedding, re-ranking, and zero-shot classification via
the Jina AI API.

Credential fields:
  - api_key : Jina AI API key (Bearer token auth)

Base URL: https://api.jina.ai/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.jina.ai/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("jinaai credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Jina AI API error {r.status_code}: {detail}")


@register_node("jinaai.embed_text")
async def jinaai_embed_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Generate vector embeddings for one or more texts.

    Config / input_data fields:
      - input   (required) : string or list of strings to embed
      - model              : embedding model name
                             (default: 'jina-embeddings-v2-base-en')
      - encoding_type      : 'float' | 'binary' | 'ubinary' (default 'float')
      - task               : retrieval task hint, e.g. 'retrieval.passage'
    """
    raw_input = config.get("input") or input_data.get("input")
    if not raw_input:
        raise ValueError("jinaai.embed_text requires 'input'")

    texts = raw_input if isinstance(raw_input, list) else [raw_input]
    model = config.get("model") or input_data.get("model", "jina-embeddings-v2-base-en")
    encoding_type = config.get("encoding_type") or input_data.get("encoding_type", "float")
    task = config.get("task") or input_data.get("task")

    payload: dict = {"input": texts, "model": model, "encoding_type": encoding_type}
    if task:
        payload["task"] = task

    log.info("jinaai.embed_text", model=model, num_texts=len(texts))
    async with await _client(credential_id, db) as client:
        r = await client.post("/embeddings", json=payload)
        _raise_for_status(r)
        data = r.json()

    embeddings = [item.get("embedding") for item in data.get("data", [])]
    return {
        "embeddings": embeddings,
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
        "count": len(embeddings),
    }


@register_node("jinaai.rerank")
async def jinaai_rerank(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Re-rank a list of documents against a query.

    Config / input_data fields:
      - query     (required) : the search query string
      - documents (required) : list of strings or dicts with 'text' key
      - model                : reranker model (default: 'jina-reranker-v2-base-multilingual')
      - top_n                : return only the top N results (optional)
      - return_documents     : include document text in response (default True)
    """
    query = config.get("query") or input_data.get("query")
    documents = config.get("documents") or input_data.get("documents")

    if not query:
        raise ValueError("jinaai.rerank requires 'query'")
    if not documents:
        raise ValueError("jinaai.rerank requires 'documents'")

    model = config.get("model") or input_data.get("model", "jina-reranker-v2-base-multilingual")
    top_n = config.get("top_n") or input_data.get("top_n")
    return_documents = bool(
        config.get("return_documents", True)
        if "return_documents" in config
        else input_data.get("return_documents", True)
    )

    # Normalise documents to list of dicts
    norm_docs = []
    for doc in (documents if isinstance(documents, list) else [documents]):
        norm_docs.append({"text": doc} if isinstance(doc, str) else doc)

    payload: dict = {
        "query": query,
        "documents": norm_docs,
        "model": model,
        "return_documents": return_documents,
    }
    if top_n is not None:
        payload["top_n"] = int(top_n)

    log.info("jinaai.rerank", model=model, query_len=len(query), doc_count=len(norm_docs))
    async with await _client(credential_id, db) as client:
        r = await client.post("/rerank", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "results": data.get("results", []),
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


@register_node("jinaai.classify_text")
async def jinaai_classify_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Zero-shot classify text into provided labels.

    Config / input_data fields:
      - input   (required) : string or list of strings to classify
      - labels  (required) : list of candidate label strings
      - model              : classifier model
                             (default: 'jina-embeddings-v2-base-en')
    """
    raw_input = config.get("input") or input_data.get("input")
    labels = config.get("labels") or input_data.get("labels")

    if not raw_input:
        raise ValueError("jinaai.classify_text requires 'input'")
    if not labels:
        raise ValueError("jinaai.classify_text requires 'labels'")

    texts = raw_input if isinstance(raw_input, list) else [raw_input]
    label_list = labels if isinstance(labels, list) else [l.strip() for l in str(labels).split(",")]
    model = config.get("model") or input_data.get("model", "jina-embeddings-v2-base-en")

    payload: dict = {"input": texts, "labels": label_list, "model": model}

    log.info("jinaai.classify_text", model=model, num_texts=len(texts), num_labels=len(label_list))
    async with await _client(credential_id, db) as client:
        r = await client.post("/classify", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "predictions": data.get("data", []),
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }
