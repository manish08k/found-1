"""Marketplace — publish/install/rate shared workflow templates and node packs."""
import re
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import MarketplaceItem, Workflow, WorkflowStatus


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def list_items(db: AsyncSession, category: str | None = None, item_type: str | None = None,
                      search: str | None = None, page: int = 1, limit: int = 20):
    query = select(MarketplaceItem).where(MarketplaceItem.is_published == True)  # noqa: E712
    if category:
        query = query.where(MarketplaceItem.category == category)
    if item_type:
        query = query.where(MarketplaceItem.item_type == item_type)
    if search:
        query = query.where(or_(
            MarketplaceItem.name.ilike(f"%{search}%"),
            MarketplaceItem.description.ilike(f"%{search}%"),
        ))
    query = query.order_by(MarketplaceItem.downloads.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_item(db: AsyncSession, slug: str) -> MarketplaceItem | None:
    result = await db.execute(
        select(MarketplaceItem).where(MarketplaceItem.slug == slug, MarketplaceItem.is_published == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def publish_item(db: AsyncSession, org_id: str | None, name: str, description: str,
                        category: str, tags: list[str], item_type: str, content: dict) -> MarketplaceItem:
    base_slug = _slugify(name)
    # Try the base slug first; if taken, append a counter so the caller
    # doesn't get a hard "name already exists" error when it's just a slug
    # collision from a near-identical name.
    slug = base_slug
    for attempt in range(1, 100):
        existing = await db.execute(select(MarketplaceItem).where(MarketplaceItem.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{attempt}"
    else:
        raise ValueError("An item with this name already exists")

    item = MarketplaceItem(
        org_id=org_id,
        name=name,
        slug=slug,
        description=description,
        category=category,
        tags=tags,
        item_type=item_type,
        content=content,
        is_published=True,
    )
    db.add(item)
    return item


async def install_item(db: AsyncSession, slug: str, user_id: str, org_id: str | None) -> tuple[MarketplaceItem, Workflow | None]:
    """
    Installing a "workflow"/"template" item creates a real, editable copy
    in the installing user's workspace — that's the actual point of a
    marketplace (browse -> get something you can immediately use), not
    just "here's some JSON, go build it yourself". "node" items (a single
    reusable node config, not a full workflow) have nothing to instantiate
    as a workflow, so those just increment downloads and return the item;
    the frontend inserts a node item directly into whatever workflow is
    currently open instead.
    """
    result = await db.execute(
        select(MarketplaceItem).where(MarketplaceItem.slug == slug, MarketplaceItem.is_published == True)  # noqa: E712
    )
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError("Item not found")
    item.downloads += 1

    new_workflow = None
    if item.item_type.value in ("workflow", "template"):
        definition = item.content if isinstance(item.content, dict) and "nodes" in item.content else {"nodes": [], "edges": []}
        new_workflow = Workflow(
            owner_id=user_id,
            org_id=org_id,
            name=f"{item.name} (from marketplace)",
            description=item.description,
            status=WorkflowStatus.inactive,  # installed inactive — the person still needs to connect their own credentials before it can run
            definition=definition,
        )
        db.add(new_workflow)
        await db.flush()

    return item, new_workflow


async def rate_item(db: AsyncSession, slug: str, rating: int) -> MarketplaceItem:
    if rating < 1 or rating > 5:
        raise ValueError("Rating must be between 1 and 5")
    result = await db.execute(select(MarketplaceItem).where(MarketplaceItem.slug == slug))
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError("Item not found")
    item.rating += rating
    item.rating_count += 1
    return item


async def unpublish_item(db: AsyncSession, slug: str, org_id: str | None) -> MarketplaceItem:
    query = select(MarketplaceItem).where(MarketplaceItem.slug == slug)
    if org_id is not None:
        query = query.where(MarketplaceItem.org_id == org_id)
    else:
        # Personal (no-org) users can only unpublish items they themselves
        # published (org_id IS NULL items).
        query = query.where(MarketplaceItem.org_id == None)  # noqa: E711
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError("Item not found or not owned by you")
    item.is_published = False
    return item
