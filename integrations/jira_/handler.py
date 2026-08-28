"""
Jira (Atlassian Cloud) integration. Credential fields:
{"domain": "yourcompany.atlassian.net", "email": "you@company.com",
 "api_token": "..."} — Atlassian Cloud REST API uses HTTP Basic auth with
your account email + an API token (not your password), generated from
https://id.atlassian.com/manage-profile/security/api-tokens.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    domain = creds.get("domain")
    email = creds.get("email")
    api_token = creds.get("api_token")
    if not domain or not email or not api_token:
        raise ValueError("Jira credential is missing 'domain', 'email', or 'api_token'")
    return httpx.AsyncClient(
        base_url=f"https://{domain}/rest/api/3",
        auth=(email, api_token),
        timeout=30,
    )


@register_node("jira.create_issue")
async def jira_create_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_key = config.get("project_key") or input_data.get("project_key")
    summary = config.get("summary") or input_data.get("summary")
    description = config.get("description") or input_data.get("description", "")
    issue_type = config.get("issue_type", "Task")

    if not project_key or not summary:
        raise ValueError("jira.create_issue requires 'project_key' and 'summary'")

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
    }
    if description:
        # Jira Cloud's v3 API uses Atlassian Document Format, not plain
        # strings, for rich-text fields — this is the minimal valid ADF
        # wrapper for a single paragraph of plain text.
        payload["fields"]["description"] = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
        }

    async with await _client(credential_id, db) as client:
        r = await client.post("/issue", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"key": data["key"], "id": data["id"]}


@register_node("jira.search_issues")
async def jira_search_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    jql = config.get("jql") or input_data.get("jql")
    max_results = min(int(config.get("max_results", 20)), 100)
    if not jql:
        raise ValueError("jira.search_issues requires 'jql' (Jira Query Language)")

    async with await _client(credential_id, db) as client:
        r = await client.get("/search", params={"jql": jql, "maxResults": max_results})
        r.raise_for_status()
        data = r.json()

    return {
        "total": data.get("total", 0),
        "issues": [
            {"key": i["key"], "summary": i["fields"].get("summary"), "status": i["fields"].get("status", {}).get("name")}
            for i in data.get("issues", [])
        ],
    }


@register_node("jira.add_comment")
async def jira_add_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    issue_key = config.get("issue_key") or input_data.get("issue_key")
    comment = config.get("comment") or input_data.get("comment")
    if not issue_key or not comment:
        raise ValueError("jira.add_comment requires 'issue_key' and 'comment'")

    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}}

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/issue/{issue_key}/comment", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"id": data["id"]}


async def test_connection(creds: dict) -> None:
    domain = creds.get("domain")
    email = creds.get("email")
    api_token = creds.get("api_token")
    if not domain or not email or not api_token:
        raise ValueError("Missing domain, email, or api_token")
    async with httpx.AsyncClient(base_url=f"https://{domain}/rest/api/3", auth=(email, api_token), timeout=10) as client:
        r = await client.get("/myself")
        r.raise_for_status()
