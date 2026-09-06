"""Google BigQuery integration — run queries, manage datasets and tables."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BQ_BASE = "https://bigquery.googleapis.com/bigquery/v2"


def _bq_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("google_bigquery.run_query")
async def google_bigquery_run_query(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Run a synchronous SQL query in Google BigQuery.

    config:
      project_id   — GCP project ID (required)
      access_token — OAuth bearer token with bigquery.jobs.create permission (required)
      query        — SQL query string (required)
      use_legacy_sql — whether to use legacy SQL syntax, default False
      timeout_ms   — query timeout in milliseconds (optional, default 30000)
      max_results  — max rows to return (optional, default 1000)
    """
    merged = {**config, **input_data}
    project_id = merged.get("project_id")
    access_token = merged.get("access_token", "")
    query = merged.get("query")

    if not project_id or not query:
        raise ValueError("project_id and query are required for google_bigquery.run_query")

    payload = {
        "query": query,
        "useLegacySql": merged.get("use_legacy_sql", False),
        "timeoutMs": merged.get("timeout_ms", 30000),
        "maxResults": merged.get("max_results", 1000),
    }

    async with httpx.AsyncClient(base_url=BQ_BASE, timeout=60) as client:
        r = await client.post(
            f"/projects/{project_id}/queries",
            headers=_bq_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    rows = data.get("rows", [])
    schema = data.get("schema", {})
    total_rows = data.get("totalRows", "0")
    log.info(
        "google_bigquery.run_query",
        project_id=project_id,
        total_rows=total_rows,
        job_complete=data.get("jobComplete"),
    )
    return {
        "rows": rows,
        "schema": schema,
        "total_rows": total_rows,
        "job_complete": data.get("jobComplete"),
        "job_reference": data.get("jobReference"),
    }


@register_node("google_bigquery.list_datasets")
async def google_bigquery_list_datasets(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all datasets in a BigQuery project.

    config:
      project_id   — GCP project ID (required)
      access_token — OAuth bearer token (required)
      max_results  — max datasets to return (optional, default 100)
    """
    merged = {**config, **input_data}
    project_id = merged.get("project_id")
    access_token = merged.get("access_token", "")

    if not project_id:
        raise ValueError("project_id is required for google_bigquery.list_datasets")

    params = {"maxResults": merged.get("max_results", 100)}

    async with httpx.AsyncClient(base_url=BQ_BASE, timeout=30) as client:
        r = await client.get(
            f"/projects/{project_id}/datasets",
            headers=_bq_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    datasets = data.get("datasets", [])
    log.info("google_bigquery.list_datasets", project_id=project_id, count=len(datasets))
    return {"datasets": datasets, "count": len(datasets)}


@register_node("google_bigquery.list_tables")
async def google_bigquery_list_tables(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all tables in a BigQuery dataset.

    config:
      project_id   — GCP project ID (required)
      access_token — OAuth bearer token (required)
      dataset_id   — dataset ID (required)
      max_results  — max tables to return (optional, default 100)
    """
    merged = {**config, **input_data}
    project_id = merged.get("project_id")
    access_token = merged.get("access_token", "")
    dataset_id = merged.get("dataset_id")

    if not project_id or not dataset_id:
        raise ValueError("project_id and dataset_id are required for google_bigquery.list_tables")

    params = {"maxResults": merged.get("max_results", 100)}

    async with httpx.AsyncClient(base_url=BQ_BASE, timeout=30) as client:
        r = await client.get(
            f"/projects/{project_id}/datasets/{dataset_id}/tables",
            headers=_bq_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    tables = data.get("tables", [])
    log.info(
        "google_bigquery.list_tables",
        project_id=project_id,
        dataset_id=dataset_id,
        count=len(tables),
    )
    return {"tables": tables, "count": len(tables)}


@register_node("google_bigquery.insert_rows")
async def google_bigquery_insert_rows(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Insert rows into a BigQuery table using streaming insertAll.

    config:
      project_id   — GCP project ID (required)
      access_token — OAuth bearer token (required)
      dataset_id   — dataset ID (required)
      table_id     — table ID (required)
      rows         — list of row dicts to insert (required)
      skip_invalid — skip invalid rows instead of failing, default False
    """
    merged = {**config, **input_data}
    project_id = merged.get("project_id")
    access_token = merged.get("access_token", "")
    dataset_id = merged.get("dataset_id")
    table_id = merged.get("table_id")
    rows = merged.get("rows", [])

    if not project_id or not dataset_id or not table_id:
        raise ValueError(
            "project_id, dataset_id, and table_id are required for google_bigquery.insert_rows"
        )
    if not rows:
        raise ValueError("rows list is required for google_bigquery.insert_rows")

    payload = {
        "rows": [{"json": row} for row in rows],
        "skipInvalidRows": merged.get("skip_invalid", False),
    }

    async with httpx.AsyncClient(base_url=BQ_BASE, timeout=30) as client:
        r = await client.post(
            f"/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}/insertAll",
            headers=_bq_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    insert_errors = data.get("insertErrors", [])
    log.info(
        "google_bigquery.insert_rows",
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        rows_inserted=len(rows),
        errors=len(insert_errors),
    )
    return {
        "insert_errors": insert_errors,
        "rows_inserted": len(rows),
        "success": len(insert_errors) == 0,
    }


@register_node("google_bigquery.get_table")
async def google_bigquery_get_table(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get metadata and schema of a BigQuery table.

    config:
      project_id   — GCP project ID (required)
      access_token — OAuth bearer token (required)
      dataset_id   — dataset ID (required)
      table_id     — table ID (required)
    """
    merged = {**config, **input_data}
    project_id = merged.get("project_id")
    access_token = merged.get("access_token", "")
    dataset_id = merged.get("dataset_id")
    table_id = merged.get("table_id")

    if not project_id or not dataset_id or not table_id:
        raise ValueError(
            "project_id, dataset_id, and table_id are required for google_bigquery.get_table"
        )

    async with httpx.AsyncClient(base_url=BQ_BASE, timeout=30) as client:
        r = await client.get(
            f"/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}",
            headers=_bq_headers(access_token),
        )
        r.raise_for_status()
        table = r.json()

    log.info(
        "google_bigquery.get_table",
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
    )
    return {"table": table, "schema": table.get("schema", {})}
