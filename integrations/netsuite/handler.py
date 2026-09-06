"""NetSuite integration — records via SuiteTalk REST API with OAuth 1.0."""
import hashlib
import hmac
import time
import uuid
import base64
import urllib.parse
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _netsuite_base(account_id: str) -> str:
    # NetSuite account IDs with underscores use dashes in the hostname
    host_account = account_id.lower().replace("_", "-")
    return f"https://{host_account}.suitetalk.api.netsuite.com/services/rest/record/v1"


def _oauth1_header(
    method: str,
    url: str,
    account_id: str,
    consumer_key: str,
    consumer_secret: str,
    token_id: str,
    token_secret: str,
) -> str:
    """Generate OAuth 1.0 Authorization header using HMAC-SHA256."""
    oauth_nonce = uuid.uuid4().hex
    oauth_timestamp = str(int(time.time()))

    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": oauth_nonce,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": oauth_timestamp,
        "oauth_token": token_id,
        "oauth_version": "1.0",
    }

    # Build base string
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])

    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha256).digest()
    ).decode()

    oauth_params["oauth_signature"] = signature
    oauth_params["realm"] = account_id.upper()

    header_parts = ", ".join(
        f'{k}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


def _netsuite_headers(method: str, url: str, account_id: str, consumer_key: str,
                      consumer_secret: str, token_id: str, token_secret: str) -> dict:
    auth = _oauth1_header(method, url, account_id, consumer_key, consumer_secret, token_id, token_secret)
    return {
        "Authorization": auth,
        "Content-Type": "application/json",
        "Prefer": "transient",
    }


@register_node("netsuite.list_records")
async def netsuite_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List records of a given type from NetSuite.

    config:
      account_id      — NetSuite account ID (required)
      consumer_key    — OAuth consumer key (required)
      consumer_secret — OAuth consumer secret (required)
      token_id        — OAuth token ID (required)
      token_secret    — OAuth token secret (required)
      record_type     — record type e.g. "customer", "invoice" (required)
      limit           — number of records (optional, default 25)
      offset          — pagination offset (optional, default 0)
    """
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    token_id = merged.get("token_id", "")
    token_secret = merged.get("token_secret", "")
    record_type = merged.get("record_type")
    if not all([account_id, consumer_key, consumer_secret, token_id, token_secret, record_type]):
        raise ValueError("account_id, consumer_key, consumer_secret, token_id, token_secret, and record_type are required")

    base = _netsuite_base(account_id)
    url = f"{base}/{record_type}"
    params: dict = {"limit": merged.get("limit", 25), "offset": merged.get("offset", 0)}
    full_url = url + "?" + urllib.parse.urlencode(params)

    headers = _netsuite_headers("GET", url, account_id, consumer_key, consumer_secret, token_id, token_secret)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(full_url, headers=headers)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("netsuite.list_records", record_type=record_type, count=len(items))
    return {"records": items, "count": data.get("count", len(items)), "record_type": record_type}


@register_node("netsuite.get_record")
async def netsuite_get_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific NetSuite record by type and ID.

    config:
      account_id      — NetSuite account ID (required)
      consumer_key    — OAuth consumer key (required)
      consumer_secret — OAuth consumer secret (required)
      token_id        — OAuth token ID (required)
      token_secret    — OAuth token secret (required)
      record_type     — record type e.g. "customer" (required)
      record_id       — internal ID of the record (required)
    """
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    token_id = merged.get("token_id", "")
    token_secret = merged.get("token_secret", "")
    record_type = merged.get("record_type")
    record_id = merged.get("record_id")
    if not all([account_id, consumer_key, consumer_secret, token_id, token_secret, record_type, record_id]):
        raise ValueError("All OAuth credentials, record_type, and record_id are required")

    base = _netsuite_base(account_id)
    url = f"{base}/{record_type}/{record_id}"
    headers = _netsuite_headers("GET", url, account_id, consumer_key, consumer_secret, token_id, token_secret)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        record = r.json()

    log.info("netsuite.get_record", record_type=record_type, record_id=record_id)
    return {"record": record, "record_id": record_id, "record_type": record_type}


@register_node("netsuite.create_record")
async def netsuite_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new record in NetSuite.

    config:
      account_id      — NetSuite account ID (required)
      consumer_key    — OAuth consumer key (required)
      consumer_secret — OAuth consumer secret (required)
      token_id        — OAuth token ID (required)
      token_secret    — OAuth token secret (required)
      record_type     — record type e.g. "customer" (required)
      fields          — dict of field name -> value to set on the record (required)
    """
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    token_id = merged.get("token_id", "")
    token_secret = merged.get("token_secret", "")
    record_type = merged.get("record_type")
    fields = merged.get("fields", {})
    if not all([account_id, consumer_key, consumer_secret, token_id, token_secret, record_type]):
        raise ValueError("All OAuth credentials and record_type are required")

    base = _netsuite_base(account_id)
    url = f"{base}/{record_type}"
    headers = _netsuite_headers("POST", url, account_id, consumer_key, consumer_secret, token_id, token_secret)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=fields)
        r.raise_for_status()
        # NetSuite returns the new record URL in the Location header
        location = r.headers.get("Location", "")
        record_id = location.split("/")[-1] if location else None

    log.info("netsuite.create_record", record_type=record_type, record_id=record_id)
    return {"record_id": record_id, "record_type": record_type, "location": location}


@register_node("netsuite.update_record")
async def netsuite_update_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing NetSuite record using PATCH.

    config:
      account_id      — NetSuite account ID (required)
      consumer_key    — OAuth consumer key (required)
      consumer_secret — OAuth consumer secret (required)
      token_id        — OAuth token ID (required)
      token_secret    — OAuth token secret (required)
      record_type     — record type e.g. "customer" (required)
      record_id       — internal ID of the record (required)
      fields          — dict of field name -> new value (required)
    """
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    token_id = merged.get("token_id", "")
    token_secret = merged.get("token_secret", "")
    record_type = merged.get("record_type")
    record_id = merged.get("record_id")
    fields = merged.get("fields", {})
    if not all([account_id, consumer_key, consumer_secret, token_id, token_secret, record_type, record_id]):
        raise ValueError("All OAuth credentials, record_type, and record_id are required")

    base = _netsuite_base(account_id)
    url = f"{base}/{record_type}/{record_id}"
    headers = _netsuite_headers("PATCH", url, account_id, consumer_key, consumer_secret, token_id, token_secret)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(url, headers=headers, json=fields)
        r.raise_for_status()

    log.info("netsuite.update_record", record_type=record_type, record_id=record_id)
    return {"success": True, "record_id": record_id, "record_type": record_type}


@register_node("netsuite.search_records")
async def netsuite_search_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search NetSuite records using SuiteQL (via the suiteql endpoint).

    config:
      account_id      — NetSuite account ID (required)
      consumer_key    — OAuth consumer key (required)
      consumer_secret — OAuth consumer secret (required)
      token_id        — OAuth token ID (required)
      token_secret    — OAuth token secret (required)
      query           — SuiteQL query string (required)
      limit           — number of results (optional, default 25)
      offset          — pagination offset (optional, default 0)
    """
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    token_id = merged.get("token_id", "")
    token_secret = merged.get("token_secret", "")
    query = merged.get("query")
    if not all([account_id, consumer_key, consumer_secret, token_id, token_secret, query]):
        raise ValueError("All OAuth credentials and query are required")

    host_account = account_id.lower().replace("_", "-")
    url = f"https://{host_account}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql"
    params = {"limit": merged.get("limit", 25), "offset": merged.get("offset", 0)}
    headers = _netsuite_headers("POST", url, account_id, consumer_key, consumer_secret, token_id, token_secret)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json={"q": query}, params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("netsuite.search_records", count=len(items))
    return {"records": items, "count": data.get("count", len(items)), "total_results": data.get("totalResults")}
