"""
Assistants API — manage AI assistants (OpenAI Assistants-compatible).

An Assistant is a named AI persona with a system prompt, optional tools,
and optional document store. Backed by the Workflow model with type=assistant.

Routes:
  GET    /api/assistants
  POST   /api/assistants
  GET    /api/assistants/{id}
  PUT    /api/assistants/{id}
  DELETE /api/assistants/{id}
  POST   /api/assistants/{id}/threads         — create a thread
  GET    /api/assistants/{id}/threads         — list threads
  POST   /api/assistants/{id}/threads/{tid}/messages  — add message to thread
  GET    /api/assistants/{id}/threads/{tid}/messages  — list thread messages
  POST   /api/assistants/{id}/threads/{tid}/run       — run the assistant on thread
"""
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import User, Assistant, AssistantThread, AssistantMessage

router = APIRouter()


# ─── Schemas ───────────────────────────────────────────────────────────────────

class AssistantCreate(BaseModel):
    name: str
    description: Optional[str] = None
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-4o-mini"
    provider: str = "openai"  # openai | anthropic | gemini
    tools: List[str] = []      # list of tool node IDs to make available
    temperature: float = 0.7
    max_tokens: int = 1024
    document_store_id: Optional[str] = None  # for RAG


class AssistantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tools: Optional[List[str]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    document_store_id: Optional[str] = None


class ThreadCreate(BaseModel):
    metadata: Optional[dict] = None


class ThreadMessageCreate(BaseModel):
    role: str = "user"
    content: str


# ─── Assistants CRUD ───────────────────────────────────────────────────────────

@router.get("")
async def list_assistants(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Assistant).where(Assistant.owner_id == user.id).order_by(Assistant.created_at.desc())
    )
    assistants = result.scalars().all()
    return {"assistants": [_serialize_assistant(a) for a in assistants]}


