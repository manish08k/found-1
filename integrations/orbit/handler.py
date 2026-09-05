"""
Orbit community platform integration.

Auth: Bearer token (api_key).

Credential fields:
  - workspace_slug (str) : Your Orbit workspace slug.
  - api_key (str)        : Orbit API key.

Nodes:
  - orbit.list_members   : List members in the workspace.
  - orbit.create_member  : Create a new member.
  - orbit.add_activity   : Add an activity to a member.
  - orbit.get_member     : Get a specific member by id or slug.

Base URL: https://app.orbit.love/api/v1/{workspace_slug}/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    creds = await get_credential_data(credential_id, db)
    workspace_slug = creds.get("workspace_slug")
    api_key = creds.get("api_key")
    if not workspace_slug:
        raise ValueError("Orbit credential missing 'workspace_slug'")
    if not api_key:
        raise ValueError("Orbit credential missing 'api_key'")
    base_url = f"https://app.orbit.love/api/v1/{workspace_slug}/"
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )
    return client, workspace_slug


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Orbit API error {r.status_code}: {detail}")


@register_node("orbit.list_members")
async def list_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List members in the Orbit workspace.

    Config / input keys:
      - page (int)     : Page number. Default 1.
      - per_page (int) : Results per page (max 100). Default 25.
      - query (str)    : Search query to filter members.
      - sort (str)     : Sort field, e.g. "orbit_level", "created_at". Default "created_at".
    """
    client, workspace_slug = await _client(credential_id, db)
    page = int(config.get("page") or input_data.get("page", 1))
    per_page = min(int(config.get("per_page") or input_data.get("per_page", 25)), 100)
    query = config.get("query") or input_data.get("query")
    sort = config.get("sort") or input_data.get("sort", "created_at")

    params: dict = {"page": page, "items": per_page, "sort": sort}
    if query:
        params["query"] = query

    log.info("orbit.list_members", workspace_slug=workspace_slug, page=page)
    async with client:
        r = await client.get("members", params=params)
        _raise_for_status(r)
        data = r.json()

    members = data.get("data", [])
    return {
        "members": members,
        "count": len(members),
        "page": page,
        "included": data.get("included", []),
    }


@register_node("orbit.create_member")
async def create_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new member in the Orbit workspace.

    Config / input keys:
      - email (str)      : Member email.
      - name (str)       : Full name.
      - github (str)     : GitHub username.
      - twitter (str)    : Twitter handle.
      - bio (str)        : Short biography.
      - tags (list|str)  : Comma-separated tags or list.
    """
    client, workspace_slug = await _client(credential_id, db)

    email = config.get("email") or input_data.get("email")
    name = config.get("name") or input_data.get("name")
    github = config.get("github") or input_data.get("github")
    twitter = config.get("twitter") or input_data.get("twitter")
    bio = config.get("bio") or input_data.get("bio")
    tags_raw = config.get("tags") or input_data.get("tags")

    member_payload: dict = {}
    if email:
        member_payload["email"] = email
    if name:
        member_payload["name"] = name
    if github:
        member_payload["github"] = github
    if twitter:
        member_payload["twitter"] = twitter
    if bio:
        member_payload["bio"] = bio
    if tags_raw:
        if isinstance(tags_raw, str):
            member_payload["tags_to_add"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            member_payload["tags_to_add"] = list(tags_raw)

    if not member_payload:
        raise ValueError("orbit.create_member requires at least one field (email, name, etc.)")

    log.info("orbit.create_member", workspace_slug=workspace_slug, email=email)
    async with client:
        r = await client.post("members", json={"member": member_payload})
        _raise_for_status(r)
        data = r.json()

    return {"member": data.get("data", {}), "included": data.get("included", [])}


@register_node("orbit.add_activity")
async def add_activity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add an activity to a member.

    Config / input keys:
      - member_id (str, required)  : Orbit member id or slug.
      - activity_type (str)        : Type key, e.g. "custom:opened_ticket". Default "custom:activity".
      - title (str)                : Activity title.
      - description (str)          : Activity description.
      - occurred_at (str)          : ISO-8601 datetime. Defaults to now.
      - key (str)                  : Idempotency key to avoid duplicates.
      - link (str)                 : URL associated with the activity.
      - weight (float)             : Orbit weight. Default 1.0.
    """
    client, workspace_slug = await _client(credential_id, db)

    member_id = config.get("member_id") or input_data.get("member_id")
    if not member_id:
        raise ValueError("orbit.add_activity requires 'member_id'")

    activity: dict = {
        "activity_type": config.get("activity_type") or input_data.get("activity_type", "custom:activity"),
        "weight": float(config.get("weight") or input_data.get("weight", 1.0)),
    }
    for field in ("title", "description", "occurred_at", "key", "link"):
        val = config.get(field) or input_data.get(field)
        if val:
            activity[field] = val

    log.info("orbit.add_activity", workspace_slug=workspace_slug, member_id=member_id)
    async with client:
        r = await client.post(f"members/{member_id}/activities", json={"activity": activity})
        _raise_for_status(r)
        data = r.json()

    return {"activity": data.get("data", {}), "included": data.get("included", [])}


@register_node("orbit.get_member")
async def get_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a single member by Orbit member id or slug.

    Config / input keys:
      - member_id (str, required) : Orbit member id or slug.
    """
    client, workspace_slug = await _client(credential_id, db)

    member_id = config.get("member_id") or input_data.get("member_id")
    if not member_id:
        raise ValueError("orbit.get_member requires 'member_id'")

    log.info("orbit.get_member", workspace_slug=workspace_slug, member_id=member_id)
    async with client:
        r = await client.get(f"members/{member_id}")
        _raise_for_status(r)
        data = r.json()

    return {"member": data.get("data", {}), "included": data.get("included", [])}
