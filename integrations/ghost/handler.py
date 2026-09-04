"""
Ghost CMS integration.

Credential fields:
  - admin_url: https://myblog.ghost.io
  - admin_api_key: Ghost Admin API key in format id:secret

Auth: Ghost Admin API key passed as Authorization header
Admin API Base: {admin_url}/ghost/api/admin
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    admin_url = creds.get("admin_url", "").rstrip("/")
    admin_api_key = creds.get("admin_api_key")
    if not admin_url:
        raise ValueError("Ghost credential is missing 'admin_url'")
    if not admin_api_key:
        raise ValueError("Ghost credential is missing 'admin_api_key'")
    base_url = f"{admin_url}/ghost/api/admin"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Ghost {admin_api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Ghost API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching site info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/site/")
    data = _check(r)
    site = data.get("site", {})
    return {"ok": True, "title": site.get("title"), "version": site.get("version")}


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

@register_node("ghost.list_posts")
async def ghost_list_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /posts — list posts."""
    params = {}
    for key in ("limit", "page", "filter", "order", "include", "fields"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/posts/", params=params)
    return _check(r)


@register_node("ghost.get_post")
async def ghost_get_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /posts/{id} — fetch a single post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("ghost.get_post requires 'post_id'")
    params = {}
    include = config.get("include") or input_data.get("include")
    if include:
        params["include"] = include
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/posts/{post_id}/", params=params)
    return _check(r)


@register_node("ghost.create_post")
async def ghost_create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /posts — create a new post."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("ghost.create_post requires 'title'")
    post: dict = {"title": title}
    for field in ("lexical", "html", "mobiledoc", "status", "slug", "tags", "authors",
                  "excerpt", "feature_image", "featured", "visibility"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            post[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/posts/", json={"posts": [post]})
    return _check(r)


@register_node("ghost.update_post")
async def ghost_update_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /posts/{id} — update an existing post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    updated_at = config.get("updated_at") or input_data.get("updated_at")
    if not post_id:
        raise ValueError("ghost.update_post requires 'post_id'")
    if not updated_at:
        raise ValueError("ghost.update_post requires 'updated_at' (for conflict detection)")
    post: dict = {"updated_at": updated_at}
    for field in ("title", "lexical", "html", "mobiledoc", "status", "slug", "tags",
                  "authors", "excerpt", "feature_image", "featured", "visibility"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            post[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/posts/{post_id}/", json={"posts": [post]})
    return _check(r)


@register_node("ghost.delete_post")
async def ghost_delete_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /posts/{id} — delete a post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("ghost.delete_post requires 'post_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/posts/{post_id}/")
    if r.status_code == 204:
        return {"deleted": True, "post_id": post_id}
    return _check(r)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@register_node("ghost.list_pages")
async def ghost_list_pages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /pages — list pages."""
    params = {}
    for key in ("limit", "page", "filter", "order", "include"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/pages/", params=params)
    return _check(r)


@register_node("ghost.create_page")
async def ghost_create_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /pages — create a new page."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("ghost.create_page requires 'title'")
    page: dict = {"title": title}
    for field in ("lexical", "html", "mobiledoc", "status", "slug", "excerpt",
                  "feature_image", "featured", "visibility"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            page[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/pages/", json={"pages": [page]})
    return _check(r)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@register_node("ghost.list_tags")
async def ghost_list_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tags — list tags."""
    params = {}
    for key in ("limit", "page", "filter", "order", "include"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/tags/", params=params)
    return _check(r)


@register_node("ghost.create_tag")
async def ghost_create_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tags — create a new tag."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("ghost.create_tag requires 'name'")
    tag: dict = {"name": name}
    for field in ("slug", "description", "feature_image", "visibility", "accent_color"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            tag[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/tags/", json={"tags": [tag]})
    return _check(r)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@register_node("ghost.list_members")
async def ghost_list_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /members — list members."""
    params = {}
    for key in ("limit", "page", "filter", "order", "include"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/members/", params=params)
    return _check(r)


@register_node("ghost.create_member")
async def ghost_create_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /members — create a new member."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("ghost.create_member requires 'email'")
    member: dict = {"email": email}
    for field in ("name", "note", "labels", "newsletters", "subscribed"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            member[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/members/", json={"members": [member]})
    return _check(r)


@register_node("ghost.update_member")
async def ghost_update_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /members/{id} — update a member."""
    member_id = config.get("member_id") or input_data.get("member_id")
    if not member_id:
        raise ValueError("ghost.update_member requires 'member_id'")
    member: dict = {}
    for field in ("name", "note", "labels", "newsletters", "subscribed", "email"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            member[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/members/{member_id}/", json={"members": [member]})
    return _check(r)


# ---------------------------------------------------------------------------
# Newsletters
# ---------------------------------------------------------------------------

@register_node("ghost.list_newsletters")
async def ghost_list_newsletters(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /newsletters — list newsletters."""
    params = {}
    for key in ("limit", "page", "filter"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/newsletters/", params=params)
    return _check(r)
