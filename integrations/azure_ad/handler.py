"""Azure Active Directory integration — users, groups, and directory management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("azure_ad.list_users")
async def azure_ad_list_users(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all users in the Azure AD tenant.

    config:
      access_token — OAuth bearer token with User.Read.All permission (required)
      tenant_id    — Azure AD tenant ID (required)
      top          — maximum number of users to return (optional, default 100)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {"$top": merged.get("top", 100)}
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/users", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    users = data.get("value", [])
    log.info("azure_ad.list_users", count=len(users))
    return {"users": users, "count": len(users)}


@register_node("azure_ad.get_user")
async def azure_ad_get_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Azure AD user.

    config:
      access_token — OAuth bearer token (required)
      user_id      — user ID or user principal name (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    user_id = merged.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for azure_ad.get_user")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/users/{user_id}", headers=_graph_headers(access_token))
        r.raise_for_status()
        user = r.json()

    log.info("azure_ad.get_user", user_id=user_id, display_name=user.get("displayName"))
    return {"user": user, "user_id": user_id}


@register_node("azure_ad.create_user")
async def azure_ad_create_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Azure AD user.

    config:
      access_token       — OAuth bearer token with User.ReadWrite.All (required)
      display_name       — user's display name (required)
      user_principal_name — e.g. johndoe@contoso.com (required)
      mail_nickname      — mail alias (required)
      password           — initial password (required)
      account_enabled    — whether account is enabled, default True
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    display_name = merged.get("display_name")
    user_principal_name = merged.get("user_principal_name")
    mail_nickname = merged.get("mail_nickname")
    password = merged.get("password")

    if not all([display_name, user_principal_name, mail_nickname, password]):
        raise ValueError(
            "display_name, user_principal_name, mail_nickname, and password are required for azure_ad.create_user"
        )

    payload = {
        "displayName": display_name,
        "userPrincipalName": user_principal_name,
        "mailNickname": mail_nickname,
        "accountEnabled": merged.get("account_enabled", True),
        "passwordProfile": {
            "forceChangePasswordNextSignIn": merged.get("force_change_password", True),
            "password": password,
        },
    }

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post("/users", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        user = r.json()

    log.info("azure_ad.create_user", user_id=user.get("id"), upn=user_principal_name)
    return {"user": user, "user_id": user.get("id")}


@register_node("azure_ad.update_user")
async def azure_ad_update_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an Azure AD user's properties.

    config:
      access_token — OAuth bearer token with User.ReadWrite.All (required)
      user_id      — user ID or UPN (required)
      properties   — dict of properties to update (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    user_id = merged.get("user_id")
    properties = merged.get("properties", {})

    if not user_id:
        raise ValueError("user_id is required for azure_ad.update_user")
    if not properties:
        raise ValueError("properties dict is required for azure_ad.update_user")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(
            f"/users/{user_id}", headers=_graph_headers(access_token), json=properties
        )
        r.raise_for_status()

    log.info("azure_ad.update_user", user_id=user_id)
    return {"success": True, "user_id": user_id}


@register_node("azure_ad.delete_user")
async def azure_ad_delete_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an Azure AD user.

    config:
      access_token — OAuth bearer token with User.ReadWrite.All (required)
      user_id      — user ID or UPN (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    user_id = merged.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for azure_ad.delete_user")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(f"/users/{user_id}", headers=_graph_headers(access_token))
        r.raise_for_status()

    log.info("azure_ad.delete_user", user_id=user_id)
    return {"success": True, "user_id": user_id}


@register_node("azure_ad.list_groups")
async def azure_ad_list_groups(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all groups in the Azure AD tenant.

    config:
      access_token — OAuth bearer token with Group.Read.All (required)
      top          — maximum number of groups to return (optional, default 100)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {"$top": merged.get("top", 100)}
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/groups", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    groups = data.get("value", [])
    log.info("azure_ad.list_groups", count=len(groups))
    return {"groups": groups, "count": len(groups)}


@register_node("azure_ad.add_member_to_group")
async def azure_ad_add_member_to_group(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Add a user or service principal as a member of an Azure AD group.

    config:
      access_token — OAuth bearer token with GroupMember.ReadWrite.All (required)
      group_id     — group object ID (required)
      member_id    — user or object ID to add (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    group_id = merged.get("group_id")
    member_id = merged.get("member_id")

    if not group_id or not member_id:
        raise ValueError("group_id and member_id are required for azure_ad.add_member_to_group")

    payload = {
        "@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{member_id}"
    }

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(
            f"/groups/{group_id}/members/$ref",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()

    log.info("azure_ad.add_member_to_group", group_id=group_id, member_id=member_id)
    return {"success": True, "group_id": group_id, "member_id": member_id}
