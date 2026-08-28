"""RBAC — role-based permission checks as FastAPI dependencies."""
from fastapi import Depends, HTTPException, status

from api.middleware.auth import get_current_user
from storage.models import User

ROLE_RANK = {"owner": 4, "admin": 3, "editor": 2, "viewer": 1}

PERMISSIONS: dict[str, list[str]] = {
    "workflow:read":       ["viewer", "editor", "admin", "owner"],
    "workflow:create":     ["editor", "admin", "owner"],
    "workflow:update":     ["editor", "admin", "owner"],
    "workflow:delete":     ["admin", "owner"],
    "workflow:execute":    ["editor", "admin", "owner"],
    "member:read":         ["viewer", "editor", "admin", "owner"],
    "member:invite":       ["admin", "owner"],
    "member:remove":       ["admin", "owner"],
    "member:role":         ["owner"],
    "audit:read":          ["admin", "owner"],
    "org:settings":        ["owner"],
    "marketplace:publish": ["editor", "admin", "owner"],
    "dlq:replay":          ["admin", "owner"],
    # Raw database credentials (host/username/password, decrypted
    # server-side on every node run) are higher blast-radius than an
    # OAuth token scoped to one provider's API — restrict who in an org
    # can add one at all.
    "credential:database:manage": ["admin", "owner"],
    # A workflow with a database.execute node can INSERT/UPDATE/DELETE
    # against a connected database. Gating workflow *creation/editing*
    # is necessary but not sufficient on its own — see
    # check_write_db_permission() below for why the execution engine
    # also re-checks this at run time.
    "workflow:use_database_execute": ["admin", "owner"],
}


def user_has_permission(user: User, permission: str) -> bool:
    """
    Non-raising check for use inside handlers that need to branch on
    permission rather than hard-fail the whole request (e.g. workflow
    save, where only the presence of a specific node type triggers the
    stricter check).

    Users with no org (solo/personal workspace) are treated as the sole
    owner of their own data — role gating exists to separate teammates
    from each other within an org, not to restrict someone from their
    own personal workflows.
    """
    if not user.org_id or not user.role:
        return True
    allowed = PERMISSIONS.get(permission, [])
    return user.role.value in allowed


def require_permission(permission: str):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.org_id or not user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not part of an organization")
        allowed = PERMISSIONS.get(permission, [])
        if user.role.value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles {allowed} for '{permission}', you have '{user.role.value}'",
            )
        return user
    return _checker


def require_permission_or_personal(permission: str):
    """
    Like require_permission, but solo/personal-workspace users (no org)
    are allowed through rather than 403'd — role gating exists to keep
    teammates from overreaching each other's org, not to block someone
    from features on their own account. Use this for things like the
    manual database credential endpoint, where a solo user has every
    right to add their own DB connection.
    """
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(user, permission):
            allowed = PERMISSIONS.get(permission, [])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles {allowed} for '{permission}', you have '{user.role.value if user.role else None}'",
            )
        return user
    return _checker


def require_role(min_role: str):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not part of an organization")
        if ROLE_RANK.get(user.role.value, 0) < ROLE_RANK.get(min_role, 0):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires {min_role} role or above")
        return user
    return _checker


# Node types that can mutate a system outside AutoFlow itself, gated by
# workflow:use_database_execute. Extend this set as new write-capable
# integrations are added (e.g. a future "s3.delete" or "http.delete_data"
# node with irreversible side effects).
WRITE_CAPABLE_NODE_TYPES = {"database.execute"}


def check_write_db_permission(definition: dict, user: User) -> None:
    """
    Raise 403 if `definition` (a workflow's node graph) contains a
    write-capable node type and this user's org role isn't allowed to
    use one. Call this from both:
      - workflow create/update (api/routes/workflows.py) — stops the
        node from being saved into a workflow in the first place.
      - the execution engine, immediately before running a node of this
        type (core/execution_engine.py) — because a workflow saved
        before someone's role was downgraded, or shared/duplicated from
        another workflow, should not silently keep write access forever.
        Save-time and run-time checks are both needed; save-time alone
        has a gap once roles change after the fact.
    """
    nodes = (definition or {}).get("nodes", [])
    has_write_node = any(n.get("type") in WRITE_CAPABLE_NODE_TYPES for n in nodes)
    if has_write_node and not user_has_permission(user, "workflow:use_database_execute"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This workflow uses a database write node (database.execute), which "
                "requires the 'admin' or 'owner' role in this organization."
            ),
        )
