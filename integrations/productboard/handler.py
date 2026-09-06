"""Productboard integration — features, notes, and product management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PRODUCTBOARD_BASE = "https://api.productboard.com"


def _productboard_headers(api_token: str) -> dict:
    return {
        "Authorization": f"Bearer {api_token}",
        "X-Version": "1",
        "Content-Type": "application/json",
    }


@register_node("productboard.list_features")
async def productboard_list_features(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List features from Productboard.

    config:
      api_token  — Productboard API token (required)
      status     — filter by status (optional)
      parent_id  — filter by parent feature ID (optional)
      page_limit — results per page (optional, default 100)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required for productboard.list_features")

    params: dict = {"pageLimit": merged.get("page_limit", 100)}
    if merged.get("status"):
        params["status.name"] = merged["status"]
    if merged.get("parent_id"):
        params["parentId"] = merged["parent_id"]

    async with httpx.AsyncClient(base_url=PRODUCTBOARD_BASE, timeout=30) as client:
        r = await client.get("/features", headers=_productboard_headers(api_token), params=params)
        r.raise_for_status()
        data = r.json()

    features = data.get("data", [])
    log.info("productboard.list_features", count=len(features))
    return {"features": features, "count": len(features), "links": data.get("links")}


@register_node("productboard.get_feature")
async def productboard_get_feature(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Productboard feature by ID.

    config:
      api_token  — Productboard API token (required)
      feature_id — feature ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    feature_id = merged.get("feature_id")
    if not api_token or not feature_id:
        raise ValueError("api_token and feature_id are required")

    async with httpx.AsyncClient(base_url=PRODUCTBOARD_BASE, timeout=30) as client:
        r = await client.get(f"/features/{feature_id}", headers=_productboard_headers(api_token))
        r.raise_for_status()
        data = r.json()

    feature = data.get("data", data)
    log.info("productboard.get_feature", feature_id=feature_id)
    return {"feature": feature, "feature_id": feature_id}


@register_node("productboard.create_feature")
async def productboard_create_feature(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new feature in Productboard.

    config:
      api_token    — Productboard API token (required)
      name         — feature name (required)
      description  — feature description (optional)
      status       — initial status name (optional)
      parent_id    — parent feature ID (optional)
      product_id   — product ID to assign to (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required for productboard.create_feature")

    payload: dict = {"data": {"name": merged.get("name", "")}}
    if merged.get("description"):
        payload["data"]["description"] = merged["description"]
    if merged.get("status"):
        payload["data"]["status"] = {"name": merged["status"]}
    if merged.get("parent_id"):
        payload["data"]["parent"] = {"id": merged["parent_id"]}
    if merged.get("product_id"):
        payload["data"]["product"] = {"id": merged["product_id"]}

    async with httpx.AsyncClient(base_url=PRODUCTBOARD_BASE, timeout=30) as client:
        r = await client.post("/features", headers=_productboard_headers(api_token), json=payload)
        r.raise_for_status()
        data = r.json()

    feature = data.get("data", data)
    feature_id = feature.get("id")
    log.info("productboard.create_feature", feature_id=feature_id)
    return {"feature": feature, "feature_id": feature_id}


@register_node("productboard.list_notes")
async def productboard_list_notes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customer notes/feedback in Productboard.

    config:
      api_token  — Productboard API token (required)
      page_limit — results per page (optional, default 100)
      user_email — filter by user email (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required for productboard.list_notes")

    params: dict = {"pageLimit": merged.get("page_limit", 100)}
    if merged.get("user_email"):
        params["user.email"] = merged["user_email"]

    async with httpx.AsyncClient(base_url=PRODUCTBOARD_BASE, timeout=30) as client:
        r = await client.get("/notes", headers=_productboard_headers(api_token), params=params)
        r.raise_for_status()
        data = r.json()

    notes = data.get("data", [])
    log.info("productboard.list_notes", count=len(notes))
    return {"notes": notes, "count": len(notes), "links": data.get("links")}


@register_node("productboard.create_note")
async def productboard_create_note(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a customer note/feedback in Productboard.

    config:
      api_token    — Productboard API token (required)
      title        — note title (required)
      content      — note text content (required)
      user_email   — email of the user who provided feedback (optional)
      feature_ids  — list of feature IDs to link (optional)
      source_url   — URL of original feedback source (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    if not api_token:
        raise ValueError("api_token is required for productboard.create_note")

    note_data: dict = {
        "title": merged.get("title", ""),
        "content": merged.get("content", ""),
    }
    if merged.get("user_email"):
        note_data["user"] = {"email": merged["user_email"]}
    if merged.get("feature_ids"):
        note_data["features"] = {"data": [{"id": fid} for fid in merged["feature_ids"]]}
    if merged.get("source_url"):
        note_data["source"] = {"origin": merged["source_url"]}

    payload = {"data": note_data}

    async with httpx.AsyncClient(base_url=PRODUCTBOARD_BASE, timeout=30) as client:
        r = await client.post("/notes", headers=_productboard_headers(api_token), json=payload)
        r.raise_for_status()
        data = r.json()

    note = data.get("data", data)
    note_id = note.get("id")
    log.info("productboard.create_note", note_id=note_id)
    return {"note": note, "note_id": note_id}
