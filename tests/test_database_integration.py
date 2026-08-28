"""Tests for the database.* integration nodes (integrations/database/handler.py)."""
import pytest

from integrations.database.handler import _build_url, _bind_params, _READ_ONLY_PREFIX


def test_build_url_postgres():
    creds = {"db_type": "postgres", "host": "db.internal", "port": 5432,
             "database": "app", "username": "u", "password": "p"}
    url = _build_url(creds)
    assert url == "postgresql+asyncpg://u:p@db.internal:5432/app"


def test_build_url_mysql_default_port():
    creds = {"db_type": "mysql", "host": "db.internal", "database": "app",
             "username": "u", "password": "p"}
    url = _build_url(creds)
    assert url.startswith("mysql+aiomysql://u:p@db.internal:3306/app")


def test_build_url_sqlite():
    creds = {"db_type": "sqlite", "database": "/data/app.db"}
    assert _build_url(creds) == "sqlite+aiosqlite:////data/app.db"


def test_build_url_password_is_url_encoded():
    creds = {"db_type": "postgres", "host": "h", "database": "d",
             "username": "u@user", "password": "p@ss/word"}
    url = _build_url(creds)
    assert "p%40ss%2Fword" in url
    assert "u%40user" in url


def test_build_url_unsupported_type_raises():
    with pytest.raises(ValueError):
        _build_url({"db_type": "mssql", "database": "d"})


@pytest.mark.parametrize("sql", [
    "SELECT * FROM users",
    "  select id from t",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "SHOW TABLES",
    "EXPLAIN SELECT 1",
])
def test_read_only_prefix_allows_reads(sql):
    assert _READ_ONLY_PREFIX.match(sql)


@pytest.mark.parametrize("sql", [
    "INSERT INTO users VALUES (1)",
    "UPDATE users SET x = 1",
    "DELETE FROM users",
    "DROP TABLE users",
    "; SELECT 1; DROP TABLE users; --",
])
def test_read_only_prefix_blocks_writes(sql):
    assert not _READ_ONLY_PREFIX.match(sql)


def test_bind_params_from_config():
    assert _bind_params({"params": {"id": 1}}, {}) == {"id": 1}


def test_bind_params_from_input_data_fallback():
    assert _bind_params({}, {"params": {"id": 2}}) == {"id": 2}


def test_bind_params_defaults_to_empty_dict():
    assert _bind_params({}, {}) == {}


def test_bind_params_rejects_non_dict():
    with pytest.raises(ValueError):
        _bind_params({"params": ["not", "a", "dict"]}, {})


# ── Live integration test ───────────────────────────────────────────────────
# Opt-in: only runs if RUN_LIVE_DB_TESTS=1 and a real MySQL is reachable at
# the given env vars. This is the exact scenario manually verified while
# building this integration (query, execute, injection-safety, read-only
# enforcement) — kept here as a regression test, not run by default in CI
# because it needs a real database rather than the CI Postgres service.
#
#   RUN_LIVE_DB_TESTS=1 LIVE_MYSQL_HOST=127.0.0.1 LIVE_MYSQL_PORT=3306 \
#   LIVE_MYSQL_DB=autoflow_demo LIVE_MYSQL_USER=autoflow_app \
#   LIVE_MYSQL_PASSWORD=... pytest tests/test_database_integration.py -k live
import os

pytestmark_live = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="set RUN_LIVE_DB_TESTS=1 with LIVE_MYSQL_* env vars to run against a real MySQL",
)


@pytestmark_live
@pytest.mark.asyncio
async def test_live_mysql_query_execute_and_injection_safety():
    from integrations.database.handler import _get_engine, _run

    creds = {
        "db_type": "mysql",
        "host": os.environ.get("LIVE_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("LIVE_MYSQL_PORT", "3306")),
        "database": os.environ.get("LIVE_MYSQL_DB", "autoflow_demo"),
        "username": os.environ.get("LIVE_MYSQL_USER", "autoflow_app"),
        "password": os.environ.get("LIVE_MYSQL_PASSWORD", ""),
    }
    engine = _get_engine(creds)

    result = await _run(
        engine, "SELECT id, name, status FROM customers WHERE status = :status ORDER BY id",
        {"status": "active"}, timeout=10, fetch=True, max_rows=100,
    )
    assert result["row_count"] >= 1

    exec_result = await _run(
        engine, "UPDATE customers SET status = :s WHERE name = :n",
        {"s": "vip", "n": "Asha Rao"}, timeout=10, fetch=False, max_rows=0,
    )
    assert exec_result["row_count"] in (0, 1)  # 0 if already run once before

    # A string containing SQL keywords, passed as a bound parameter, must
    # never be treated as executable SQL.
    injection = "'; DROP TABLE customers; --"
    safe = await _run(
        engine, "SELECT id FROM customers WHERE name = :n",
        {"n": injection}, timeout=10, fetch=True, max_rows=10,
    )
    assert safe["row_count"] == 0
    still_there = await _run(engine, "SELECT COUNT(*) as c FROM customers", {}, timeout=10, fetch=True, max_rows=10)
    assert still_there["rows"][0]["c"] >= 3

    await engine.dispose()
