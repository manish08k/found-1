"""
Bitwarden Password Manager Public Organization API integration.

Provides member management and collection management for a Bitwarden
Organization via the Bitwarden Public API.

Credential fields:
  - client_id     : OAuth2 client_id for the organization API key.
  - client_secret : OAuth2 client_secret for the organization API key.

Auth: client_credentials OAuth2 flow — tokens are fetched from
      https://identity.bitwarden.com/connect/token and cached per invocation.
Base URL: https://api.bitwarden.com/public/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bitwarden.com/public"
TOKEN_URL = "https://identity.bitwarden.com/connect/token"


async def _get_access_token(client_id: str, client_secret: str) -> str:
    """Obtain a client_credentials access token from Bitwarden Identity."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "api.organization",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 300:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise ValueError(f"Bitwarden token error {r.status_code}: {detail}")
        token_data = r.json()
        return token_data["access_token"]


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    if not client_id:
        raise ValueError("Bitwarden credential missing 'client_id'")
    if not client_secret:
        raise ValueError("Bitwarden credential missing 'client_secret'")

    access_token = await _get_access_token(client_id, client_secret)

    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Bitwarden API error {r.status_code}: {detail}")


@register_node("bitwarden.list_members")
async def bw_list_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all members of the organization.

    No additional parameters required.
    """
    async with await _client(credential_id, db) as client:
        r = await client.get("/members")
        _raise_for_status(r)
        data = r.json()

    members = data.get("data", [])
    log.info("bitwarden.list_members", count=len(members))
    return {"members": members, "count": len(members), "continuation_token": data.get("continuationToken")}


@register_node("bitwarden.invite_member")
async def bw_invite_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Invite a new member to the organization.

    Params:
      - email (required): Email address of the user to invite.
      - type: Member type — 0 (Owner), 1 (Admin), 2 (User), 3 (Manager), 4 (Custom).
               Default 2 (User).
      - access_all: bool — grant access to all collections (default False).
      - collections: List of collection access dicts, e.g.
          [{"id": "uuid", "readOnly": false, "hidePasswords": false}]
      - reset_password_enrolled: bool — auto-enroll in password reset (default False).
    """
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("bitwarden.invite_member requires 'email'")

    member_type = int(config.get("type") if config.get("type") is not None else input_data.get("type", 2))
    access_all = bool(config.get("access_all") or input_data.get("access_all", False))
    reset_password_enrolled = bool(
        config.get("reset_password_enrolled") or input_data.get("reset_password_enrolled", False)
    )

    collections = config.get("collections") or input_data.get("collections", [])
    if isinstance(collections, str):
        import json
        collections = json.loads(collections)

    payload: dict = {
        "email": email,
        "type": member_type,
        "accessAll": access_all,
        "resetPasswordEnrolled": reset_password_enrolled,
        "collections": collections,
    }

    async with await _client(credential_id, db) as client:
        r = await client.post("/members", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bitwarden.invite_member", email=email, id=data.get("id"))
    return {"member": data, "id": data.get("id"), "email": data.get("email")}


@register_node("bitwarden.list_collections")
async def bw_list_collections(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all collections in the organization.

    No additional parameters required.
    """
    async with await _client(credential_id, db) as client:
        r = await client.get("/collections")
        _raise_for_status(r)
        data = r.json()

    collections = data.get("data", [])
    log.info("bitwarden.list_collections", count=len(collections))
    return {"collections": collections, "count": len(collections)}


@register_node("bitwarden.create_collection")
async def bw_create_collection(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new collection in the organization.

    Params:
      - name (required): Collection name.
      - external_id: External identifier for the collection.
      - groups: List of group access dicts, e.g.
          [{"id": "group-uuid", "readOnly": false, "hidePasswords": false}]
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("bitwarden.create_collection requires 'name'")

    payload: dict = {"name": name}

    external_id = config.get("external_id") or input_data.get("external_id")
    if external_id:
        payload["externalId"] = external_id

    groups = config.get("groups") or input_data.get("groups", [])
    if isinstance(groups, str):
        import json
        groups = json.loads(groups)
    payload["groups"] = groups

    async with await _client(credential_id, db) as client:
        r = await client.post("/collections", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bitwarden.create_collection", name=name, id=data.get("id"))
    return {"collection": data, "id": data.get("id"), "name": data.get("name")}


@register_node("bitwarden.update_member")
async def bw_update_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update an existing organization member.

    Params:
      - member_id (required): The UUID of the member to update.
      - type: New member type (0=Owner, 1=Admin, 2=User, 3=Manager, 4=Custom).
      - access_all: bool — grant/revoke access to all collections.
      - collections: Updated list of collection access dicts.
      - reset_password_enrolled: bool.
    """
    member_id = config.get("member_id") or input_data.get("member_id")
    if not member_id:
        raise ValueError("bitwarden.update_member requires 'member_id'")

    payload: dict = {}

    member_type = config.get("type") if config.get("type") is not None else input_data.get("type")
    if member_type is not None:
        payload["type"] = int(member_type)

    access_all = config.get("access_all")
    if access_all is None:
        access_all = input_data.get("access_all")
    if access_all is not None:
        payload["accessAll"] = bool(access_all)

    reset_pw = config.get("reset_password_enrolled")
    if reset_pw is None:
        reset_pw = input_data.get("reset_password_enrolled")
    if reset_pw is not None:
        payload["resetPasswordEnrolled"] = bool(reset_pw)

    collections = config.get("collections") or input_data.get("collections")
    if collections is not None:
        if isinstance(collections, str):
            import json
            collections = json.loads(collections)
        payload["collections"] = collections

    if not payload:
        raise ValueError("bitwarden.update_member requires at least one field to update")

    async with await _client(credential_id, db) as client:
        r = await client.put(f"/members/{member_id}", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("bitwarden.update_member", member_id=member_id)
    return {"member": data, "id": data.get("id")}
