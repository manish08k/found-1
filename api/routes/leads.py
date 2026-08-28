"""
Leads API — capture leads from chatbot widget interactions.

Routes:
  GET    /api/leads
  POST   /api/leads
  GET    /api/leads/{id}
  PUT    /api/leads/{id}
  DELETE /api/leads/{id}
  GET    /api/leads/export/csv — export leads as CSV
"""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import User, Lead

router = APIRouter()


class LeadCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    workflow_id: Optional[str] = None
    conversation_id: Optional[str] = None
    metadata: Optional[dict] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None  # new | contacted | qualified | disqualified
    metadata: Optional[dict] = None


@router.get("")
async def list_leads(
    workflow_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Lead).where(Lead.owner_id == user.id).order_by(Lead.created_at.desc())
    if workflow_id:
        stmt = stmt.where(Lead.workflow_id == workflow_id)
    if status:
        stmt = stmt.where(Lead.status == status)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    leads = result.scalars().all()
    return {"leads": [_serialize(l) for l in leads], "count": len(leads)}


@router.post("")
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lead = Lead(
        owner_id=user.id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        workflow_id=body.workflow_id,
        conversation_id=body.conversation_id,
        status="new",
        lead_metadata=body.metadata or {},
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return _serialize(lead)


@router.get("/export/csv")
async def export_leads_csv(
    workflow_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Lead).where(Lead.owner_id == user.id).order_by(Lead.created_at.desc())
    if workflow_id:
        stmt = stmt.where(Lead.workflow_id == workflow_id)

    result = await db.execute(stmt)
    leads = result.scalars().all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "name", "email", "phone", "status", "workflow_id", "created_at"])
    writer.writeheader()
    for lead in leads:
        writer.writerow({
            "id": lead.id,
            "name": lead.name or "",
            "email": lead.email or "",
            "phone": lead.phone or "",
            "status": lead.status or "",
            "workflow_id": lead.workflow_id or "",
            "created_at": lead.created_at.isoformat() if lead.created_at else "",
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/{lead_id}")
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lead = await _get_or_404(lead_id, user.id, db)
    return _serialize(lead)


@router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lead = await _get_or_404(lead_id, user.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "metadata":
            lead.lead_metadata = value
        else:
            setattr(lead, field, value)
    await db.commit()
    await db.refresh(lead)
    return _serialize(lead)


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lead = await _get_or_404(lead_id, user.id, db)
    await db.delete(lead)
    await db.commit()
    return {"deleted": True, "id": lead_id}


async def _get_or_404(lead_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.owner_id == user_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def _serialize(l) -> dict:
    return {
        "id": l.id,
        "name": l.name,
        "email": l.email,
        "phone": l.phone,
        "status": l.status,
        "workflow_id": l.workflow_id,
        "conversation_id": l.conversation_id,
        "metadata": l.lead_metadata,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }
