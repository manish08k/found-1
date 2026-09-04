"""
LinkedIn API v2 integration.

Credential fields:
  - access_token: LinkedIn OAuth2 access token (Authorization: Bearer)

Auth: Bearer token
Base URL: https://api.linkedin.com/v2
LinkedIn-Version: 202312
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

LINKEDIN_BASE_URL = "https://api.linkedin.com/v2"
LINKEDIN_VERSION = "202312"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("LinkedIn credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=LINKEDIN_BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"LinkedIn API error {r.status_code}: {detail}")
    if r.status_code == 204:
        return {"ok": True}
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("linkedin.get_profile")
async def linkedin_get_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me — get the authenticated user's profile."""
    fields = config.get("fields") or input_data.get("fields")
    params: dict = {}
    if fields:
        params["fields"] = fields if isinstance(fields, str) else ",".join(fields)
    async with await _client(credential_id, db) as client:
        r = await client.get("/me", params=params)
    return _check(r)


@register_node("linkedin.list_connections")
async def linkedin_list_connections(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /connections — list first-degree connections."""
    params: dict = {"q": "viewer"}
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = min(int(count), 500)
    start = config.get("start") or input_data.get("start")
    if start:
        params["start"] = int(start)
    async with await _client(credential_id, db) as client:
        r = await client.get("/connections", params=params)
    return _check(r)


@register_node("linkedin.create_post")
async def linkedin_create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /ugcPosts — create a text post as the authenticated user."""
    text = config.get("text") or input_data.get("text")
    author = config.get("author") or input_data.get("author")
    if not text:
        raise ValueError("linkedin.create_post requires 'text'")
    async with await _client(credential_id, db) as client:
        if not author:
            me = await client.get("/me")
            author = f"urn:li:person:{_check(me)['id']}"
        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": config.get("visibility") or input_data.get("visibility") or "PUBLIC"
            },
        }
        r = await client.post("/ugcPosts", json=body)
    return _check(r)


@register_node("linkedin.list_posts")
async def linkedin_list_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /ugcPosts — list posts by the authenticated user."""
    params: dict = {"q": "authors"}
    async with await _client(credential_id, db) as client:
        me = await client.get("/me")
        author_urn = f"urn:li:person:{_check(me)['id']}"
        params["authors"] = f"List({author_urn})"
        count = config.get("count") or input_data.get("count")
        if count:
            params["count"] = min(int(count), 50)
        r = await client.get("/ugcPosts", params=params)
    return _check(r)


@register_node("linkedin.get_organization")
async def linkedin_get_organization(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /organizations/{id} — get an organization's profile."""
    org_id = config.get("org_id") or input_data.get("org_id")
    if not org_id:
        raise ValueError("linkedin.get_organization requires 'org_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/organizations/{org_id}")
    return _check(r)


@register_node("linkedin.list_organizations")
async def linkedin_list_organizations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /organizationAcls — list organizations the user administers."""
    params: dict = {"q": "roleAssignee"}
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = min(int(count), 50)
    async with await _client(credential_id, db) as client:
        r = await client.get("/organizationAcls", params=params)
    return _check(r)


@register_node("linkedin.list_organization_posts")
async def linkedin_list_organization_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /ugcPosts — list posts by an organization."""
    org_id = config.get("org_id") or input_data.get("org_id")
    if not org_id:
        raise ValueError("linkedin.list_organization_posts requires 'org_id'")
    params: dict = {
        "q": "authors",
        "authors": f"List(urn:li:organization:{org_id})",
    }
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = min(int(count), 50)
    async with await _client(credential_id, db) as client:
        r = await client.get("/ugcPosts", params=params)
    return _check(r)


@register_node("linkedin.create_organization_post")
async def linkedin_create_organization_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /ugcPosts — create a post as an organization."""
    org_id = config.get("org_id") or input_data.get("org_id")
    text = config.get("text") or input_data.get("text")
    if not org_id or not text:
        raise ValueError("linkedin.create_organization_post requires 'org_id' and 'text'")
    body = {
        "author": f"urn:li:organization:{org_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": config.get("visibility") or input_data.get("visibility") or "PUBLIC"
        },
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/ugcPosts", json=body)
    return _check(r)


@register_node("linkedin.list_jobs")
async def linkedin_list_jobs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /jobSearch — search for jobs on LinkedIn."""
    params: dict = {}
    keywords = config.get("keywords") or input_data.get("keywords")
    if keywords:
        params["keywords"] = keywords
    location = config.get("location") or input_data.get("location")
    if location:
        params["locationFallback"] = location
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = min(int(count), 50)
    async with await _client(credential_id, db) as client:
        r = await client.get("/jobSearch", params=params)
    return _check(r)


@register_node("linkedin.list_followers")
async def linkedin_list_followers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /networkSizes — get follower count for a person or organization."""
    entity_urn = config.get("entity_urn") or input_data.get("entity_urn")
    if not entity_urn:
        raise ValueError("linkedin.list_followers requires 'entity_urn'")
    params = {"edgeType": "CompanyFollowedByMember"}
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/networkSizes/{urllib_encode(entity_urn)}", params=params)
    return _check(r)


def urllib_encode(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s, safe="")


async def test_connection(credential_id: str, db) -> dict:
    """Test LinkedIn connection by fetching the current user's profile."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    _check(r)
    return {"ok": True}
