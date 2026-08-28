"""
Linear integration — issues, projects, teams, comments, status updates.
Nodes: linear.create_issue, linear.update_issue, linear.get_issue,
       linear.list_issues, linear.create_comment, linear.search_issues,
       linear.get_teams
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


def _headers(config):
    api_key = config.get("api_key") or getattr(settings, "LINEAR_API_KEY", "")
    if not api_key:
        raise ValueError("linear nodes require LINEAR_API_KEY or 'api_key' in config")
    return {"Authorization": api_key, "Content-Type": "application/json"}


async def _graphql(query: str, variables: dict, config: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables},
            headers=_headers(config),
        )
        r.raise_for_status()
        return r.json()


@register_node("linear.create_issue")
async def linear_create_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    title = merged.get("title", "New Issue")
    description = merged.get("description", "")
    team_id = merged.get("team_id")
    priority = int(merged.get("priority", 0))
    label_ids = merged.get("label_ids") or []

    if not team_id:
        raise ValueError("linear.create_issue requires 'team_id'")

    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id title url identifier state { name } priority }
      }
    }
    """
    variables = {"input": {"teamId": team_id, "title": title, "description": description,
                            "priority": priority, "labelIds": label_ids}}
    data = await _graphql(mutation, variables, merged)
    result = data["data"]["issueCreate"]
    return {"issue": result.get("issue"), "success": result.get("success")}


@register_node("linear.update_issue")
async def linear_update_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    issue_id = merged.get("issue_id")
    if not issue_id:
        raise ValueError("linear.update_issue requires 'issue_id'")

    updates = {}
    for field in ("title", "description", "stateId", "priority", "assigneeId", "labelIds"):
        val = merged.get(field)
        if val is not None:
            updates[field] = val

    mutation = """
    mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
        issue { id title url identifier state { name } }
      }
    }
    """
    data = await _graphql(mutation, {"id": issue_id, "input": updates}, merged)
    result = data["data"]["issueUpdate"]
    return {"issue": result.get("issue"), "success": result.get("success")}


@register_node("linear.get_issue")
async def linear_get_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    issue_id = merged.get("issue_id")
    if not issue_id:
        raise ValueError("linear.get_issue requires 'issue_id'")

    query = """
    query GetIssue($id: String!) {
      issue(id: $id) {
        id title description url identifier priority
        state { name }
        assignee { name email }
        labels { nodes { name } }
      }
    }
    """
    data = await _graphql(query, {"id": issue_id}, merged)
    return {"issue": data["data"].get("issue")}


@register_node("linear.list_issues")
async def linear_list_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    team_id = merged.get("team_id")
    state_name = merged.get("state")
    first = min(int(merged.get("limit", 25)), 100)

    filter_clause = ""
    if team_id:
        filter_clause = f', filter: {{ team: {{ id: {{ eq: "{team_id}" }} }} }}'
    if state_name:
        filter_clause += f' # state filter: {state_name}'

    query = f"""
    query ListIssues {{
      issues(first: {first}{filter_clause}) {{
        nodes {{
          id title url identifier priority
          state {{ name }}
          assignee {{ name }}
        }}
      }}
    }}
    """
    data = await _graphql(query, {}, merged)
    issues = data["data"]["issues"]["nodes"]
    return {"issues": issues, "count": len(issues)}


@register_node("linear.search_issues")
async def linear_search_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    term = merged.get("query") or merged.get("term", "")
    if not term:
        raise ValueError("linear.search_issues requires 'query'")

    query = """
    query SearchIssues($term: String!) {
      issueSearch(term: $term) {
        nodes { id title url identifier state { name } }
      }
    }
    """
    data = await _graphql(query, {"term": term}, merged)
    issues = data["data"]["issueSearch"]["nodes"]
    return {"issues": issues, "count": len(issues)}


@register_node("linear.create_comment")
async def linear_create_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    issue_id = merged.get("issue_id")
    body = merged.get("body", "")
    if not issue_id:
        raise ValueError("linear.create_comment requires 'issue_id'")

    mutation = """
    mutation CreateComment($input: CommentCreateInput!) {
      commentCreate(input: $input) {
        success
        comment { id body createdAt }
      }
    }
    """
    data = await _graphql(mutation, {"input": {"issueId": issue_id, "body": body}}, merged)
    result = data["data"]["commentCreate"]
    return {"comment": result.get("comment"), "success": result.get("success")}


@register_node("linear.get_teams")
async def linear_get_teams(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    query = """
    query GetTeams {
      teams { nodes { id name key description } }
    }
    """
    data = await _graphql(query, {}, merged)
    teams = data["data"]["teams"]["nodes"]
    return {"teams": teams, "count": len(teams)}
