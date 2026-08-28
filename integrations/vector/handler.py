"""
Vector store nodes — the missing RAG (Retrieval-Augmented Generation)
primitive. Embeddings come from OpenAI's embeddings API (works
standalone from chat — an Anthropic-only deployment can still embed);
storage/search is storage.models.VectorDocument with cosine similarity
computed in Python rather than pgvector, so this works on any Postgres
without needing an extension enabled — see that model's docstring for
the tradeoff and the upgrade path once collection sizes justify it.

Nodes:
  - vector.upsert  — embed text and store it in a named collection
  - vector.search  — embed a query and return the top-K most similar
                      stored documents (RAG retrieval)
  - vector.delete_collection — clear out a collection
"""
import math

import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


async def _embed(texts: list[str], model: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "Vector store nodes need OPENAI_API_KEY set (embeddings are OpenAI-only "
            "regardless of which provider ai.chat uses — Anthropic doesn't offer an embeddings API)."
        )
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            OPENAI_EMBEDDINGS_URL,
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={"input": texts, "model": model},
        )
        r.raise_for_status()
        data = r.json()
    return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@register_node("vector.upsert")
async def vector_upsert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    from storage.models import VectorDocument

    workflow_id = config.get("_workflow_id")
    collection = config.get("collection") or input_data.get("collection")
    text = config.get("text") or input_data.get("text")
    metadata = config.get("metadata") or input_data.get("metadata") or {}
    if not collection:
        raise ValueError("vector.upsert requires 'collection'")
    if not text:
        raise ValueError("vector.upsert requires 'text'")
    if not isinstance(text, list):
        text = [text]
    if not isinstance(metadata, list):
        metadata = [metadata] * len(text)

    embeddings = await _embed(text)
    ids = []
    for t, emb, meta in zip(text, embeddings, metadata):
        doc = VectorDocument(workflow_id=workflow_id, collection=collection, text=t, embedding=emb, doc_metadata=meta)
        db.add(doc)
        await db.flush()
        ids.append(doc.id)

    return {"upserted": len(ids), "ids": ids, "collection": collection}


@register_node("vector.search")
async def vector_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """RAG retrieval: embed the query, return the top-K most similar documents in the collection."""
    from sqlalchemy import select
    from storage.models import VectorDocument

    workflow_id = config.get("_workflow_id")
    collection = config.get("collection") or input_data.get("collection")
    query = config.get("query") or input_data.get("query")
    top_k = min(int(config.get("top_k", 5)), 50)
    min_score = float(config.get("min_score", 0.0))
    if not collection:
        raise ValueError("vector.search requires 'collection'")
    if not query:
        raise ValueError("vector.search requires 'query'")

    query_embedding = (await _embed([query]))[0]

    result = await db.execute(
        select(VectorDocument).where(VectorDocument.workflow_id == workflow_id, VectorDocument.collection == collection)
    )
    docs = result.scalars().all()

    scored = [
        (d, _cosine_similarity(query_embedding, d.embedding))
        for d in docs
    ]
    scored = [(d, s) for d, s in scored if s >= min_score]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top = scored[:top_k]

    return {
        "results": [
            {"text": d.text, "score": round(score, 4), "metadata": d.doc_metadata}
            for d, score in top
        ],
        "context": "\n\n".join(d.text for d, _ in top),  # ready to drop straight into an ai.chat prompt for RAG
        "total_in_collection": len(docs),
    }


@register_node("vector.delete_collection")
async def vector_delete_collection(config: dict, input_data: dict, credential_id: str, db) -> dict:
    from sqlalchemy import delete
    from storage.models import VectorDocument

    workflow_id = config.get("_workflow_id")
    collection = config.get("collection") or input_data.get("collection")
    if not collection:
        raise ValueError("vector.delete_collection requires 'collection'")

    result = await db.execute(
        delete(VectorDocument).where(VectorDocument.workflow_id == workflow_id, VectorDocument.collection == collection)
    )
    return {"deleted": result.rowcount, "collection": collection}
