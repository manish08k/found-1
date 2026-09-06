"""LLMRails integration — LLM infrastructure and embeddings."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.llmrails.com/v1"


def _headers(config: dict) -> dict:
    return {"X-API-KEY": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("llmrails.add_to_corpus")
async def llmrails_add_to_corpus(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    corpus_id = merged.get("corpus_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/corpus/{corpus_id}/document", json={
            "rawText": merged.get("text", ""),
            "metadata": merged.get("metadata", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("llmrails.query_corpus")
async def llmrails_query_corpus(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    corpus_id = merged.get("corpus_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/corpus/{corpus_id}/query", json={
            "query": merged.get("query", ""),
            "topK": merged.get("top_k", 5),
        })
        r.raise_for_status()
    return r.json()
