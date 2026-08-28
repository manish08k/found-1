"""Marketplace — list, get, publish, install, rate, unpublish."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from api.middleware.rbac import require_permission
from core.marketplace import (
    get_item, install_item, list_items, publish_item, rate_item, unpublish_item,
)
from storage.database import get_db
from storage.models import User

router = APIRouter()


class PublishRequest(BaseModel):
    name: str
    description: str = ""
    category: Optional[str] = None
    tags: list[str] = []
    item_type: str = "workflow"
    content: dict = {}


class RateRequest(BaseModel):
    rating: int


@router.get("")
async def browse(
    category: Optional[str] = None,
    item_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items = await list_items(db, category, item_type, search, page, limit)
    return [
        {
            "name": i.name, "slug": i.slug, "description": i.description,
            "category": i.category, "tags": i.tags, "item_type": i.item_type,
            "downloads": i.downloads,
            "avg_rating": (i.rating / i.rating_count) if i.rating_count else 0,
        }
        for i in items
    ]


@router.get("/{slug}")
async def get_one(slug: str, db: AsyncSession = Depends(get_db)):
    item = await get_item(db, slug)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {
        "name": item.name, "slug": item.slug, "description": item.description,
        "category": item.category, "tags": item.tags, "item_type": item.item_type,
        "content": item.content, "downloads": item.downloads,
        "avg_rating": (item.rating / item.rating_count) if item.rating_count else 0,
    }


@router.post("/publish", status_code=201)
async def publish(
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("marketplace:publish")),
):
    try:
        item = await publish_item(
            db, user.org_id, body.name, body.description, body.category, body.tags, body.item_type, body.content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"slug": item.slug, "name": item.name}


@router.post("/{slug}/install")
async def install(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        item, workflow = await install_item(db, slug, user_id=user.id, org_id=user.org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    response = {"name": item.name, "item_type": item.item_type.value, "content": item.content}
    if workflow:
        response["workflow_id"] = workflow.id
    return response


@router.post("/{slug}/rate")
async def rate(
    slug: str,
    body: RateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        item = await rate_item(db, slug, body.rating)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"avg_rating": item.rating / item.rating_count}


@router.delete("/{slug}")
async def unpublish(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("marketplace:publish")),
):
    try:
        await unpublish_item(db, slug, user.org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    return {"message": "Unpublished"}
