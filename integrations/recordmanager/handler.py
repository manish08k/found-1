"""
Record manager nodes — track document upsert state for incremental indexing.

Nodes:
  recordmanager.postgres.check      — check if doc IDs already exist
  recordmanager.postgres.update     — mark doc IDs as indexed
  recordmanager.postgres.delete_stale — delete IDs not in current batch
  recordmanager.mysql.check
  recordmanager.mysql.update
  recordmanager.mysql.delete_stale
  recordmanager.sqlite.check
  recordmanager.sqlite.update
  recordmanager.sqlite.delete_stale
"""
import asyncio
import hashlib
import json
import re
import time

import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# ─── helpers ─────────────────────────────────────────────────────────────────

_SQLITE_DBS: dict[str, object] = {}  # path → connection

# Only allow simple alphanumeric + underscore table names to prevent injection
# through the table name (which cannot be parameterized in SQL).
_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def _validate_table_name(table: str) -> str:
    if not _SAFE_IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    return table


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _run_sync(fn):
    """Run a sync function in the default thread pool."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, fn)


# ─── recordmanager.postgres.* ────────────────────────────────────────────────

@register_node("recordmanager.postgres.check")
async def rm_postgres_check(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Check which doc IDs (by content hash) are already indexed.
    config: db_url, table (default autoflow_record_manager), namespace
    input_data: documents (list of {id, content}) OR doc_ids (list of str hashes)
    Returns: {existing: [...], new: [...]}
    """
    import sqlalchemy as sa

    db_url = config.get("db_url") or settings.DATABASE_URL.replace("+asyncpg", "")
    table = _validate_table_name(config.get("table", "autoflow_record_manager"))
    namespace = config.get("namespace", "default")

    documents = input_data.get("documents", [])
    if documents:
        doc_ids = [_content_hash(d.get("content", "") + d.get("id", "")) for d in documents]
    else:
        doc_ids = input_data.get("doc_ids", [])

    def _check():
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            # Ensure table
            conn.execute(sa.text(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    updated_at BIGINT NOT NULL
                )
            """))
            conn.commit()
            if not doc_ids:
                return [], []
            placeholders = ",".join(f":id_{i}" for i in range(len(doc_ids)))
            params = {f"id_{i}": doc_id for i, doc_id in enumerate(doc_ids)}
            params["ns"] = namespace
            result = conn.execute(sa.text(
                f"SELECT id FROM {table} WHERE namespace=:ns AND id IN ({placeholders})"
            ), params)
            existing = {row[0] for row in result.fetchall()}
        new = [d for d in doc_ids if d not in existing]
        return list(existing), new

    existing, new = await _run_sync(_check)
    return {"existing": existing, "new": new, "existing_count": len(existing), "new_count": len(new)}


@register_node("recordmanager.postgres.update")
async def rm_postgres_update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Mark doc IDs as indexed (upsert with current timestamp)."""
    import sqlalchemy as sa

    db_url = config.get("db_url") or settings.DATABASE_URL.replace("+asyncpg", "")
    table = _validate_table_name(config.get("table", "autoflow_record_manager"))
    namespace = config.get("namespace", "default")

    documents = input_data.get("documents", [])
    if documents:
        doc_ids = [_content_hash(d.get("content", "") + d.get("id", "")) for d in documents]
    else:
        doc_ids = input_data.get("doc_ids", [])

    now = int(time.time())

    def _update():
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(sa.text(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    updated_at BIGINT NOT NULL
                )
            """))
            for doc_id in doc_ids:
                conn.execute(sa.text(
                    f"INSERT INTO {table}(id, namespace, updated_at) VALUES (:id, :ns, :ts) "
                    f"ON CONFLICT(id) DO UPDATE SET updated_at=:ts"
                ), {"id": doc_id, "ns": namespace, "ts": now})
            conn.commit()
        return len(doc_ids)

    count = await _run_sync(_update)
    return {"updated": count, "namespace": namespace}


@register_node("recordmanager.postgres.delete_stale")
async def rm_postgres_delete_stale(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete record manager entries not present in current batch (stale docs)."""
    import sqlalchemy as sa

    db_url = config.get("db_url") or settings.DATABASE_URL.replace("+asyncpg", "")
    table = _validate_table_name(config.get("table", "autoflow_record_manager"))
    namespace = config.get("namespace", "default")
    current_ids = input_data.get("current_ids", [])

    def _delete():
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            if current_ids:
                placeholders = ",".join(f":id_{i}" for i in range(len(current_ids)))
                params = {f"id_{i}": cid for i, cid in enumerate(current_ids)}
                params["ns"] = namespace
                result = conn.execute(sa.text(
                    f"DELETE FROM {table} WHERE namespace=:ns AND id NOT IN ({placeholders})"
                ), params)
            else:
                result = conn.execute(sa.text(
                    f"DELETE FROM {table} WHERE namespace=:ns"
                ), {"ns": namespace})
            conn.commit()
            return result.rowcount
        return 0

    deleted = await _run_sync(_delete)
    return {"deleted_stale": deleted, "namespace": namespace}


# ─── recordmanager.mysql.* ───────────────────────────────────────────────────

@register_node("recordmanager.mysql.check")
async def rm_mysql_check(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Check which doc IDs are already indexed in MySQL."""
    import sqlalchemy as sa

    mysql_url = config.get("db_url") or getattr(settings, "MYSQL_URL", "mysql+pymysql://root:@localhost/autoflow")
    table = _validate_table_name(config.get("table", "autoflow_record_manager"))
    namespace = config.get("namespace", "default")

    documents = input_data.get("documents", [])
    doc_ids = [_content_hash(d.get("content", "") + d.get("id", "")) for d in documents] if documents else input_data.get("doc_ids", [])

    def _check():
        engine = sa.create_engine(mysql_url)
        with engine.connect() as conn:
            conn.execute(sa.text(f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    id VARCHAR(64) PRIMARY KEY,
                    namespace VARCHAR(255) NOT NULL,
                    updated_at BIGINT NOT NULL,
                    INDEX idx_ns (namespace)
                )
            """))
            conn.commit()
            if not doc_ids:
                return [], []
            placeholders = ",".join(f":id_{i}" for i in range(len(doc_ids)))
            params = {f"id_{i}": doc_id for i, doc_id in enumerate(doc_ids)}
            params["ns"] = namespace
            result = conn.execute(sa.text(
                f"SELECT id FROM `{table}` WHERE namespace=:ns AND id IN ({placeholders})"
            ), params)
            existing = {row[0] for row in result.fetchall()}
        new = [d for d in doc_ids if d not in existing]
        return list(existing), new

    existing, new = await _run_sync(_check)
    return {"existing": existing, "new": new, "existing_count": len(existing), "new_count": len(new)}


@register_node("recordmanager.mysql.update")
async def rm_mysql_update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Mark doc IDs as indexed in MySQL."""
    import sqlalchemy as sa

    mysql_url = config.get("db_url") or getattr(settings, "MYSQL_URL", "mysql+pymysql://root:@localhost/autoflow")
    table = _validate_table_name(config.get("table", "autoflow_record_manager"))
    namespace = config.get("namespace", "default")
    documents = input_data.get("documents", [])
    doc_ids = [_content_hash(d.get("content", "") + d.get("id", "")) for d in documents] if documents else input_data.get("doc_ids", [])
    now = int(time.time())

    def _update():
        engine = sa.create_engine(mysql_url)
        with engine.connect() as conn:
            for doc_id in doc_ids:
                conn.execute(sa.text(
                    f"INSERT INTO `{table}` (id, namespace, updated_at) VALUES (:id, :ns, :ts) "
                    f"ON DUPLICATE KEY UPDATE updated_at=:ts"
                ), {"id": doc_id, "ns": namespace, "ts": now})
            conn.commit()
        return len(doc_ids)

    count = await _run_sync(_update)
    return {"updated": count, "namespace": namespace}


@register_node("recordmanager.mysql.delete_stale")
async def rm_mysql_delete_stale(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete stale records in MySQL."""
    import sqlalchemy as sa

    mysql_url = config.get("db_url") or getattr(settings, "MYSQL_URL", "mysql+pymysql://root:@localhost/autoflow")
    table = _validate_table_name(config.get("table", "autoflow_record_manager"))
    namespace = config.get("namespace", "default")
    current_ids = input_data.get("current_ids", [])

    def _delete():
        engine = sa.create_engine(mysql_url)
        with engine.connect() as conn:
            if current_ids:
                placeholders = ",".join(f":id_{i}" for i in range(len(current_ids)))
                params = {f"id_{i}": cid for i, cid in enumerate(current_ids)}
                params["ns"] = namespace
                result = conn.execute(sa.text(
                    f"DELETE FROM `{table}` WHERE namespace=:ns AND id NOT IN ({placeholders})"
                ), params)
            else:
                result = conn.execute(sa.text(
                    f"DELETE FROM `{table}` WHERE namespace=:ns"
                ), {"ns": namespace})
            conn.commit()
            return result.rowcount

    deleted = await _run_sync(_delete)
    return {"deleted_stale": deleted, "namespace": namespace}


# ─── recordmanager.sqlite.* ──────────────────────────────────────────────────

@register_node("recordmanager.sqlite.check")
async def rm_sqlite_check(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Check which doc IDs are already indexed in a local SQLite database."""
    import sqlite3

    db_path = config.get("db_path") or getattr(settings, "SQLITE_PATH", "/tmp/autoflow_records.db")
    table = _validate_table_name(config.get("table", "record_manager"))
    namespace = config.get("namespace", "default")

    documents = input_data.get("documents", [])
    doc_ids = [_content_hash(d.get("content", "") + d.get("id", "")) for d in documents] if documents else input_data.get("doc_ids", [])

    def _check():
        conn = sqlite3.connect(db_path)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        conn.commit()
        if not doc_ids:
            conn.close()
            return [], []
        placeholders = ",".join("?" * len(doc_ids))
        cur = conn.execute(
            f"SELECT id FROM {table} WHERE namespace=? AND id IN ({placeholders})",
            [namespace] + doc_ids
        )
        existing = {row[0] for row in cur.fetchall()}
        conn.close()
        new = [d for d in doc_ids if d not in existing]
        return list(existing), new

    existing, new = await _run_sync(_check)
    return {"existing": existing, "new": new, "existing_count": len(existing), "new_count": len(new)}


@register_node("recordmanager.sqlite.update")
async def rm_sqlite_update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Mark doc IDs as indexed in SQLite."""
    import sqlite3

    db_path = config.get("db_path") or getattr(settings, "SQLITE_PATH", "/tmp/autoflow_records.db")
    table = _validate_table_name(config.get("table", "record_manager"))
    namespace = config.get("namespace", "default")
    documents = input_data.get("documents", [])
    doc_ids = [_content_hash(d.get("content", "") + d.get("id", "")) for d in documents] if documents else input_data.get("doc_ids", [])
    now = int(time.time())

    def _update():
        conn = sqlite3.connect(db_path)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, updated_at INTEGER NOT NULL
            )
        """)
        conn.executemany(
            f"INSERT OR REPLACE INTO {table}(id, namespace, updated_at) VALUES (?, ?, ?)",
            [(d, namespace, now) for d in doc_ids]
        )
        conn.commit()
        conn.close()
        return len(doc_ids)

    count = await _run_sync(_update)
    return {"updated": count, "namespace": namespace}


@register_node("recordmanager.sqlite.delete_stale")
async def rm_sqlite_delete_stale(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete stale records in SQLite."""
    import sqlite3

    db_path = config.get("db_path") or getattr(settings, "SQLITE_PATH", "/tmp/autoflow_records.db")
    table = _validate_table_name(config.get("table", "record_manager"))
    namespace = config.get("namespace", "default")
    current_ids = input_data.get("current_ids", [])

    def _delete():
        conn = sqlite3.connect(db_path)
        if current_ids:
            placeholders = ",".join("?" * len(current_ids))
            cur = conn.execute(
                f"DELETE FROM {table} WHERE namespace=? AND id NOT IN ({placeholders})",
                [namespace] + current_ids
            )
        else:
            cur = conn.execute(f"DELETE FROM {table} WHERE namespace=?", [namespace])
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return deleted

    deleted = await _run_sync(_delete)
    return {"deleted_stale": deleted, "namespace": namespace}
