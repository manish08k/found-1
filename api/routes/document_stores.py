"""
Document Stores API — manage collections of documents for RAG.

A DocumentStore is a named vector collection that can be populated
from various loaders and queried by assistants/chatflows.

Routes:
  GET    /api/document-stores
  POST   /api/document-stores
  GET    /api/document-stores/{id}
  PUT    /api/document-stores/{id}
  DELETE /api/document-stores/{id}
  POST   /api/document-stores/{id}/upsert     — add documents
  POST   /api/document-stores/{id}/query      — semantic search
  DELETE /api/document-stores/{id}/documents  — clear documents
  GET    /api/document-stores/{id}/chunks     — list stored chunks
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import User, DocumentStore, VectorDocument

router = APIRouter()


class DocumentStoreCreate(BaseModel):
    name: str
    description: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str = "openai"
    chunk_size: int = 1000
    chunk_overlap: int = 200


class DocumentStoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class UpsertDocumentsBody(BaseModel):
    documents: List[dict]  # list of {"text": str, "metadata": dict}
    collection: Optional[str] = None  # override store name as collection key


class QueryBody(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.0
    collection: Optional[str] = None


# ─── CRUD ───────────────────────────────────────────────────────────────────────

@router.get("")
async def list_document_stores(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DocumentStore)
        .where(DocumentStore.owner_id == user.id)
        .order_by(DocumentStore.created_at.desc())
    )
    stores = result.scalars().all()
    return {"document_stores": [_serialize(s) for s in stores]}


@router.post("")
async def create_document_store(
    body: DocumentStoreCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = DocumentStore(
        owner_id=user.id,
        name=body.name,
        description=body.description,
        embedding_model=body.embedding_model,
        embedding_provider=body.embedding_provider,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return _serialize(store)


@router.get("/{store_id}")
async def get_document_store(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = await _get_or_404(store_id, user.id, db)
    # Count documents
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(VectorDocument.id)).where(VectorDocument.collection == store_id)
    )
    doc_count = count_result.scalar_one()
    data = _serialize(store)
    data["document_count"] = doc_count
    return data


@router.put("/{store_id}")
async def update_document_store(
    store_id: str,
    body: DocumentStoreUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = await _get_or_404(store_id, user.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(store, field, value)
    await db.commit()
    await db.refresh(store)
    return _serialize(store)


@router.delete("/{store_id}")
async def delete_document_store(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = await _get_or_404(store_id, user.id, db)
    # Delete all documents in collection
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(VectorDocument).where(VectorDocument.collection == store_id))
    await db.delete(store)
    await db.commit()
    return {"deleted": True, "id": store_id}


# ─── Document Operations ───────────────────────────────────────────────────────

@router.post("/{store_id}/upsert")
async def upsert_documents(
    store_id: str,
    body: UpsertDocumentsBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Embed and store documents in the document store."""
    store = await _get_or_404(store_id, user.id, db)
    collection = body.collection or store_id

    # Use vector.upsert node logic
    from integrations.vector.handler import vector_upsert, _embed

    texts = [d["text"] if isinstance(d, dict) else str(d) for d in body.documents]
    metadatas = [d.get("metadata", {}) if isinstance(d, dict) else {} for d in body.documents]

    if not texts:
        return {"upserted": 0}

    embeddings = await _embed(texts, store.embedding_model)

    ids = []
    for text, emb, meta in zip(texts, embeddings, metadatas):
        doc = VectorDocument(
            workflow_id=store_id,  # reuse workflow_id field to scope to store
            collection=collection,
            text=text,
            embedding=emb,
            doc_metadata=meta,
        )
        db.add(doc)
        await db.flush()
        ids.append(doc.id)

    await db.commit()
    return {"upserted": len(ids), "ids": ids, "collection": collection}


@router.post("/{store_id}/query")
async def query_document_store(
    store_id: str,
    body: QueryBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Semantic search within a document store."""
    store = await _get_or_404(store_id, user.id, db)
    collection = body.collection or store_id

    from integrations.vector.handler import _embed, _cosine_similarity

    query_embedding = (await _embed([body.query], store.embedding_model))[0]

    result = await db.execute(
        select(VectorDocument).where(
            VectorDocument.collection == collection
        )
    )
    docs = result.scalars().all()

    scored = [(d, _cosine_similarity(query_embedding, d.embedding)) for d in docs]
    scored = [(d, s) for d, s in scored if s >= body.min_score]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:body.top_k]

    return {
        "results": [
            {"text": d.text, "score": round(s, 4), "metadata": d.doc_metadata, "id": d.id}
            for d, s in top
        ],
        "context": "\n\n".join(d.text for d, _ in top),
        "total_in_store": len(docs),
        "query": body.query,
    }


@router.delete("/{store_id}/documents")
async def clear_documents(
    store_id: str,
    collection: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete all documents from the store (or a specific sub-collection)."""
    store = await _get_or_404(store_id, user.id, db)
    from sqlalchemy import delete as sql_delete

    col = collection or store_id
    result = await db.execute(
        sql_delete(VectorDocument).where(VectorDocument.collection == col)
    )
    await db.commit()
    return {"deleted": result.rowcount, "collection": col}


@router.get("/{store_id}/chunks")
async def list_chunks(
    store_id: str,
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List stored document chunks (without embeddings)."""
    await _get_or_404(store_id, user.id, db)

    result = await db.execute(
        select(VectorDocument)
        .where(VectorDocument.collection == store_id)
        .order_by(VectorDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    docs = result.scalars().all()

    return {
        "chunks": [
            {"id": d.id, "text": d.text[:200], "metadata": d.doc_metadata,
             "created_at": d.created_at.isoformat()}
            for d in docs
        ],
        "count": len(docs),
    }


# ─── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(store_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(DocumentStore).where(DocumentStore.id == store_id, DocumentStore.owner_id == user_id)
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Document store not found")
    return store


def _serialize(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "embedding_model": s.embedding_model,
        "embedding_provider": s.embedding_provider,
        "chunk_size": s.chunk_size,
        "chunk_overlap": s.chunk_overlap,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
