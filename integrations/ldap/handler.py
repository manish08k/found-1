"""
LDAP directory integration.

Provides directory search, entry retrieval, creation, and update via LDAP3.

Credential fields:
  - host          : LDAP server hostname or IP
  - port          : LDAP port (default 389, or 636 for SSL)
  - bind_dn       : Bind distinguished name
  - bind_password : Bind password
  - use_ssl       : Boolean, use LDAPS (default False)
"""
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import ldap3
    _LDAP3_AVAILABLE = True
except ImportError:
    _LDAP3_AVAILABLE = False


def _require_ldap3() -> None:
    if not _LDAP3_AVAILABLE:
        raise ImportError(
            "The 'ldap3' package is required for LDAP integration but is not installed. "
            "Install it with: pip install ldap3"
        )


def _get_connection(creds: dict):
    """Build and bind an ldap3 Connection from credential data."""
    _require_ldap3()
    host = creds.get("host")
    port = int(creds.get("port", 636 if creds.get("use_ssl") else 389))
    bind_dn = creds.get("bind_dn")
    bind_password = creds.get("bind_password")
    use_ssl = bool(creds.get("use_ssl", False))

    if not host:
        raise ValueError("LDAP credential missing 'host'")
    if not bind_dn:
        raise ValueError("LDAP credential missing 'bind_dn'")
    if not bind_password:
        raise ValueError("LDAP credential missing 'bind_password'")

    server = ldap3.Server(host, port=port, use_ssl=use_ssl, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
    return conn


@register_node("ldap.search")
async def ldap_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search LDAP directory entries."""
    _require_ldap3()
    creds = await get_credential_data(credential_id, db)

    search_base = config.get("search_base") or input_data.get("search_base")
    search_filter = config.get("search_filter") or input_data.get("search_filter", "(objectClass=*)")
    attributes = config.get("attributes") or input_data.get("attributes", ldap3.ALL_ATTRIBUTES)
    scope_str = (config.get("scope") or input_data.get("scope", "SUBTREE")).upper()

    scope_map = {
        "SUBTREE": ldap3.SUBTREE,
        "LEVEL": ldap3.LEVEL,
        "BASE": ldap3.BASE,
    }
    scope = scope_map.get(scope_str, ldap3.SUBTREE)

    if not search_base:
        raise ValueError("ldap.search requires 'search_base'")

    log.info("ldap.search", search_base=search_base, search_filter=search_filter)
    conn = _get_connection(creds)
    try:
        conn.search(search_base, search_filter, search_scope=scope, attributes=attributes)
        entries = []
        for entry in conn.entries:
            entries.append({"dn": entry.entry_dn, "attributes": entry.entry_attributes_as_dict})
    finally:
        conn.unbind()

    return {"entries": entries, "count": len(entries)}


@register_node("ldap.get_entry")
async def ldap_get_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get a specific LDAP entry by its distinguished name."""
    _require_ldap3()
    creds = await get_credential_data(credential_id, db)

    dn = config.get("dn") or input_data.get("dn")
    attributes = config.get("attributes") or input_data.get("attributes", ldap3.ALL_ATTRIBUTES)

    if not dn:
        raise ValueError("ldap.get_entry requires 'dn'")

    log.info("ldap.get_entry", dn=dn)
    conn = _get_connection(creds)
    try:
        conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE, attributes=attributes)
        if not conn.entries:
            return {"entry": None, "found": False}
        entry = conn.entries[0]
        result = {"dn": entry.entry_dn, "attributes": entry.entry_attributes_as_dict}
    finally:
        conn.unbind()

    return {"entry": result, "found": True}


@register_node("ldap.create_entry")
async def ldap_create_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new LDAP directory entry."""
    _require_ldap3()
    creds = await get_credential_data(credential_id, db)

    dn = config.get("dn") or input_data.get("dn")
    object_class = config.get("object_class") or input_data.get("object_class")
    attributes = config.get("attributes") or input_data.get("attributes", {})

    if not dn:
        raise ValueError("ldap.create_entry requires 'dn'")
    if not object_class:
        raise ValueError("ldap.create_entry requires 'object_class'")

    log.info("ldap.create_entry", dn=dn, object_class=object_class)
    conn = _get_connection(creds)
    try:
        success = conn.add(dn, object_class, attributes)
        result = conn.result
    finally:
        conn.unbind()

    if not success:
        raise ValueError(f"LDAP create_entry failed: {result}")

    return {"created": True, "dn": dn, "result": result}


@register_node("ldap.update_entry")
async def ldap_update_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Modify attributes on an existing LDAP entry."""
    _require_ldap3()
    creds = await get_credential_data(credential_id, db)

    dn = config.get("dn") or input_data.get("dn")
    changes = config.get("changes") or input_data.get("changes", {})

    if not dn:
        raise ValueError("ldap.update_entry requires 'dn'")
    if not changes:
        raise ValueError("ldap.update_entry requires 'changes' dict mapping attribute -> value")

    # Build ldap3 change dict: {attr: [(MODIFY_REPLACE, [value])]}
    ldap_changes = {}
    for attr, value in changes.items():
        values = value if isinstance(value, list) else [value]
        ldap_changes[attr] = [(ldap3.MODIFY_REPLACE, values)]

    log.info("ldap.update_entry", dn=dn, attributes=list(changes.keys()))
    conn = _get_connection(creds)
    try:
        success = conn.modify(dn, ldap_changes)
        result = conn.result
    finally:
        conn.unbind()

    if not success:
        raise ValueError(f"LDAP update_entry failed: {result}")

    return {"updated": True, "dn": dn, "result": result}
