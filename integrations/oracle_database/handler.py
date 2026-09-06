"""Oracle Database integration — SQL queries and data management."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("oracle_database.execute_query")
async def oracle_database_execute_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    try:
        import cx_Oracle
        conn_str = f"{merged.get('username', '')}/{merged.get('password', '')}@{merged.get('host', '')}:{merged.get('port', 1521)}/{merged.get('service', '')}"
        with cx_Oracle.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute(merged.get("query", "SELECT 1 FROM DUAL"), merged.get("params", []))
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return {"rows": [dict(zip(columns, row)) for row in rows], "row_count": len(rows)}
    except ImportError:
        return {"error": "cx_Oracle not installed. Install with: pip install cx_Oracle", "rows": []}
    except Exception as e:
        return {"error": str(e), "rows": []}


@register_node("oracle_database.execute_dml")
async def oracle_database_execute_dml(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    try:
        import cx_Oracle
        conn_str = f"{merged.get('username', '')}/{merged.get('password', '')}@{merged.get('host', '')}:{merged.get('port', 1521)}/{merged.get('service', '')}"
        with cx_Oracle.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute(merged.get("query", ""), merged.get("params", []))
            conn.commit()
            return {"rows_affected": cursor.rowcount, "success": True}
    except ImportError:
        return {"error": "cx_Oracle not installed", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}