@router.post("")
async def create_assistant(
    body: AssistantCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assistant = Assistant(
        owner_id=user.id,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        model=body.model,
        provider=body.provider,
        tools=body.tools,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        document_store_id=body.document_store_id,
    )
    db.add(assistant)
    await db.commit()
    await db.refresh(assistant)
    return _serialize_assistant(assistant)


@router.get("/{assistant_id}")
async def get_assistant(
    assistant_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assistant = await _get_or_404(assistant_id, user.id, db)
    return _serialize_assistant(assistant)


@router.put("/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    body: AssistantUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assistant = await _get_or_404(assistant_id, user.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(assistant, field, value)
    await db.commit()
    await db.refresh(assistant)
    return _serialize_assistant(assistant)


@router.delete("/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assistant = await _get_or_404(assistant_id, user.id, db)
    await db.delete(assistant)
    await db.commit()
    return {"deleted": True, "id": assistant_id}


# ─── Threads ───────────────────────────────────────────────────────────────────

@router.post("/{assistant_id}/threads")
async def create_thread(
    assistant_id: str,
    body: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assistant = await _get_or_404(assistant_id, user.id, db)
    thread = AssistantThread(
        assistant_id=assistant_id,
        user_id=user.id,
        metadata=body.metadata or {},
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return {"id": thread.id, "assistant_id": assistant_id, "created_at": thread.created_at.isoformat()}


@router.get("/{assistant_id}/threads")
async def list_threads(
    assistant_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_or_404(assistant_id, user.id, db)
    result = await db.execute(
        select(AssistantThread)
        .where(AssistantThread.assistant_id == assistant_id, AssistantThread.user_id == user.id)
        .order_by(AssistantThread.created_at.desc())
    )
    threads = result.scalars().all()
    return {"threads": [{"id": t.id, "created_at": t.created_at.isoformat(), "metadata": t.metadata} for t in threads]}


@router.post("/{assistant_id}/threads/{thread_id}/messages")
async def add_thread_message(
    assistant_id: str,
    thread_id: str,
    body: ThreadMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assistant = await _get_or_404(assistant_id, user.id, db)
    thread = await _get_thread_or_404(thread_id, assistant_id, db)

    message = AssistantMessage(
        thread_id=thread_id,
        role=body.role,
        content=body.content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return {"id": message.id, "role": message.role, "content": message.content,
            "created_at": message.created_at.isoformat()}


@router.get("/{assistant_id}/threads/{thread_id}/messages")
async def list_thread_messages(
    assistant_id: str,
    thread_id: str,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_or_404(assistant_id, user.id, db)
    await _get_thread_or_404(thread_id, assistant_id, db)

    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread_id)
        .order_by(AssistantMessage.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return {
        "messages": [{"id": m.id, "role": m.role, "content": m.content,
                      "created_at": m.created_at.isoformat()} for m in messages]
    }


@router.post("/{assistant_id}/threads/{thread_id}/run")
async def run_thread(
    assistant_id: str,
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run the assistant on the thread's messages and append the response."""
    assistant = await _get_or_404(assistant_id, user.id, db)
    await _get_thread_or_404(thread_id, assistant_id, db)

    # Load thread messages
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread_id)
        .order_by(AssistantMessage.created_at.asc())
        .limit(50)
    )
    messages = result.scalars().all()

    # Build conversation history
    history = [{"role": m.role, "content": m.content} for m in messages]
    if not history:
        raise HTTPException(status_code=400, detail="Thread has no messages to run")

    # Call LLM
    from integrations.ai.handler import _call_anthropic, _call_openai
    from core.config import settings

    system_prompt = assistant.system_prompt
    # Include RAG context if document_store_id configured
    rag_context = ""
    if assistant.document_store_id:
        try:
            from storage.models import DocumentStore
            ds_result = await db.execute(select(DocumentStore).where(DocumentStore.id == assistant.document_store_id))
            ds = ds_result.scalar_one_or_none()
            if ds:
                # Search vector docs relevant to last user message
                last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
                from integrations.vector.handler import vector_search
                search_result = await vector_search(
                    {"collection": assistant.document_store_id, "query": last_user, "top_k": 3},
                    {}, None, db,
                )
                rag_context = search_result.get("context", "")
        except Exception:
            pass

    if rag_context:
        system_prompt = f"{system_prompt}\n\nRelevant context:\n{rag_context}"

    # Build final prompt from history
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)

    if assistant.provider == "anthropic":
        response_text = await _call_anthropic(
            assistant.model, system_prompt, transcript, assistant.max_tokens, assistant.temperature
        )
    else:
        response_text = await _call_openai(
            assistant.model, system_prompt, transcript, assistant.max_tokens, assistant.temperature
        )

    # Save assistant response
    response_msg = AssistantMessage(
        thread_id=thread_id,
        role="assistant",
        content=response_text,
    )
    db.add(response_msg)
    await db.commit()
    await db.refresh(response_msg)

    return {
        "id": response_msg.id,
        "role": "assistant",
        "content": response_text,
        "thread_id": thread_id,
        "created_at": response_msg.created_at.isoformat(),
    }


# ─── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(assistant_id: str, user_id: str, db: AsyncSession) -> "Assistant":
    result = await db.execute(
        select(Assistant).where(Assistant.id == assistant_id, Assistant.owner_id == user_id)
    )
    assistant = result.scalar_one_or_none()
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return assistant


async def _get_thread_or_404(thread_id: str, assistant_id: str, db: AsyncSession) -> "AssistantThread":
    result = await db.execute(
        select(AssistantThread).where(
            AssistantThread.id == thread_id,
            AssistantThread.assistant_id == assistant_id,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


def _serialize_assistant(a) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "system_prompt": a.system_prompt,
        "model": a.model,
        "provider": a.provider,
        "tools": a.tools,
        "temperature": a.temperature,
        "max_tokens": a.max_tokens,
        "document_store_id": a.document_store_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
