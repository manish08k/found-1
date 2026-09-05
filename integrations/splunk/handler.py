"""
Splunk SIEM integration.

Credential fields:
  - base_url: Splunk instance base URL, e.g. https://splunk.example.com:8089
  - token    : Splunk HTTP Event Collector / REST API Bearer token

Auth: Authorization: Bearer {token}
Base URL: {base_url}/services/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    token = creds.get("token")
    if not base_url:
        raise ValueError("Splunk credential missing 'base_url'")
    if not token:
        raise ValueError("Splunk credential missing 'token'")
    return httpx.AsyncClient(
        base_url=f"{base_url}/services/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        # Many Splunk instances use self-signed certs; verify can be toggled via env
        verify=True,
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> dict:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Splunk API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    try:
        return r.json()
    except Exception:
        return {"response": r.text}


@register_node("splunk.search")
async def splunk_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Run a Splunk search query and return results.

    Config keys:
      search     (str): SPL search string (e.g. 'search index=main error | head 20')
      earliest   (str): Earliest time modifier (default '-24h')
      latest     (str): Latest time modifier (default 'now')
      max_count  (int): Maximum results to return (default 100)
    """
    query = config.get("search") or input_data.get("search")
    if not query:
        raise ValueError("splunk.search requires 'search'")

    earliest = config.get("earliest") or input_data.get("earliest", "-24h")
    latest = config.get("latest") or input_data.get("latest", "now")
    max_count = min(int(config.get("max_count") or input_data.get("max_count", 100)), 10000)

    # Ensure query starts with 'search' keyword
    if not query.strip().lower().startswith("search"):
        query = f"search {query}"

    log.info("splunk.search", query=query[:80], earliest=earliest, latest=latest)

    async with await _client(credential_id, db) as client:
        # Create a blocking search job
        r = await client.post(
            "search/jobs",
            data={
                "search": query,
                "earliest_time": earliest,
                "latest_time": latest,
                "output_mode": "json",
                "exec_mode": "blocking",
                "count": max_count,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        job_data = _raise_for_status(r)
        sid = job_data.get("sid")
        if not sid:
            raise ValueError(f"Splunk search job did not return sid: {job_data}")

        # Fetch results
        results_r = await client.get(
            f"search/jobs/{sid}/results",
            params={"output_mode": "json", "count": max_count},
        )
        results_data = _raise_for_status(results_r)

    results = results_data.get("results", [])
    return {"results": results, "count": len(results), "sid": sid, "query": query}


@register_node("splunk.get_events")
async def splunk_get_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve raw events from a Splunk index.

    Config keys:
      index    (str): Splunk index name (default 'main')
      source   (str): Optional source filter
      host     (str): Optional host filter
      earliest (str): Earliest time (default '-1h')
      latest   (str): Latest time (default 'now')
      limit    (int): Max events to retrieve (default 50)
    """
    index = config.get("index") or input_data.get("index", "main")
    source = config.get("source") or input_data.get("source", "")
    host = config.get("host") or input_data.get("host", "")
    earliest = config.get("earliest") or input_data.get("earliest", "-1h")
    latest = config.get("latest") or input_data.get("latest", "now")
    limit = min(int(config.get("limit") or input_data.get("limit", 50)), 1000)

    query_parts = [f"search index={index}"]
    if source:
        query_parts.append(f"source={source}")
    if host:
        query_parts.append(f"host={host}")
    query = " ".join(query_parts) + f" | head {limit}"

    log.info("splunk.get_events", index=index, limit=limit)

    async with await _client(credential_id, db) as client:
        r = await client.post(
            "search/jobs",
            data={
                "search": query,
                "earliest_time": earliest,
                "latest_time": latest,
                "output_mode": "json",
                "exec_mode": "blocking",
                "count": limit,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        job_data = _raise_for_status(r)
        sid = job_data.get("sid")
        if not sid:
            raise ValueError(f"Splunk search job did not return sid: {job_data}")

        results_r = await client.get(
            f"search/jobs/{sid}/results",
            params={"output_mode": "json", "count": limit},
        )
        results_data = _raise_for_status(results_r)

    events = results_data.get("results", [])
    return {"events": events, "count": len(events), "index": index}


@register_node("splunk.create_alert")
async def splunk_create_alert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a saved search alert in Splunk.

    Config keys:
      name        (str) : Alert name (required)
      search      (str) : SPL search string (required)
      cron_schedule (str): Cron expression (default '0 * * * *' = hourly)
      alert_type  (str) : 'number of events' or 'custom' (default 'number of events')
      threshold   (int) : Alert threshold (default 1)
      actions     (str) : Comma-separated action list (default 'email')
      email       (str) : Email address for alert (optional)
    """
    name = config.get("name") or input_data.get("name")
    search = config.get("search") or input_data.get("search")
    if not name:
        raise ValueError("splunk.create_alert requires 'name'")
    if not search:
        raise ValueError("splunk.create_alert requires 'search'")

    cron = config.get("cron_schedule") or input_data.get("cron_schedule", "0 * * * *")
    alert_type = config.get("alert_type") or input_data.get("alert_type", "number of events")
    threshold = int(config.get("threshold") or input_data.get("threshold", 1))
    actions = config.get("actions") or input_data.get("actions", "email")
    email = config.get("email") or input_data.get("email", "")

    if not search.strip().lower().startswith("search"):
        search = f"search {search}"

    payload: dict = {
        "name": name,
        "search": search,
        "cron_schedule": cron,
        "is_scheduled": "1",
        "alert_type": alert_type,
        "alert_comparator": "greater than",
        "alert_threshold": str(threshold),
        "actions": actions,
    }
    if email:
        payload["action.email.to"] = email
        payload["action.email"] = "1"

    log.info("splunk.create_alert", name=name)
    async with await _client(credential_id, db) as client:
        r = await client.post(
            "saved/searches",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    data = _raise_for_status(r)
    return {"alert": data, "name": name, "success": True}


@register_node("splunk.list_saved_searches")
async def splunk_list_saved_searches(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List saved searches / alerts in Splunk.

    Config keys:
      count  (int): Maximum number to return (default 50)
      search (str): Optional filter string to narrow results
    """
    count = min(int(config.get("count") or input_data.get("count", 50)), 500)
    filter_str = config.get("search") or input_data.get("search", "")

    params: dict = {"output_mode": "json", "count": count}
    if filter_str:
        params["search"] = filter_str

    log.info("splunk.list_saved_searches", count=count)
    async with await _client(credential_id, db) as client:
        r = await client.get("saved/searches", params=params)
    data = _raise_for_status(r)
    entries = data.get("entry", [])
    searches = [
        {
            "name": e.get("name"),
            "search": e.get("content", {}).get("search"),
            "cron_schedule": e.get("content", {}).get("cron_schedule"),
            "is_scheduled": e.get("content", {}).get("is_scheduled"),
        }
        for e in entries
    ]
    return {"saved_searches": searches, "count": len(searches)}
