"""Microsoft Power BI integration — datasets and reports via Power BI REST API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

POWER_BI_BASE = "https://api.powerbi.com/v1.0/myorg"


def _power_bi_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("power_bi.list_datasets")
async def power_bi_list_datasets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Power BI datasets in the user's workspace.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token with Power BI scope (required)
      group_id     — workspace/group ID (optional, uses "My Workspace" if omitted)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    group_id = merged.get("group_id")

    if group_id:
        endpoint = f"/groups/{group_id}/datasets"
    else:
        endpoint = "/datasets"

    async with httpx.AsyncClient(base_url=POWER_BI_BASE, timeout=30) as client:
        r = await client.get(endpoint, headers=_power_bi_headers(access_token))
        r.raise_for_status()
        data = r.json()

    datasets = data.get("value", [])
    log.info("power_bi.list_datasets", count=len(datasets))
    return {"datasets": datasets, "count": len(datasets)}


@register_node("power_bi.list_reports")
async def power_bi_list_reports(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Power BI reports in the user's workspace.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token with Power BI scope (required)
      group_id     — workspace/group ID (optional, uses "My Workspace" if omitted)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    group_id = merged.get("group_id")

    if group_id:
        endpoint = f"/groups/{group_id}/reports"
    else:
        endpoint = "/reports"

    async with httpx.AsyncClient(base_url=POWER_BI_BASE, timeout=30) as client:
        r = await client.get(endpoint, headers=_power_bi_headers(access_token))
        r.raise_for_status()
        data = r.json()

    reports = data.get("value", [])
    log.info("power_bi.list_reports", count=len(reports))
    return {"reports": reports, "count": len(reports)}


@register_node("power_bi.get_dataset")
async def power_bi_get_dataset(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Power BI dataset by ID.

    config/input_data:
      access_token — Microsoft OAuth2 bearer token with Power BI scope (required)
      dataset_id   — Power BI dataset ID (required)
      group_id     — workspace/group ID (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    dataset_id = merged.get("dataset_id")
    group_id = merged.get("group_id")
    if not dataset_id:
        raise ValueError("dataset_id is required for power_bi.get_dataset")

    if group_id:
        endpoint = f"/groups/{group_id}/datasets/{dataset_id}"
    else:
        endpoint = f"/datasets/{dataset_id}"

    async with httpx.AsyncClient(base_url=POWER_BI_BASE, timeout=30) as client:
        r = await client.get(endpoint, headers=_power_bi_headers(access_token))
        r.raise_for_status()
        dataset = r.json()

    log.info("power_bi.get_dataset", dataset_id=dataset_id, name=dataset.get("name"))
    return {"dataset": dataset, "dataset_id": dataset_id}


@register_node("power_bi.refresh_dataset")
async def power_bi_refresh_dataset(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Trigger a refresh for a Power BI dataset.

    config/input_data:
      access_token     — Microsoft OAuth2 bearer token with Power BI scope (required)
      dataset_id       — Power BI dataset ID to refresh (required)
      group_id         — workspace/group ID (optional)
      notify_option    — refresh notification option: "NoNotification", "MailOnFailure",
                         or "MailOnCompletion" (optional, default "NoNotification")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    dataset_id = merged.get("dataset_id")
    group_id = merged.get("group_id")
    if not dataset_id:
        raise ValueError("dataset_id is required for power_bi.refresh_dataset")

    payload = {"notifyOption": merged.get("notify_option", "NoNotification")}

    if group_id:
        endpoint = f"/groups/{group_id}/datasets/{dataset_id}/refreshes"
    else:
        endpoint = f"/datasets/{dataset_id}/refreshes"

    async with httpx.AsyncClient(base_url=POWER_BI_BASE, timeout=30) as client:
        r = await client.post(endpoint, headers=_power_bi_headers(access_token), json=payload)
        r.raise_for_status()

    log.info("power_bi.refresh_dataset", dataset_id=dataset_id)
    return {"refresh_triggered": True, "dataset_id": dataset_id}
