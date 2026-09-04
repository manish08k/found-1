"""
Reddit integration.

Credential fields:
  - access_token: Reddit OAuth2 access token

Auth: Authorization: Bearer {access_token}
Base URL: https://oauth.reddit.com
Note: Reddit requires a User-Agent header
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

REDDIT_BASE_URL = "https://oauth.reddit.com"
REDDIT_USER_AGENT = "FoundAutomationPlatform/1.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Reddit credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=REDDIT_BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": REDDIT_USER_AGENT,
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
        raise ValueError(f"Reddit API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching the current user's identity."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/api/v1/me")
    data = _check(r)
    return {"ok": True, "username": data.get("name"), "id": data.get("id")}


# ---------------------------------------------------------------------------
# Subreddits
# ---------------------------------------------------------------------------

@register_node("reddit.get_subreddit")
async def reddit_get_subreddit(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /r/{subreddit}/about — get subreddit info."""
    subreddit = config.get("subreddit") or input_data.get("subreddit")
    if not subreddit:
        raise ValueError("reddit.get_subreddit requires 'subreddit'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/r/{subreddit}/about.json")
    return _check(r)


# ---------------------------------------------------------------------------
# Posts (Links)
# ---------------------------------------------------------------------------

@register_node("reddit.list_posts")
async def reddit_list_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /r/{subreddit}/{sort} — list posts in a subreddit."""
    subreddit = config.get("subreddit") or input_data.get("subreddit")
    if not subreddit:
        raise ValueError("reddit.list_posts requires 'subreddit'")
    sort = config.get("sort", input_data.get("sort", "hot"))
    params = {}
    for key in ("limit", "after", "before", "t"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/r/{subreddit}/{sort}.json", params=params)
    return _check(r)


@register_node("reddit.get_post")
async def reddit_get_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /by_id/{fullname} — get a post by fullname (e.g. t3_abc123)."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("reddit.get_post requires 'post_id'")
    fullname = post_id if post_id.startswith("t3_") else f"t3_{post_id}"
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/by_id/{fullname}.json")
    return _check(r)


@register_node("reddit.create_post")
async def reddit_create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/submit — submit a new post."""
    subreddit = config.get("subreddit") or input_data.get("subreddit")
    title = config.get("title") or input_data.get("title")
    kind = config.get("kind", input_data.get("kind", "self"))
    if not subreddit or not title:
        raise ValueError("reddit.create_post requires 'subreddit' and 'title'")
    data: dict = {"sr": subreddit, "title": title, "kind": kind, "api_type": "json"}
    if kind == "link":
        url = config.get("url") or input_data.get("url")
        if not url:
            raise ValueError("reddit.create_post with kind='link' requires 'url'")
        data["url"] = url
    else:
        text = config.get("text") or input_data.get("text", "")
        data["text"] = text
    for field in ("nsfw", "spoiler", "flair_id", "flair_text"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            data[field] = v
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    async with httpx.AsyncClient(
        base_url=REDDIT_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": REDDIT_USER_AGENT},
        timeout=30.0,
    ) as client:
        r = await client.post("/api/submit", data=data)
    return _check(r)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@register_node("reddit.get_comments")
async def reddit_get_comments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /comments/{article} — get comments for a post."""
    article_id = config.get("article_id") or input_data.get("article_id")
    subreddit = config.get("subreddit") or input_data.get("subreddit")
    if not article_id:
        raise ValueError("reddit.get_comments requires 'article_id'")
    params = {}
    for key in ("limit", "depth", "sort"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    path = f"/r/{subreddit}/comments/{article_id}.json" if subreddit else f"/comments/{article_id}.json"
    async with await _client(credential_id, db) as client:
        r = await client.get(path, params=params)
    return _check(r)


@register_node("reddit.create_comment")
async def reddit_create_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/comment — post a comment on a post or reply to a comment."""
    parent_id = config.get("parent_id") or input_data.get("parent_id")
    text = config.get("text") or input_data.get("text")
    if not parent_id or not text:
        raise ValueError("reddit.create_comment requires 'parent_id' and 'text'")
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    async with httpx.AsyncClient(
        base_url=REDDIT_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": REDDIT_USER_AGENT},
        timeout=30.0,
    ) as client:
        r = await client.post("/api/comment", data={"parent": parent_id, "text": text, "api_type": "json"})
    return _check(r)


# ---------------------------------------------------------------------------
# Voting & Saving
# ---------------------------------------------------------------------------

@register_node("reddit.vote")
async def reddit_vote(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/vote — vote on a post or comment."""
    fullname = config.get("fullname") or input_data.get("fullname")
    direction = config.get("direction", input_data.get("direction", 1))
    if not fullname:
        raise ValueError("reddit.vote requires 'fullname' (e.g. t3_abc123 or t1_xyz)")
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    async with httpx.AsyncClient(
        base_url=REDDIT_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": REDDIT_USER_AGENT},
        timeout=30.0,
    ) as client:
        r = await client.post("/api/vote", data={"id": fullname, "dir": int(direction)})
    if r.status_code == 200:
        return {"voted": True, "fullname": fullname, "direction": direction}
    return _check(r)


@register_node("reddit.save_post")
async def reddit_save_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/save or /api/unsave — save or unsave a post."""
    fullname = config.get("fullname") or input_data.get("fullname")
    unsave = config.get("unsave", input_data.get("unsave", False))
    if not fullname:
        raise ValueError("reddit.save_post requires 'fullname'")
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    endpoint = "/api/unsave" if unsave else "/api/save"
    async with httpx.AsyncClient(
        base_url=REDDIT_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": REDDIT_USER_AGENT},
        timeout=30.0,
    ) as client:
        r = await client.post(endpoint, data={"id": fullname})
    if r.status_code == 200:
        return {"saved": not unsave, "fullname": fullname}
    return _check(r)


# ---------------------------------------------------------------------------
# Subscriptions & Search
# ---------------------------------------------------------------------------

@register_node("reddit.list_subscriptions")
async def reddit_list_subscriptions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subreddits/mine/subscriber — list subreddits the user subscribes to."""
    params = {}
    for key in ("limit", "after", "before"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/subreddits/mine/subscriber.json", params=params)
    return _check(r)


@register_node("reddit.search")
async def reddit_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /search — search Reddit posts."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("reddit.search requires 'query'")
    params: dict = {"q": query}
    for key in ("sort", "t", "limit", "after", "before", "subreddit", "restrict_sr", "type"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    subreddit = config.get("subreddit") or input_data.get("subreddit")
    path = f"/r/{subreddit}/search.json" if subreddit else "/search.json"
    async with await _client(credential_id, db) as client:
        r = await client.get(path, params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("reddit.get_user")
async def reddit_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /user/{username}/about — get user account info."""
    username = config.get("username") or input_data.get("username")
    if not username:
        raise ValueError("reddit.get_user requires 'username'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/user/{username}/about.json")
    return _check(r)


@register_node("reddit.get_user_posts")
async def reddit_get_user_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /user/{username}/submitted — get posts submitted by a user."""
    username = config.get("username") or input_data.get("username")
    if not username:
        raise ValueError("reddit.get_user_posts requires 'username'")
    params = {}
    for key in ("limit", "after", "before", "sort", "t"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/user/{username}/submitted.json", params=params)
    return _check(r)
