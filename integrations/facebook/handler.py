"""
Facebook Graph API integration.

Provides page post management, insights analytics, and photo uploads via the
Facebook Graph API v17.0.

Credential fields:
  - access_token : Facebook Page or User access token

Base URL: https://graph.facebook.com/v17.0/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://graph.facebook.com/v17.0"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Facebook API error {r.status_code}: {detail}")

    # Facebook embeds errors in 200 responses sometimes
    try:
        body = r.json()
        if "error" in body:
            err = body["error"]
            raise ValueError(
                f"Facebook API error {err.get('code')}: {err.get('message')}"
            )
    except (ValueError, KeyError):
        pass


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token", "").strip()
    if not access_token:
        raise ValueError("Facebook credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        params={"access_token": access_token},
        timeout=30.0,
    )


@register_node("facebook.get_page_posts")
async def get_page_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve posts published on a Facebook Page.

    Config / input keys:
      - page_id (str)  : Required. Facebook Page ID or slug.
      - limit   (int)  : Number of posts to return (1-100). Default 10.
      - fields  (str)  : Comma-separated Graph API fields.
                         Default "id,message,created_time,story,full_picture".
      - since   (str)  : Unix timestamp or ISO date — filter posts after this.
      - until   (str)  : Unix timestamp or ISO date — filter posts before this.

    Returns:
      { "posts": [...], "total": int, "page_id": str, "paging": dict }
    """
    page_id = config.get("page_id") or input_data.get("page_id")
    if not page_id:
        raise ValueError("facebook.get_page_posts requires 'page_id'")

    limit = min(int(config.get("limit") or input_data.get("limit", 10)), 100)
    fields = (
        config.get("fields")
        or input_data.get("fields")
        or "id,message,created_time,story,full_picture,permalink_url"
    )

    params: dict = {"fields": fields, "limit": limit}
    since = config.get("since") or input_data.get("since")
    until = config.get("until") or input_data.get("until")
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    log.info("facebook.get_page_posts", page_id=page_id, limit=limit)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{page_id}/posts", params=params)
        _raise_for_status(r)
        data = r.json()

    posts = data.get("data", [])
    return {
        "posts": posts,
        "total": len(posts),
        "page_id": page_id,
        "paging": data.get("paging", {}),
    }


@register_node("facebook.create_post")
async def create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Publish a text or link post to a Facebook Page.

    Config / input keys:
      - page_id     (str)  : Required. Target Page ID.
      - message     (str)  : Post text content.
      - link        (str)  : URL to share as a link preview.
      - published   (bool) : Publish immediately (True) or save as draft.
                             Default True.
      - scheduled_publish_time (int): Unix timestamp for scheduled publishing.

    Returns:
      { "post_id": str, "page_id": str, "published": bool }
    """
    page_id = config.get("page_id") or input_data.get("page_id")
    message = config.get("message") or input_data.get("message", "")
    link = config.get("link") or input_data.get("link")

    if not page_id:
        raise ValueError("facebook.create_post requires 'page_id'")
    if not message and not link:
        raise ValueError("facebook.create_post requires 'message' or 'link'")

    published = str(config.get("published") or input_data.get("published", "true")).lower() not in ("false", "0", "no")
    scheduled_time = config.get("scheduled_publish_time") or input_data.get("scheduled_publish_time")

    payload: dict = {}
    if message:
        payload["message"] = message
    if link:
        payload["link"] = link
    if not published:
        payload["published"] = False
    if scheduled_time:
        payload["scheduled_publish_time"] = scheduled_time
        payload["published"] = False

    log.info("facebook.create_post", page_id=page_id, has_link=bool(link))

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{page_id}/feed", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "post_id": data.get("id"),
        "page_id": page_id,
        "published": published and not scheduled_time,
        "raw": data,
    }


@register_node("facebook.get_page_insights")
async def get_page_insights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve analytics metrics for a Facebook Page.

    Config / input keys:
      - page_id (str)        : Required. Page ID.
      - metrics (str|list)   : Comma-separated metric names or list.
                               Default "page_impressions,page_reach,page_fans,
                               page_views_total,page_post_engagements".
      - period  (str)        : Aggregation period: "day", "week", "days_28",
                               "month". Default "day".
      - since   (str)        : Start date (YYYY-MM-DD or Unix ts).
      - until   (str)        : End date (YYYY-MM-DD or Unix ts).

    Returns:
      { "page_id": str, "insights": [...], "period": str }
    """
    page_id = config.get("page_id") or input_data.get("page_id")
    if not page_id:
        raise ValueError("facebook.get_page_insights requires 'page_id'")

    default_metrics = (
        "page_impressions,page_reach,page_fans,"
        "page_views_total,page_post_engagements"
    )
    metrics_raw = config.get("metrics") or input_data.get("metrics") or default_metrics
    if isinstance(metrics_raw, list):
        metrics_raw = ",".join(metrics_raw)

    period = config.get("period") or input_data.get("period", "day")

    params: dict = {"metric": metrics_raw, "period": period}
    since = config.get("since") or input_data.get("since")
    until = config.get("until") or input_data.get("until")
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    log.info("facebook.get_page_insights", page_id=page_id, period=period)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{page_id}/insights", params=params)
        _raise_for_status(r)
        data = r.json()

    insights = data.get("data", [])
    # Flatten for convenience
    flat: dict = {}
    for metric in insights:
        name = metric.get("name")
        values = metric.get("values", [])
        flat[name] = values[-1].get("value") if values else None

    return {
        "page_id": page_id,
        "insights": insights,
        "summary": flat,
        "period": period,
        "paging": data.get("paging", {}),
    }


@register_node("facebook.upload_photo")
async def upload_photo(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Upload a photo to a Facebook Page from a URL or base64 data.

    Config / input keys:
      - page_id     (str)  : Required. Target Page ID.
      - url         (str)  : Publicly accessible image URL (preferred).
      - caption     (str)  : Photo caption text.
      - published   (bool) : Publish immediately. Default True.
      - album_path  (str)  : Album endpoint to upload to.
                             Default "photos" (page's wall photos).

    Returns:
      { "photo_id": str, "post_id": str, "page_id": str }
    """
    page_id = config.get("page_id") or input_data.get("page_id")
    url = config.get("url") or input_data.get("url")
    caption = config.get("caption") or input_data.get("caption", "")
    published = str(config.get("published") or input_data.get("published", "true")).lower() not in ("false", "0", "no")
    album_path = config.get("album_path") or input_data.get("album_path", "photos")

    if not page_id:
        raise ValueError("facebook.upload_photo requires 'page_id'")
    if not url:
        raise ValueError("facebook.upload_photo requires 'url'")

    payload: dict = {
        "url": url,
        "published": published,
    }
    if caption:
        payload["caption"] = caption

    log.info("facebook.upload_photo", page_id=page_id, album_path=album_path)

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{page_id}/{album_path}", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "photo_id": data.get("id"),
        "post_id": data.get("post_id"),
        "page_id": page_id,
        "published": published,
        "raw": data,
    }
