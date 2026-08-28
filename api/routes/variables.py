"""
Variables API — manage reusable workflow variables (static or secret).

Routes:
  GET    /api/variables
  POST   /api/variables
  GET    /api/variables/{id}
  PUT    /api/variables/{id}
  DELETE /api/variables/{id}
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import User, Variable

router = APIRouter()


class VariableCreate(BaseModel):
    name: str
    value: str
    description: Optional[str] = None
    is_secret: bool = False  # if True, value is encrypted and masked in responses
    variable_type: str = "string"  # string | number | boolean | json


class VariableUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    is_secret: Optional[bool] = None


@router.get("")
async def list_variables(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Variable)
        .where(Variable.owner_id == user.id)
        .order_by(Variable.name.asc())
    )
    variables = result.scalars().all()
    return {"variables": [_serialize(v) for v in variables]}


@router.post("")
async def create_variable(
    body: VariableCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Check for duplicate name
    existing = await db.execute(
        select(Variable).where(Variable.owner_id == user.id, Variable.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Variable '{body.name}' already exists")

    stored_value = body.value
    if body.is_secret:
        from credentials.encryption import encrypt_token
        stored_value = encrypt_token(body.value)

    variable = Variable(
        owner_id=user.id,
        name=body.name,
        value=stored_value,
        description=body.description,
        is_secret=body.is_secret,
        variable_type=body.variable_type,
    )
    db.add(variable)
    await db.commit()
    await db.refresh(variable)
    return _serialize(variable)


@router.get("/{var_id}")
async def get_variable(
    var_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    var = await _get_or_404(var_id, user.id, db)
    return _serialize(var)


@router.put("/{var_id}")
async def update_variable(
    var_id: str,
    body: VariableUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    var = await _get_or_404(var_id, user.id, db)
    if body.name is not None:
        var.name = body.name
    if body.description is not None:
        var.description = body.description
    if body.is_secret is not None:
        var.is_secret = body.is_secret
    if body.value is not None:
        if var.is_secret or (body.is_secret is True):
            from credentials.encryption import encrypt_token
            var.value = encrypt_token(body.value)
        else:
            var.value = body.value

    await db.commit()
    await db.refresh(var)
    return _serialize(var)


@router.delete("/{var_id}")
async def delete_variable(
    var_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    var = await _get_or_404(var_id, user.id, db)
    await db.delete(var)
    await db.commit()
    return {"deleted": True, "id": var_id}


async def _get_or_404(var_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(Variable).where(Variable.id == var_id, Variable.owner_id == user_id)
    )
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(status_code=404, detail="Variable not found")
    return var


def _serialize(v) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "description": v.description,
        "variable_type": v.variable_type,
        "is_secret": v.is_secret,
        "value": "***" if v.is_secret else v.value,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }
