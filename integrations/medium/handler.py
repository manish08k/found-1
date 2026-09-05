"""
Medium blogging platform integration.

Provides post creation, user info retrieval, and publication management
via the Medium API v1.

Credential fields:
  - integration_token : Medium integration token (Settings > Integration tokens)

Auth: Authorization: Bearer <integration_token> header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.medium.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("integration_token")
    if not token:
        raise ValueError("Medium credential missing 'integration_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Medium API error {r.status_code}: {detail}")


@register_node("medium.get_user")
async def medium_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get the authenticated Medium user's profile."""
    log.info("medium.get_user")
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
        _raise_for_status(r)
        data = r.json()

    return {"user": data.get("data", {})}


@register_node("medium.list_publications")
async def medium_list_publications(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List publications the authenticated user contributes to."""
    log.info("medium.list_publications")
    async with await _client(credential_id, db) as client:
        # First get user id
        me_r = await client.get("/me")
        _raise_for_status(me_r)
        user_id = me_r.json().get("data", {}).get("id")
        if not user_id:
            raise ValueError("Could not retrieve Medium user ID")

        r = await client.get(f"/users/{user_id}/publications")
        _raise_for_status(r)
        data = r.json()

    return {"publications": data.get("data", [])}


@register_node("medium.create_post")
async def medium_create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new Medium post under the authenticated user."""
    title = config.get("title") or input_data.get("title")
    content = config.get("content") or input_data.get("content", "")
    content_format = config.get("content_format") or input_data.get("content_format", "markdown")
    publish_status = config.get("publish_status") or input_data.get("publish_status", "draft")
    tags = config.get("tags") or input_data.get("tags", [])
    canonical_url = config.get("canonical_url") or input_data.get("canonical_url", "")

    if not title:
        raise ValueError("medium.create_post requires 'title'")

    payload: dict = {
        "title": title,
        "contentFormat": content_format,
        "content": content,
        "publishStatus": publish_status,
    }
    if tags:
        payload["tags"] = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",") if t.strip()]
    if canonical_url:
        payload["canonicalUrl"] = canonical_url

    log.info("medium.create_post", title=title, publish_status=publish_status)
    async with await _client(credential_id, db) as client:
        # Get user id first
        me_r = await client.get("/me")
        _raise_for_status(me_r)
        user_id = me_r.json().get("data", {}).get("id")
        if not user_id:
            raise ValueError("Could not retrieve Medium user ID")

        r = await client.post(f"/users/{user_id}/posts", json=payload)
        _raise_for_status(r)
        data = r.json()

    post = data.get("data", {})
    return {"post": post, "post_id": post.get("id"), "url": post.get("url")}


@register_node("medium.create_publication_post")
async def medium_create_publication_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new Medium post under a specific publication."""
    publication_id = config.get("publication_id") or input_data.get("publication_id")
    title = config.get("title") or input_data.get("title")
    content = config.get("content") or input_data.get("content", "")
    content_format = config.get("content_format") or input_data.get("content_format", "markdown")
    publish_status = config.get("publish_status") or input_data.get("publish_status", "draft")
    tags = config.get("tags") or input_data.get("tags", [])
    canonical_url = config.get("canonical_url") or input_data.get("canonical_url", "")

    if not publication_id:
        raise ValueError("medium.create_publication_post requires 'publication_id'")
    if not title:
        raise ValueError("medium.create_publication_post requires 'title'")

    payload: dict = {
        "title": title,
        "contentFormat": content_format,
        "content": content,
        "publishStatus": publish_status,
    }
    if tags:
        payload["tags"] = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",") if t.strip()]
    if canonical_url:
        payload["canonicalUrl"] = canonical_url

    log.info("medium.create_publication_post", publication_id=publication_id, title=title)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/publications/{publication_id}/posts", json=payload)
        _raise_for_status(r)
        data = r.json()

    post = data.get("data", {})
    return {"post": post, "post_id": post.get("id"), "url": post.get("url")}
