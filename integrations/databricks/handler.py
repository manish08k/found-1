"""Databricks integration — cluster management, job execution, and run monitoring."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _headers(config: dict) -> dict:
    token = config.get("token") or ""
    if not token:
        raise ValueError("databricks nodes require 'token' in config")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _host(config: dict) -> str:
    host = config.get("host") or ""
    if not host:
        raise ValueError("databricks nodes require 'host' in config (e.g. https://xxx.azuredatabricks.net)")
    return host.rstrip("/")


@register_node("databricks.list_clusters")
async def databricks_list_clusters(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Databricks clusters in the workspace.

    config:
      host  — workspace URL, e.g. https://xxx.azuredatabricks.net
      token — personal access token
    """
    merged = {**config, **input_data}
    base = _host(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/api/2.0/clusters/list", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    clusters = data.get("clusters", [])
    log.info("databricks.list_clusters", count=len(clusters))
    return {"clusters": clusters, "count": len(clusters)}


@register_node("databricks.start_cluster")
async def databricks_start_cluster(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Start a stopped Databricks cluster.

    config:
      host       — workspace URL
      token      — personal access token
      cluster_id — ID of the cluster to start
    """
    merged = {**config, **input_data}
    cluster_id = merged.get("cluster_id")
    if not cluster_id:
        raise ValueError("databricks.start_cluster requires 'cluster_id'")
    base = _host(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base}/api/2.0/clusters/start",
            json={"cluster_id": cluster_id},
            headers=_headers(merged),
        )
        r.raise_for_status()
    log.info("databricks.start_cluster", cluster_id=cluster_id)
    return {"ok": True, "cluster_id": cluster_id}


@register_node("databricks.terminate_cluster")
async def databricks_terminate_cluster(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Terminate (delete) a running Databricks cluster.

    config:
      host       — workspace URL
      token      — personal access token
      cluster_id — ID of the cluster to terminate
    """
    merged = {**config, **input_data}
    cluster_id = merged.get("cluster_id")
    if not cluster_id:
        raise ValueError("databricks.terminate_cluster requires 'cluster_id'")
    base = _host(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base}/api/2.0/clusters/delete",
            json={"cluster_id": cluster_id},
            headers=_headers(merged),
        )
        r.raise_for_status()
    log.info("databricks.terminate_cluster", cluster_id=cluster_id)
    return {"ok": True, "cluster_id": cluster_id}


@register_node("databricks.run_job")
async def databricks_run_job(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Trigger a Databricks job run now.

    config:
      host             — workspace URL
      token            — personal access token
      job_id           — ID of the job to run
      notebook_params  — optional dict of notebook parameter key/value pairs
    """
    merged = {**config, **input_data}
    job_id = merged.get("job_id")
    if not job_id:
        raise ValueError("databricks.run_job requires 'job_id'")
    base = _host(merged)
    payload: dict = {"job_id": int(job_id)}
    notebook_params = merged.get("notebook_params")
    if notebook_params and isinstance(notebook_params, dict):
        payload["notebook_params"] = notebook_params
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base}/api/2.1/jobs/run-now",
            json=payload,
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    run_id = data.get("run_id")
    log.info("databricks.run_job", job_id=job_id, run_id=run_id)
    return {"run_id": run_id, "job_id": int(job_id), "ok": True}


@register_node("databricks.get_run")
async def databricks_get_run(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve the metadata of a Databricks job run.

    config:
      host   — workspace URL
      token  — personal access token
      run_id — ID of the run to retrieve
    """
    merged = {**config, **input_data}
    run_id = merged.get("run_id")
    if not run_id:
        raise ValueError("databricks.get_run requires 'run_id'")
    base = _host(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base}/api/2.1/runs/get",
            params={"run_id": run_id},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    state = data.get("state", {})
    log.info("databricks.get_run", run_id=run_id, life_cycle=state.get("life_cycle_state"))
    return {"run": data, "state": state, "run_id": run_id}


@register_node("databricks.list_jobs")
async def databricks_list_jobs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all jobs defined in the Databricks workspace.

    config:
      host  — workspace URL
      token — personal access token
    """
    merged = {**config, **input_data}
    base = _host(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/api/2.1/jobs/list", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    jobs = data.get("jobs", [])
    log.info("databricks.list_jobs", count=len(jobs))
    return {"jobs": jobs, "count": len(jobs)}
