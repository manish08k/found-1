"""
Twitter/X API v2 integration.

Credential fields:
  - bearer_token: App-only Bearer token (for read operations)
  - api_key: API Key / Consumer Key (for OAuth 1.0a write operations)
  - api_secret: API Key Secret / Consumer Secret
  - access_token: OAuth 1.0a Access Token
  - access_token_secret: OAuth 1.0a Access Token Secret

Auth:
  - Read operations: Authorization: Bearer {bearer_token}
  - Write operations: OAuth 1.0a using api_key, api_secret, access_token, access_token_secret
Base URL: https://api.twitter.com/2
"""
import hashlib
import hmac
import time
import urllib.parse
import base64
import os
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

TWITTER_BASE_URL = "https://api.twitter.com/2"


async def _read_client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    bearer_token = creds.get("bearer_token")
    if not bearer_token:
        raise ValueError("Twitter credential is missing 'bearer_token'")
    return httpx.AsyncClient(
        base_url=TWITTER_BASE_URL,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _oauth1_header(method: str, url: str, params: dict,
                   api_key: str, api_secret: str,
                   access_token: str, access_token_secret: str) -> str:
    """Generate OAuth 1.0a Authorization header."""
    oauth_nonce = base64.b64encode(os.urandom(16)).decode().rstrip("=")
    oauth_timestamp = str(int(time.time()))
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": oauth_nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": oauth_timestamp,
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    # Combine all params for signature base
    all_params = {**params, **oauth_params}
    sorted_params = "&".join(
        f"{urllib.parse.quote(str(k), safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    signature_base = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])
    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_token_secret, safe='')}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), signature_base.encode(), hashlib.sha1).digest()  # type: ignore[attr-defined]
    ).decode()
    oauth_params["oauth_signature"] = signature
    header_parts = ", ".join(
        f'{urllib.parse.quote(str(k), safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


async def _write_client(credential_id: str, db, method: str, url: str, body_params: dict = None) -> tuple[httpx.AsyncClient, dict]:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    access_token = creds.get("access_token")
    access_token_secret = creds.get("access_token_secret")
    if not all([api_key, api_secret, access_token, access_token_secret]):
        # Fall back to bearer token for writes if OAuth 1.0a not configured
        bearer_token = creds.get("bearer_token")
        if not bearer_token:
            raise ValueError("Twitter write operations require OAuth 1.0a credentials (api_key, api_secret, access_token, access_token_secret)")
        return httpx.AsyncClient(
            base_url=TWITTER_BASE_URL,
            headers={"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"},
            timeout=30.0,
        ), {}
    auth_header = _oauth1_header(
        method, url, body_params or {},
        api_key, api_secret, access_token, access_token_secret,
    )
    return httpx.AsyncClient(
        base_url=TWITTER_BASE_URL,
        headers={"Authorization": auth_header, "Content-Type": "application/json"},
        timeout=30.0,
    ), {}


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Twitter API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Read Nodes
# ---------------------------------------------------------------------------

@register_node("twitter.search_tweets")
async def twitter_search_tweets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tweets/search/recent — search recent tweets."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("twitter.search_tweets requires 'query'")
    params: dict = {"query": query}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = min(int(max_results), 100)
    tweet_fields = config.get("tweet_fields") or input_data.get("tweet_fields")
    if tweet_fields:
        params["tweet.fields"] = tweet_fields if isinstance(tweet_fields, str) else ",".join(tweet_fields)
    async with await _read_client(credential_id, db) as client:
        r = await client.get("/tweets/search/recent", params=params)
    return _check(r)


@register_node("twitter.get_tweet")
async def twitter_get_tweet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tweets/{id} — get a tweet by ID."""
    tweet_id = config.get("tweet_id") or input_data.get("tweet_id")
    if not tweet_id:
        raise ValueError("twitter.get_tweet requires 'tweet_id'")
    params: dict = {}
    tweet_fields = config.get("tweet_fields") or input_data.get("tweet_fields")
    if tweet_fields:
        params["tweet.fields"] = tweet_fields if isinstance(tweet_fields, str) else ",".join(tweet_fields)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/tweets/{tweet_id}", params=params)
    return _check(r)


@register_node("twitter.get_user")
async def twitter_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{id} — get a user by ID."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("twitter.get_user requires 'user_id'")
    params: dict = {}
    user_fields = config.get("user_fields") or input_data.get("user_fields")
    if user_fields:
        params["user.fields"] = user_fields if isinstance(user_fields, str) else ",".join(user_fields)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}", params=params)
    return _check(r)


@register_node("twitter.get_user_by_username")
async def twitter_get_user_by_username(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/by/username/{username} — get a user by username."""
    username = config.get("username") or input_data.get("username")
    if not username:
        raise ValueError("twitter.get_user_by_username requires 'username'")
    params: dict = {}
    user_fields = config.get("user_fields") or input_data.get("user_fields")
    if user_fields:
        params["user.fields"] = user_fields if isinstance(user_fields, str) else ",".join(user_fields)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/users/by/username/{username}", params=params)
    return _check(r)


@register_node("twitter.list_user_tweets")
async def twitter_list_user_tweets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{id}/tweets — list tweets by a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("twitter.list_user_tweets requires 'user_id'")
    params: dict = {}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = min(int(max_results), 100)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/tweets", params=params)
    return _check(r)


@register_node("twitter.list_followers")
async def twitter_list_followers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{id}/followers — list followers of a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("twitter.list_followers requires 'user_id'")
    params: dict = {}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = min(int(max_results), 1000)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/followers", params=params)
    return _check(r)


@register_node("twitter.list_following")
async def twitter_list_following(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{id}/following — list accounts that a user follows."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("twitter.list_following requires 'user_id'")
    params: dict = {}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = min(int(max_results), 1000)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/following", params=params)
    return _check(r)


@register_node("twitter.list_mentions")
async def twitter_list_mentions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{id}/mentions — list recent mentions of a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("twitter.list_mentions requires 'user_id'")
    params: dict = {}
    max_results = config.get("max_results") or input_data.get("max_results")
    if max_results:
        params["max_results"] = min(int(max_results), 100)
    async with await _read_client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/mentions", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Write Nodes (OAuth 1.0a)
# ---------------------------------------------------------------------------

@register_node("twitter.create_tweet")
async def twitter_create_tweet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tweets — create a new tweet."""
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("twitter.create_tweet requires 'text'")
    body: dict = {"text": text}
    reply_to = config.get("reply_to_tweet_id") or input_data.get("reply_to_tweet_id")
    if reply_to:
        body["reply"] = {"in_reply_to_tweet_id": reply_to}
    url = f"{TWITTER_BASE_URL}/tweets"
    client, _ = await _write_client(credential_id, db, "POST", url)
    async with client as c:
        r = await c.post("/tweets", json=body)
    return _check(r)


@register_node("twitter.delete_tweet")
async def twitter_delete_tweet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /tweets/{id} — delete a tweet."""
    tweet_id = config.get("tweet_id") or input_data.get("tweet_id")
    if not tweet_id:
        raise ValueError("twitter.delete_tweet requires 'tweet_id'")
    url = f"{TWITTER_BASE_URL}/tweets/{tweet_id}"
    client, _ = await _write_client(credential_id, db, "DELETE", url)
    async with client as c:
        r = await c.delete(f"/tweets/{tweet_id}")
    return _check(r)


@register_node("twitter.like_tweet")
async def twitter_like_tweet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/{id}/likes — like a tweet."""
    user_id = config.get("user_id") or input_data.get("user_id")
    tweet_id = config.get("tweet_id") or input_data.get("tweet_id")
    if not user_id or not tweet_id:
        raise ValueError("twitter.like_tweet requires 'user_id' and 'tweet_id'")
    body = {"tweet_id": tweet_id}
    url = f"{TWITTER_BASE_URL}/users/{user_id}/likes"
    client, _ = await _write_client(credential_id, db, "POST", url, body)
    async with client as c:
        r = await c.post(f"/users/{user_id}/likes", json=body)
    return _check(r)


@register_node("twitter.retweet")
async def twitter_retweet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/{id}/retweets — retweet a tweet."""
    user_id = config.get("user_id") or input_data.get("user_id")
    tweet_id = config.get("tweet_id") or input_data.get("tweet_id")
    if not user_id or not tweet_id:
        raise ValueError("twitter.retweet requires 'user_id' and 'tweet_id'")
    body = {"tweet_id": tweet_id}
    url = f"{TWITTER_BASE_URL}/users/{user_id}/retweets"
    client, _ = await _write_client(credential_id, db, "POST", url, body)
    async with client as c:
        r = await c.post(f"/users/{user_id}/retweets", json=body)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test Twitter connection by fetching the authenticated user."""
    async with await _read_client(credential_id, db) as client:
        r = await client.get("/users/me")
    _check(r)
    return {"ok": True}
