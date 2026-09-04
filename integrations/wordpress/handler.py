"""
WordPress integration.

Credential fields:
  - site_url: https://myblog.com
  - username: WordPress username
  - app_password: WordPress Application Password

Auth: HTTP Basic with username:app_password
Base URL: {site_url}/wp-json/wp/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    site_url = creds.get("site_url", "").rstrip("/")
    username = creds.get("username")
    app_password = creds.get("app_password")
    if not site_url:
        raise ValueError("WordPress credential is missing 'site_url'")
    if not username:
        raise ValueError("WordPress credential is missing 'username'")
    if not app_password:
        raise ValueError("WordPress credential is missing 'app_password'")
    base_url = f"{site_url}/wp-json/wp/v2"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(username, app_password),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"WordPress API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching site info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me")
    data = _check(r)
    return {"ok": True, "user": data.get("name"), "id": data.get("id")}


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

@register_node("wordpress.list_posts")
async def wordpress_list_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /posts — list posts with optional filters."""
    params = {}
    for key in ("per_page", "page", "status", "author", "search", "categories", "tags"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/posts", params=params)
    return {"posts": _check(r)}


@register_node("wordpress.get_post")
async def wordpress_get_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /posts/{id} — fetch a single post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("wordpress.get_post requires 'post_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/posts/{post_id}")
    return _check(r)


@register_node("wordpress.create_post")
async def wordpress_create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /posts — create a new post."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("wordpress.create_post requires 'title'")
    body: dict = {"title": title}
    for field in ("content", "excerpt", "status", "author", "categories", "tags", "slug", "comment_status"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/posts", json=body)
    return _check(r)


@register_node("wordpress.update_post")
async def wordpress_update_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /posts/{id} — update an existing post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("wordpress.update_post requires 'post_id'")
    body: dict = {}
    for field in ("title", "content", "excerpt", "status", "author", "categories", "tags", "slug"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/posts/{post_id}", json=body)
    return _check(r)


@register_node("wordpress.delete_post")
async def wordpress_delete_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /posts/{id} — delete a post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("wordpress.delete_post requires 'post_id'")
    force = config.get("force", input_data.get("force", False))
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/posts/{post_id}", params={"force": force})
    return _check(r)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@register_node("wordpress.list_pages")
async def wordpress_list_pages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /pages — list pages."""
    params = {}
    for key in ("per_page", "page", "status", "search"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/pages", params=params)
    return {"pages": _check(r)}


@register_node("wordpress.create_page")
async def wordpress_create_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /pages — create a new page."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("wordpress.create_page requires 'title'")
    body: dict = {"title": title}
    for field in ("content", "excerpt", "status", "slug", "parent", "menu_order"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/pages", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@register_node("wordpress.list_categories")
async def wordpress_list_categories(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /categories — list categories."""
    params = {}
    for key in ("per_page", "page", "search", "hide_empty"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/categories", params=params)
    return {"categories": _check(r)}


@register_node("wordpress.create_category")
async def wordpress_create_category(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /categories — create a new category."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("wordpress.create_category requires 'name'")
    body: dict = {"name": name}
    for field in ("description", "slug", "parent"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/categories", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@register_node("wordpress.list_tags")
async def wordpress_list_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tags — list tags."""
    params = {}
    for key in ("per_page", "page", "search", "hide_empty"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/tags", params=params)
    return {"tags": _check(r)}


@register_node("wordpress.create_tag")
async def wordpress_create_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tags — create a new tag."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("wordpress.create_tag requires 'name'")
    body: dict = {"name": name}
    for field in ("description", "slug"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/tags", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

@register_node("wordpress.list_media")
async def wordpress_list_media(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /media — list media library items."""
    params = {}
    for key in ("per_page", "page", "search", "media_type", "mime_type"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/media", params=params)
    return {"media": _check(r)}


@register_node("wordpress.upload_media")
async def wordpress_upload_media(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /media — upload a media file via URL or base64 content."""
    file_url = config.get("file_url") or input_data.get("file_url")
    file_content = config.get("file_content") or input_data.get("file_content")
    filename = config.get("filename") or input_data.get("filename", "upload.bin")
    mime_type = config.get("mime_type") or input_data.get("mime_type", "application/octet-stream")
    if not file_url and not file_content:
        raise ValueError("wordpress.upload_media requires 'file_url' or 'file_content'")
    creds = await get_credential_data(credential_id, db)
    site_url = creds.get("site_url", "").rstrip("/")
    username = creds.get("username")
    app_password = creds.get("app_password")
    base_url = f"{site_url}/wp-json/wp/v2"
    if file_url:
        async with httpx.AsyncClient() as fetch_client:
            fr = await fetch_client.get(file_url)
        file_content_bytes = fr.content
    else:
        import base64
        file_content_bytes = base64.b64decode(file_content)
    async with httpx.AsyncClient(
        base_url=base_url,
        auth=(username, app_password),
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": mime_type},
        timeout=60.0,
    ) as client:
        r = await client.post("/media", content=file_content_bytes)
    return _check(r)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@register_node("wordpress.list_comments")
async def wordpress_list_comments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /comments — list comments."""
    params = {}
    for key in ("per_page", "page", "post", "status", "author_email"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/comments", params=params)
    return {"comments": _check(r)}


@register_node("wordpress.create_comment")
async def wordpress_create_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /comments — create a new comment."""
    post = config.get("post") or input_data.get("post")
    content = config.get("content") or input_data.get("content")
    if not post or not content:
        raise ValueError("wordpress.create_comment requires 'post' and 'content'")
    body: dict = {"post": post, "content": content}
    for field in ("author_name", "author_email", "author_url", "parent"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/comments", json=body)
    return _check(r)
