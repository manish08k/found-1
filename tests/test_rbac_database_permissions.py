"""Tests for api/middleware/rbac.py's write-DB-node and manual-credential gating."""
import pytest
from types import SimpleNamespace

from fastapi import HTTPException

from api.middleware.rbac import (
    user_has_permission,
    check_write_db_permission,
    PERMISSIONS,
)


def _user(role: str | None, org_id: str | None = "org-1"):
    role_obj = SimpleNamespace(value=role) if role else None
    return SimpleNamespace(id="u1", org_id=org_id, role=role_obj)


@pytest.mark.parametrize("role,expected", [
    ("owner", True), ("admin", True), ("editor", False), ("viewer", False),
])
def test_database_manage_permission_by_role(role, expected):
    assert user_has_permission(_user(role), "credential:database:manage") is expected


def test_solo_user_without_org_is_always_allowed():
    """Role gating separates teammates within an org — it shouldn't block a solo user from their own data."""
    solo = _user(role=None, org_id=None)
    assert user_has_permission(solo, "credential:database:manage") is True
    assert user_has_permission(solo, "workflow:use_database_execute") is True


def test_check_write_db_permission_allows_admin():
    definition = {"nodes": [{"id": "n1", "type": "database.execute"}]}
    check_write_db_permission(definition, _user("admin"))  # should not raise


def test_check_write_db_permission_blocks_editor():
    definition = {"nodes": [{"id": "n1", "type": "database.execute"}]}
    with pytest.raises(HTTPException) as exc:
        check_write_db_permission(definition, _user("editor"))
    assert exc.value.status_code == 403


def test_check_write_db_permission_ignores_read_only_nodes():
    """A workflow with only database.query (read-only) shouldn't be gated by the write permission."""
    definition = {"nodes": [{"id": "n1", "type": "database.query"}]}
    check_write_db_permission(definition, _user("viewer"))  # should not raise


def test_check_write_db_permission_handles_empty_definition():
    check_write_db_permission({}, _user("viewer"))  # should not raise
    check_write_db_permission({"nodes": []}, _user("viewer"))  # should not raise
