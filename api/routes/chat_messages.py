"""
Chat Messages API — persistent chat sessions and message history
for chatflow/assistant endpoints.

Routes:
  POST   /api/chat-messages/{workflow_id}   — send a message, get a response
  GET    /api/chat-messages/{workflow_id}   — list messages for a conversation
  DELETE /api/chat-messages/{workflow_id}   — clear conversation history
  GET    /api/chat-messages/{workflow_id}/{id} — get single message
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import Workflow, MemoryMessage, User

router = APIRouter()


class ChatMessageCreate(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None  # alias for conversation_id


class ChatMessageResponse(BaseModel):
    id: str
    workflow_id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime


@router.post("/{workflow_id}")
async def send_chat_message(
    workflow_id: str,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a message to a chatflow and receive the AI response."""
    # Validate workflow exists and belongs to user/org
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    conversation_id = body.conversation_id or body.session_id or str(uuid.uuid4())

    # Trigger the workflow with the chat message as input
    from core.execution_engine import execute_workflow
    from storage.database import db_context

    input_data = {
        "message": body.message,
        "conversation_id": conversation_id,
        "user_id": user.id,
        "role": "user",
    }

    try:
        async with db_context() as exec_db:
            result_data = await execute_workflow(
                workflow_id=workflow_id,
                trigger_type="chat",
                trigger_data=input_data,
                db=exec_db,
            )
    except Exception as e:
        # Return error as chat message rather than raising
        result_data = {"text": f"Error: {str(e)}", "error": True}

    # Extract response text from various node output formats
    response_text = (
        result_data.get("text")
        or result_data.get("response")
        or result_data.get("answer")
        or result_data.get("output")
        or str(result_data)
    )

    # Persist both messages
    user_msg = MemoryMessage(
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        role="user",
        content=body.message,
    )
    assistant_msg = MemoryMessage(
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        role="assistant",
        content=response_text,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return {
        "id": assistant_msg.id,
        "conversation_id": conversation_id,
        "question": body.message,
        "text": response_text,
        "sourceDocuments": result_data.get("sourceDocuments") or result_data.get("results"),
        "createdDate": assistant_msg.created_at.isoformat(),
    }


@router.get("/{workflow_id}")
async def list_chat_messages(
    workflow_id: str,
    conversation_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List chat messages for a workflow/conversation."""
    stmt = (
        select(MemoryMessage)
        .where(MemoryMessage.workflow_id == workflow_id)
        .order_by(MemoryMessage.created_at.asc())
        .limit(limit)
    )
    if conversation_id:
        stmt = stmt.where(MemoryMessage.conversation_id == conversation_id)

    result = await db.execute(stmt)
    messages = result.scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "conversation_id": m.conversation_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.delete("/{workflow_id}")
async def clear_chat_messages(
    workflow_id: str,
    conversation_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Clear conversation history for a workflow."""
    stmt = delete(MemoryMessage).where(MemoryMessage.workflow_id == workflow_id)
    if conversation_id:
        stmt = stmt.where(MemoryMessage.conversation_id == conversation_id)

    result = await db.execute(stmt)
    await db.commit()

    return {"deleted": result.rowcount, "workflow_id": workflow_id}


@router.get("/{workflow_id}/{message_id}")
async def get_chat_message(
    workflow_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single chat message by ID."""
    result = await db.execute(
        select(MemoryMessage).where(
            MemoryMessage.id == message_id,
            MemoryMessage.workflow_id == workflow_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "conversation_id": message.conversation_id,
        "workflow_id": workflow_id,
        "created_at": message.created_at.isoformat(),
    }
