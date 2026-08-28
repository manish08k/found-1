"""
API Keys management — create/revoke API keys for programmatic access.

Routes:
  GET    /api/api-keys
  POST   /api/api-keys
  DELETE /api/api-keys/{id}
  PUT    /api/api-keys/{id}        — rename / update metadata
  POST   /api/api-keys/{id}/rotate — rotate the key (revoke old, issue new)
"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import User, APIKey

router = APIRouter()


class APIKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    expires_days: Optional[int] = None  # None = never expires


class APIKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


def _generate_key() -> tuple[str, str]:
    """Returns (plain_key, key_hash). Only the hash is stored."""
    raw = f"af_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, key_hash


@router.get("")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id, APIKey.revoked == False)  # noqa: E712
        .order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return {
        "api_keys": [
            {
                "id": k.id,
                "name": k.name,
                "description": k.description,
                "key_prefix": k.key_prefix,
                "created_at": k.created_at.isoformat(),
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in keys
        ]
    }


@router.post("")
async def create_api_key(
    body: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plain_key, key_hash = _generate_key()

    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=body.expires_days)

    api_key = APIKey(
        user_id=user.id,
        name=body.name,
        description=body.description,
        key_hash=key_hash,
        key_prefix=plain_key[:10],  # "af_XXXXXXXX" — first 10 chars shown for identification
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": plain_key,  # Only returned ONCE at creation time
        "key_prefix": api_key.key_prefix,
        "created_at": api_key.created_at.isoformat(),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "warning": "Store this key safely — it will not be shown again.",
    }


@router.put("/{key_id}")
async def update_api_key(
    key_id: str,
    body: APIKeyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = await _get_or_404(key_id, user.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(key, field, value)
    await db.commit()
    await db.refresh(key)
    return {"id": key.id, "name": key.name, "description": key.description}


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = await _get_or_404(key_id, user.id, db)
    key.revoked = True
    key.revoked_at = datetime.utcnow()
    await db.commit()
    return {"revoked": True, "id": key_id}


@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoke the old key and issue a new one with the same name/metadata."""
    old_key = await _get_or_404(key_id, user.id, db)
    old_key.revoked = True
    old_key.revoked_at = datetime.utcnow()

    plain_key, key_hash = _generate_key()
    new_key = APIKey(
        user_id=user.id,
        name=old_key.name,
        description=old_key.description,
        key_hash=key_hash,
        key_prefix=plain_key[:10],
        expires_at=old_key.expires_at,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return {
        "id": new_key.id,
        "name": new_key.name,
        "key": plain_key,
        "key_prefix": new_key.key_prefix,
        "rotated_from": key_id,
        "warning": "Store this key safely — it will not be shown again.",
    }


async def _get_or_404(key_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id, APIKey.revoked == False)  # noqa
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key
