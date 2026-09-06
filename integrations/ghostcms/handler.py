"""Ghost CMS publishing platform (admin API) — handler for ghostcms integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _ghost_headers(merged: dict) -> tuple[dict, str]:
    """Build Ghost Admin API auth headers and base URL."""
    import jwt as pyjwt
    import time

    admin_api_key = merged.get("api_key") or merged.get("admin_api_key") or ""
    site_url = merged.get("site_url") or merged.get("url") or ""
    if not admin_api_key or ":" not in admin_api_key:
        raise ValueError("api_key must be in format 'id:secret' for Ghost Admin API")
    if not site_url:
        raise ValueError("site_url is required for Ghost CMS")

    kid, secret = admin_api_key.split(":", 1)
    iat = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
    token = pyjwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
    base = f"https://{site_url.rstrip('/')}/ghost/api/admin"
    return {"Authorization": f"Ghost {token}", "Content-Type": "application/json"}, base


@register_node("ghostcms.list_posts")
async def ghostcms_list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List posts from Ghost CMS.

    config/input_data:
      api_key  -- Ghost Admin API key in 'id:secret' format (required)
      site_url -- Ghost site domain, e.g. 'myblog.com' (required)
    """
    merged = {**config, **input_data}
    headers, base = _ghost_headers(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/posts/", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("ghostcms.list_posts", count=len(data.get("posts", [])))
    return {"data": data}


@register_node("ghostcms.create_post")
async def ghostcms_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a post in Ghost CMS.

    config/input_data:
      api_key  -- Ghost Admin API key (required)
      site_url -- Ghost site domain (required)
      title    -- Post title (required)
      html     -- Post HTML body (optional)
      status   -- 'draft' or 'published' (default 'draft')
    """
    merged = {**config, **input_data}
    headers, base = _ghost_headers(merged)
    title = merged.get("title") or ""
    if not title:
        raise ValueError("title is required for ghostcms.create_post")
    post = {"title": title}
    if merged.get("html"):
        post["html"] = merged["html"]
    post["status"] = merged.get("status", "draft")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base}/posts/", headers=headers, json={"posts": [post]})
        r.raise_for_status()
        data = r.json()
    log.info("ghostcms.create_post", title=title)
    return {"data": data}


@register_node("ghostcms.get_post")
async def ghostcms_get_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a post by ID from Ghost CMS.

    config/input_data:
      api_key  -- Ghost Admin API key (required)
      site_url -- Ghost site domain (required)
      post_id  -- Post ID (required)
    """
    merged = {**config, **input_data}
    headers, base = _ghost_headers(merged)
    post_id = merged.get("post_id") or ""
    if not post_id:
        raise ValueError("post_id is required for ghostcms.get_post")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/posts/{post_id}/", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("ghostcms.get_post", post_id=post_id)
    return {"data": data}


@register_node("ghostcms.update_post")
async def ghostcms_update_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update a post in Ghost CMS.

    config/input_data:
      api_key    -- Ghost Admin API key (required)
      site_url   -- Ghost site domain (required)
      post_id    -- Post ID (required)
      updated_at -- Current updated_at timestamp (required by Ghost)
      title      -- New title (optional)
      html       -- New HTML body (optional)
      status     -- New status (optional)
    """
    merged = {**config, **input_data}
    headers, base = _ghost_headers(merged)
    post_id = merged.get("post_id") or ""
    if not post_id:
        raise ValueError("post_id is required for ghostcms.update_post")
    post = {"updated_at": merged.get("updated_at", "")}
    for key in ("title", "html", "status", "slug", "featured"):
        if merged.get(key) is not None:
            post[key] = merged[key]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{base}/posts/{post_id}/", headers=headers, json={"posts": [post]})
        r.raise_for_status()
        data = r.json()
    log.info("ghostcms.update_post", post_id=post_id)
    return {"data": data}
